#!/usr/bin/env python3
"""
QQ智能助手 - vLLM 推理服务启动脚本

在 E5-2680 + 2×RTX 3090 (24GB×2) 上使用 vLLM 启动 Qwen2.5-7B 推理服务。

硬件适配:
  - 2×3090 24GB: 使用张量并行 (tensor-parallel-size=2)
  - 单卡 24GB 足以容纳 Qwen2.5-7B AWQ 4bit + KV Cache
  - 总吞吐量: ~50-60 req/s (远超 30 req/s 需求)

启动:
  python scripts/launch_vllm.py                    # FP16 + TP=2
  python scripts/launch_vllm.py --quant awq        # AWQ 4bit 量化
  python scripts/launch_vllm.py --model Qwen/Qwen2.5-7B-Instruct
  python scripts/launch_vllm.py --lora-path ./loras/hutao_lora_7b/final

要求:
  pip install vllm
"""
import argparse
import subprocess
import sys
from pathlib import Path


def build_args(args) -> list:
    """构建 vLLM 启动参数"""
    _BACKEND = Path(__file__).parent.parent
    cmd = [
        sys.executable, "-m", "vllm.entrypoints.openai.api_server",
        "--host", args.host,
        "--port", str(args.port),
        "--model", args.model,
        "--served-model-name", args.served_name or args.model.split("/")[-1],
        "--max-model-len", str(args.max_model_len),
        "--gpu-memory-utilization", str(args.gpu_mem_util),
        "--max-num-seqs", str(args.max_num_seqs),
        "--max-num-batched-tokens", str(args.max_batched_tokens),
    ]

    # 双卡张量并行
    if args.tensor_parallel > 1:
        cmd += ["--tensor-parallel-size", str(args.tensor_parallel)]

    # 量化
    if args.quant:
        cmd += ["--quantization", args.quant]

    # LoRA 适配器
    if args.lora_path:
        lora_path = str(Path(args.lora_path).resolve())
        cmd += [
            "--enable-lora",
            "--max-lora-rank", str(args.max_lora_rank),
            "--lora-modules", f"hutao={lora_path}",
        ]

    # 数据类型
    if args.dtype:
        cmd += ["--dtype", args.dtype]

    # 前缀缓存 (共享 system prompt)
    if args.enable_prefix_caching:
        cmd += ["--enable-prefix-caching"]

    return cmd


def main():
    parser = argparse.ArgumentParser(description="vLLM 推理服务启动器 (QQ智能助手)")
    parser.add_argument("--host", default="0.0.0.0", help="监听地址")
    parser.add_argument("--port", type=int, default=8001, help="监听端口 (不要让 FastAPI 占用)")
    parser.add_argument("--model", default="Qwen/Qwen2.5-7B-Instruct",
                        help="模型名称或本地路径")
    parser.add_argument("--served-name", default="qwen2.5-7b",
                        help="对外暴露的模型名")
    parser.add_argument("--max-model-len", type=int, default=4096,
                        help="最大上下文长度 (RTX 3090 24GB 推荐 4096-8192)")
    parser.add_argument("--gpu-mem-util", type=float, default=0.90,
                        help="GPU 显存利用率 (0-1)")
    parser.add_argument("--max-num-seqs", type=int, default=64,
                        help="最大并发序列数 (Continuous Batching 上限)")
    parser.add_argument("--max-batched-tokens", type=int, default=8192,
                        help="单次 batch 最大 token 数")
    parser.add_argument("--tensor-parallel", type=int, default=2,
                        help="张量并行数 (2×3090 → 2)")
    parser.add_argument("--quant", choices=["awq", "gptq", "fp8"],
                        default="awq", help="量化方法 (AWQ 推荐, 23%显存节省)")
    parser.add_argument("--dtype", default="auto",
                        help="数据类型 (auto/float16/bfloat16)")
    parser.add_argument("--lora-path", help="LoRA 适配器路径")
    parser.add_argument("--max-lora-rank", type=int, default=16,
                        help="LoRA 最大秩")
    parser.add_argument("--enable-prefix-caching", action="store_true",
                        default=True, help="启用前缀缓存 (共享 system prompt KV Cache)")
    parser.add_argument("--no-quant", action="store_true",
                        help="不使用量化 (FP16 模式, 需 TP=2)")

    args = parser.parse_args()

    if args.no_quant:
        args.quant = ""
        print("[INFO] FP16 模式 (不使用量化) — 需要双卡张量并行")

    cmd = build_args(args)
    print(f"[vLLM] 启动命令: {' '.join(cmd)}")
    print(f"[vLLM] API 地址: http://{args.host}:{args.port}/v1")
    print(f"[vLLM] 模型: {args.model}")
    print(f"[vLLM] 量化: {args.quant or 'FP16'}")
    print(f"[vLLM] 张量并行: TP={args.tensor_parallel}")
    print(f"[vLLM] 最大并发序列: {args.max_num_seqs}")
    print("-" * 60)

    subprocess.run(cmd)


if __name__ == "__main__":
    main()
