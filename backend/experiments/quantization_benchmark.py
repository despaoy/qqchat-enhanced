"""量化基准实验 - 对比 FP16/BF16 / AWQ / NF4 / INT8 的质量-延迟-显存前沿。

遵循路线图 guardrail：
- 每次实验记录 model/tokenizer/vLLM/CUDA/driver/prompt set/命令行
- 结论是条件性的（"AWQ 在满足质量阈值的同时降低显存"），而非"AWQ 普遍最优"
- 支持 --mock 模式用于 CPU 开发机验证
"""
from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import sys
import time
import statistics
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional, Callable

logger = logging.getLogger(__name__)
_BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(_BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(_BACKEND_DIR))

# pynvml 显存测量（复用 trainer.py:59 模式）
HAS_PYNVML = False
try:
    import pynvml
    pynvml.nvmlInit()
    HAS_PYNVML = True
except Exception:
    pass


def _get_vram_mb() -> Optional[float]:
    """获取 GPU 0 的已用显存（MB）。"""
    if HAS_PYNVML:
        try:
            handle = pynvml.nvmlDeviceGetHandleByIndex(0)
            info = pynvml.nvmlDeviceGetMemoryInfo(handle)
            return round(info.used / 1024 / 1024, 1)
        except Exception:
            pass
    return None


@dataclass
class QuantizationConfig:
    """量化基准配置。"""
    label: str
    model_path: str
    quantization: str  # fp16 | bf16 | awq | nf4 | int8
    max_model_len: int = 4096
    gpu_memory_utilization: float = 0.90
    dtype: str = "auto"
    vllm_url: str = "http://localhost:8001"
    served_model_name: str = ""


@dataclass
class BenchmarkResult:
    """单配置基准结果。"""
    label: str
    quantization: str
    load_time_s: float = 0.0
    vram_mb: Optional[float] = None
    ttft_ms: float = 0.0
    decode_tokens_per_s: float = 0.0
    p50_latency_ms: float = 0.0
    p95_latency_ms: float = 0.0
    p99_latency_ms: float = 0.0
    quality_score: float = 0.0
    quality_metrics: Dict[str, Any] = field(default_factory=dict)
    error: str = ""
    timestamp: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class QuantizationBenchmark:
    """量化基准运行器。"""

    # 默认对比配置
    DEFAULT_CONFIGS = [
        QuantizationConfig(label="fp16", model_path="", quantization="fp16", dtype="float16"),
        QuantizationConfig(label="awq", model_path="", quantization="awq", dtype="float16"),
        QuantizationConfig(label="nf4", model_path="", quantization="nf4", dtype="float16"),
        QuantizationConfig(label="int8", model_path="", quantization="int8", dtype="float16"),
    ]

    # 基准测试 prompt 集（覆盖短/中/长、角色/知识/闲聊）
    DEFAULT_PROMPTS = [
        "你好，请介绍一下你自己。",
        "胡桃的元素战技是什么？",
        "钟离的护盾机制详细说明一下。",
        "原神的元素反应系统有哪些？",
        "请用胡桃的语气说一段话。",
        "深渊螺旋怎么配队比较好？",
        "七七的治疗量受什么属性影响？",
        "魈的输出手法是什么？",
    ]

    def __init__(self, vllm_url: str = "http://localhost:8001"):
        self.vllm_url = vllm_url

    async def _call_vllm(self, config: QuantizationConfig, prompt: str,
                         max_tokens: int = 128) -> Dict[str, Any]:
        """调用 vLLM OpenAI 兼容 API，返回延迟和回复。"""
        import httpx
        url = f"{config.vllm_url}/v1/chat/completions"
        model_id = config.served_model_name or config.model_path
        start = time.monotonic()
        try:
            async with httpx.AsyncClient(timeout=120.0) as client:
                r = await client.post(url, json={
                    "model": model_id,
                    "messages": [{"role": "user", "content": prompt}],
                    "max_tokens": max_tokens,
                    "temperature": 0.7,
                })
            latency_ms = (time.monotonic() - start) * 1000
            if r.status_code != 200:
                return {"ok": False, "latency_ms": latency_ms, "error": f"HTTP {r.status_code}: {r.text[:200]}", "reply": "", "completion_tokens": 0}
            data = r.json()
            reply = data.get("choices", [{}])[0].get("message", {}).get("content", "")
            usage = data.get("usage", {})
            completion_tokens = usage.get("completion_tokens", 0)
            return {"ok": True, "latency_ms": latency_ms, "reply": reply, "completion_tokens": completion_tokens, "error": ""}
        except Exception as e:
            latency_ms = (time.monotonic() - start) * 1000
            return {"ok": False, "latency_ms": latency_ms, "error": str(e)[:200], "reply": "", "completion_tokens": 0}

    async def benchmark_model(self, config: QuantizationConfig,
                              prompts: Optional[List[str]] = None) -> BenchmarkResult:
        """对单个配置运行基准测试。"""
        prompts = prompts or self.DEFAULT_PROMPTS
        result = BenchmarkResult(
            label=config.label,
            quantization=config.quantization,
            timestamp=datetime.now().isoformat(),
        )

        # 测量加载时间（首请求视为含加载时间）
        load_start = time.monotonic()
        first = await self._call_vllm(config, prompts[0], max_tokens=32)
        result.load_time_s = round(time.monotonic() - load_start, 2)

        if not first["ok"]:
            result.error = first["error"]
            return result

        # TTFT 近似为首请求延迟（含模型加载），后续请求测量纯推理
        result.ttft_ms = round(first["latency_ms"], 1)
        result.vram_mb = _get_vram_mb()

        # 收集延迟样本
        latencies: List[float] = [first["latency_ms"]]
        replies: List[str] = [first["reply"]]
        total_tokens = first["completion_tokens"]

        for prompt in prompts[1:]:
            r = await self._call_vllm(config, prompt, max_tokens=128)
            if r["ok"]:
                latencies.append(r["latency_ms"])
                replies.append(r["reply"])
                total_tokens += r["completion_tokens"]
            else:
                replies.append("")
                logger.warning(f"请求失败 ({config.label}): {r['error']}")

        # 计算延迟分位数
        if latencies:
            sorted_lat = sorted(latencies)
            n = len(sorted_lat)
            result.p50_latency_ms = round(sorted_lat[n // 2], 1)
            result.p95_latency_ms = round(sorted_lat[int(n * 0.95)] if n > 1 else sorted_lat[0], 1)
            result.p99_latency_ms = round(sorted_lat[min(int(n * 0.99), n - 1)] if n > 1 else sorted_lat[0], 1)

            # 解码吞吐：总 token / 总推理时间（排除首请求加载时间）
            inference_time_s = sum(latencies[1:]) / 1000 if len(latencies) > 1 else latencies[0] / 1000
            if inference_time_s > 0 and total_tokens > 0:
                result.decode_tokens_per_s = round(total_tokens / inference_time_s, 1)

        # 质量评分：用 GenerationMetrics 计算 distinct_1 + distinct_2 均值
        try:
            from evaluation.generation_metrics import GenerationMetrics
            gm = GenerationMetrics()
            d1 = gm.distinct_n(replies, 1)
            d2 = gm.distinct_n(replies, 2)
            rep = sum(gm.repetition_rate(r) for r in replies) / max(len(replies), 1)
            result.quality_metrics = {
                "distinct_1": d1,
                "distinct_2": d2,
                "avg_repetition_rate": round(rep, 4),
            }
            # 综合质量分：多样性高 + 重复率低 => 高分
            result.quality_score = round((d1 + d2) / 2 * (1 - rep), 4)
        except Exception as e:
            logger.warning(f"质量评分计算失败: {e}")
            result.quality_metrics = {"error": str(e)}

        return result

    def benchmark_model_mock(self, config: QuantizationConfig) -> BenchmarkResult:
        """Mock 模式：返回预置结果用于 CPU 验证。"""
        # 模拟不同量化的特性：fp16 显存最高质量最好，量化后显存降但质量略降
        base = {
            "fp16": {"vram": 14800, "ttft": 120, "tps": 85, "quality": 0.82},
            "bf16": {"vram": 14900, "ttft": 125, "tps": 82, "quality": 0.83},
            "awq": {"vram": 6200, "ttft": 95, "tps": 110, "quality": 0.78},
            "nf4": {"vram": 5100, "ttft": 110, "tps": 95, "quality": 0.75},
            "int8": {"vram": 7800, "ttft": 105, "tps": 92, "quality": 0.76},
        }
        m = base.get(config.quantization, base["fp16"])
        return BenchmarkResult(
            label=config.label,
            quantization=config.quantization,
            load_time_s=round(8.5 + hash(config.label) % 30 / 10, 1),
            vram_mb=m["vram"],
            ttft_ms=m["ttft"],
            decode_tokens_per_s=m["tps"],
            p50_latency_ms=round(m["ttft"] * 1.2, 1),
            p95_latency_ms=round(m["ttft"] * 1.8, 1),
            p99_latency_ms=round(m["ttft"] * 2.5, 1),
            quality_score=m["quality"],
            quality_metrics={
                "distinct_1": round(m["quality"] * 0.9, 4),
                "distinct_2": round(m["quality"] * 0.85, 4),
                "avg_repetition_rate": round(1 - m["quality"], 4),
                "mock": True,
            },
            timestamp=datetime.now().isoformat(),
        )

    async def run_comparison(self, configs: List[QuantizationConfig],
                             prompts: Optional[List[str]] = None,
                             mock: bool = False) -> List[BenchmarkResult]:
        """运行多配置对比。"""
        results: List[BenchmarkResult] = []
        for cfg in configs:
            logger.info(f"基准测试: {cfg.label} ({cfg.quantization})")
            if mock:
                results.append(self.benchmark_model_mock(cfg))
            else:
                r = await self.benchmark_model(cfg, prompts)
                results.append(r)
        return results

    def build_comparison_table(self, results: List[BenchmarkResult]) -> str:
        """生成 Markdown 对比表。"""
        header = "| label | quant | load_s | vram_mb | ttft_ms | tokens/s | p50_ms | p95_ms | p99_ms | quality |"
        sep = "|-------|-------|--------|---------|---------|----------|--------|--------|--------|---------|"
        rows = [header, sep]
        for r in results:
            vram = f"{r.vram_mb:.0f}" if r.vram_mb is not None else "N/A"
            rows.append(
                f"| {r.label} | {r.quantization} | {r.load_time_s} | {vram} | "
                f"{r.ttft_ms} | {r.decode_tokens_per_s} | {r.p50_latency_ms} | "
                f"{r.p95_latency_ms} | {r.p99_latency_ms} | {r.quality_score} |"
            )
        return "\n".join(rows)

    def save_report(self, results: List[BenchmarkResult], output_dir: Path,
                    environment: Optional[Dict[str, str]] = None) -> Path:
        """保存 JSON + Markdown 报告。"""
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")

        # 环境信息（遵循 guardrail：记录 model/vLLM/CUDA/driver）
        env_info = {
            "timestamp": ts,
            "vllm_version": os.getenv("VLLM_VERSION", "unknown"),
            "cuda_version": os.getenv("CUDA_VERSION", "unknown"),
            "driver_version": os.getenv("NVIDIA_DRIVER", "unknown"),
            "python_version": sys.version.split()[0],
            **(environment or {}),
        }

        # JSON 报告
        report = {
            "experiment_type": "quantization_benchmark",
            "environment": env_info,
            "results": [r.to_dict() for r in results],
            "comparison_table": self.build_comparison_table(results),
        }
        json_path = output_dir / f"quantization_benchmark_{ts}.json"
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2, ensure_ascii=False)

        # Markdown 报告
        md_path = output_dir / f"quantization_benchmark_{ts}.md"
        with open(md_path, "w", encoding="utf-8") as f:
            f.write(f"# 量化基准实验报告\n\n")
            f.write(f"**时间**: {ts}\n\n")
            f.write(f"## 环境\n\n")
            for k, v in env_info.items():
                f.write(f"- **{k}**: {v}\n")
            f.write(f"\n## 对比结果\n\n")
            f.write(self.build_comparison_table(results))
            f.write("\n\n## 结论\n\n")
            f.write(self._generate_conclusion(results))
        logger.info(f"报告已保存: {json_path}, {md_path}")
        return json_path

    def _generate_conclusion(self, results: List[BenchmarkResult]) -> str:
        """生成条件性结论（遵循 guardrail：不宣称普遍最优）。"""
        if not results:
            return "无结果。"
        best_quality = max(results, key=lambda r: r.quality_score)
        lowest_vram = min(results, key=lambda r: r.vram_mb or 99999)
        fastest = max(results, key=lambda r: r.decode_tokens_per_s)
        return (
            f"- 质量最高: **{best_quality.label}** (quality={best_quality.quality_score})\n"
            f"- 显存最低: **{lowest_vram.label}** (vram={lowest_vram.vram_mb}MB)\n"
            f"- 吞吐最高: **{fastest.label}** (tokens/s={fastest.decode_tokens_per_s})\n\n"
            f"结论是条件性的：需根据目标并发和 VRAM 预算选择量化方案，"
            f"而非宣称某一方案普遍最优。"
        )


def main():
    parser = argparse.ArgumentParser(description="量化基准实验")
    parser.add_argument("--mock", action="store_true", help="Mock 模式（CPU 验证）")
    parser.add_argument("--output-dir", type=str, default="deploy/results", help="报告输出目录")
    parser.add_argument("--vllm-url", type=str, default="http://localhost:8001", help="vLLM 服务地址")
    parser.add_argument("--model-path", type=str, default="", help="模型路径")
    parser.add_argument("--prompts-file", type=str, default="", help="自定义 prompt 集 JSON 文件")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

    prompts = QuantizationBenchmark.DEFAULT_PROMPTS
    if args.prompts_file:
        with open(args.prompts_file, "r", encoding="utf-8") as f:
            prompts = json.load(f)

    benchmark = QuantizationBenchmark(vllm_url=args.vllm_url)

    configs = [
        QuantizationConfig(label="fp16", model_path=args.model_path, quantization="fp16", vllm_url=args.vllm_url),
        QuantizationConfig(label="awq", model_path=args.model_path, quantization="awq", vllm_url=args.vllm_url),
        QuantizationConfig(label="nf4", model_path=args.model_path, quantization="nf4", vllm_url=args.vllm_url),
        QuantizationConfig(label="int8", model_path=args.model_path, quantization="int8", vllm_url=args.vllm_url),
    ]

    if args.mock:
        results = [benchmark.benchmark_model_mock(cfg) for cfg in configs]
    else:
        results = asyncio.run(benchmark.run_comparison(configs, prompts, mock=False))

    print("\n" + "=" * 70)
    print("  量化基准对比结果")
    print("=" * 70)
    print(benchmark.build_comparison_table(results))

    output_dir = Path(args.output_dir)
    report_path = benchmark.save_report(results, output_dir)
    print(f"\n报告已保存: {report_path}")


if __name__ == "__main__":
    main()
