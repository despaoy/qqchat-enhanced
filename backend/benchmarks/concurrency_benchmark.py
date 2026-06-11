#!/usr/bin/env python3
"""
QQ智能助手 — 全链路并发压力测试

测试场景:
  - 多个3000人群聊，高峰时每群每秒3次提问
  - 10群高峰: 30 req/s
  - 30群高峰: 90 req/s
  - 50群高峰: 150 req/s

测试维度:
  1. LLM推理并发 (核心瓶颈)
  2. API代理层吞吐
  3. 数据库读写并发
  4. 知识库搜索并发
  5. 全链路端到端

使用:
  $env:PYTHONIOENCODING='utf-8'
  python concurrency_benchmark.py
  python concurrency_benchmark.py --quick          # 快速模式
  python concurrency_benchmark.py --target generate # 仅测LLM推理
  python concurrency_benchmark.py --target all      # 全链路测试
"""

import asyncio
import time
import json
import statistics
import sys
import os
import argparse
import traceback
from dataclasses import dataclass, field
from typing import Optional, List, Dict
from collections import defaultdict

import httpx

# ============================================================
# 配置
# ============================================================
BASE_URL = os.getenv("TEST_BASE_URL", "http://localhost:8000")
NEXTJS_URL = os.getenv("TEST_NEXTJS_URL", "http://localhost:5000")

HEALTH_URL = f"{BASE_URL}/health"
GENERATE_URL = f"{BASE_URL}/api/generate"
STATS_URL = f"{BASE_URL}/api/stats"
MESSAGES_URL = f"{BASE_URL}/api/messages"
LORAS_URL = f"{BASE_URL}/api/loras"
KNOWLEDGE_SEARCH_URL = f"{BASE_URL}/api/knowledge/search"
KNOWLEDGE_STATS_URL = f"{BASE_URL}/api/knowledge/stats"
MODEL_STATUS_URL = f"{BASE_URL}/api/model/status"

# QQ 群聊真实消息样本
GROUP_MESSAGES = [
    "在吗", "今天吃什么", "哈哈哈哈笑死我了", "这个功能怎么用来着",
    "有人一起打游戏吗", "晚安", "早", "最近有什么好看的番推荐吗",
    "我emo了怎么办", "大佬们帮忙看看这个问题", "谢谢", "你说的对但是",
    "啊啊啊好烦", "有人吗有人吗有人吗", "周末有没有一起出去玩的",
    "分享一个好玩的视频", "哈哈哈", "不太懂，能讲详细点吗", "辛苦了", "嗯嗯知道了",
    "胡桃你在吗", "帮我查一下原神的攻略", "这个角色怎么配队", "深渊怎么打",
    "圣遗物怎么选", "今天活动什么时候开始", "抽卡建议", "新手应该练谁",
]

# ============================================================
# 数据结构
# ============================================================
@dataclass
class RequestResult:
    success: bool
    status_code: int
    latency_ms: float
    endpoint: str = ""
    error: Optional[str] = None
    tokens: int = 0


@dataclass
class BenchmarkReport:
    test_name: str
    concurrent_level: int
    total_requests: int
    duration_seconds: float
    results: List[RequestResult] = field(default_factory=list)

    @property
    def success_count(self) -> int:
        return sum(1 for r in self.results if r.success)

    @property
    def failure_count(self) -> int:
        return sum(1 for r in self.results if not r.success)

    @property
    def success_rate(self) -> float:
        return self.success_count / self.total_requests * 100 if self.total_requests else 0

    @property
    def throughput_qps(self) -> float:
        return self.total_requests / self.duration_seconds if self.duration_seconds else 0

    @property
    def latencies_ms(self) -> List[float]:
        return [r.latency_ms for r in self.results if r.success]

    @property
    def p50_ms(self) -> float:
        lats = self.latencies_ms
        return statistics.median(lats) if lats else 0

    @property
    def p90_ms(self) -> float:
        lats = self.latencies_ms
        if not lats: return 0
        s = sorted(lats)
        return s[min(int(len(s) * 0.9), len(s) - 1)]

    @property
    def p99_ms(self) -> float:
        lats = self.latencies_ms
        if not lats: return 0
        s = sorted(lats)
        return s[min(int(len(s) * 0.99), len(s) - 1)]

    @property
    def avg_ms(self) -> float:
        lats = self.latencies_ms
        return statistics.mean(lats) if lats else 0

    @property
    def min_ms(self) -> float:
        lats = self.latencies_ms
        return min(lats) if lats else 0

    @property
    def max_ms(self) -> float:
        lats = self.latencies_ms
        return max(lats) if lats else 0

    @property
    def error_distribution(self) -> Dict[str, int]:
        dist = defaultdict(int)
        for r in self.results:
            if not r.success and r.error:
                short = r.error[:80].split('\n')[0]
                dist[short] += 1
        return dict(sorted(dist.items(), key=lambda x: -x[1]))

    def print_report(self):
        print(f"\n{'='*70}")
        print(f"  {self.test_name}")
        print(f"{'='*70}")
        print(f"  并发级别:     {self.concurrent_level}")
        print(f"  总请求数:     {self.total_requests}")
        print(f"  持续时间:     {self.duration_seconds:.1f}s")
        print(f"  成功/失败:    {self.success_count}/{self.failure_count} ({self.success_rate:.1f}%)")
        print(f"  吞吐量:       {self.throughput_qps:.2f} req/s")
        print(f"{'─'*70}")
        if self.latencies_ms:
            print(f"  延迟 (ms):")
            print(f"    平均:       {self.avg_ms:.0f}")
            print(f"    P50:        {self.p50_ms:.0f}")
            print(f"    P90:        {self.p90_ms:.0f}")
            print(f"    P99:        {self.p99_ms:.0f}")
            print(f"    最小/最大:  {self.min_ms:.0f} / {self.max_ms:.0f}")
        else:
            print(f"  延迟:         无成功请求")
        if self.error_distribution:
            print(f"{'─'*70}")
            print(f"  错误分布:")
            for err, cnt in list(self.error_distribution.items())[:5]:
                print(f"    [{cnt}x] {err}")
        print(f"{'='*70}")


# ============================================================
# 服务检查
# ============================================================
async def check_backend_health() -> bool:
    try:
        async with httpx.AsyncClient(timeout=5.0) as c:
            r = await c.get(HEALTH_URL)
            return r.status_code == 200
    except Exception:
        return False


async def detect_model() -> dict:
    try:
        async with httpx.AsyncClient(timeout=10.0) as c:
            r = await c.get(MODEL_STATUS_URL)
            if r.status_code == 200:
                return r.json()
    except Exception:
        pass
    return {}


async def check_gpu_status():
    try:
        import subprocess
        result = subprocess.run(
            ['nvidia-smi', '--query-gpu=memory.used,memory.total,utilization.gpu,temperature.gpu',
             '--format=csv,noheader,nounits'],
            capture_output=True, text=True, timeout=5
        )
        if result.returncode == 0:
            parts = result.stdout.strip().split(',')
            if len(parts) >= 3:
                print(f"  GPU: {parts[0].strip()}/{parts[1].strip()}MB, 利用率:{parts[2].strip()}%", end="")
                if len(parts) >= 4:
                    print(f", 温度:{parts[3].strip()}C", end="")
                print()
    except Exception:
        pass


# ============================================================
# 测试1: LLM推理并发压测 (核心瓶颈)
# ============================================================
async def test_llm_concurrency(concurrent: int, total: int) -> BenchmarkReport:
    """测试 /api/generate 的并发推理能力"""
    sem = asyncio.Semaphore(concurrent)
    results = []
    start_time = time.time()

    async def worker(idx: int):
        async with sem:
            msg = GROUP_MESSAGES[idx % len(GROUP_MESSAGES)]
            payload = {
                "message": msg,
                "sessionType": "group",
                "sessionId": f"bench_group_{idx % 50}",
                "sessionName": f"压测群{idx % 50}",
                "userId": f"bench_user_{idx % 300}",
                "userName": f"测试用户{idx % 300}",
            }
            req_start = time.time()
            try:
                async with httpx.AsyncClient(timeout=httpx.Timeout(120.0, connect=10.0)) as client:
                    resp = await client.post(GENERATE_URL, json=payload)
                    latency = (time.time() - req_start) * 1000
                    if resp.status_code == 200:
                        data = resp.json()
                        tokens = len(data.get("reply", "")) // 2
                        return RequestResult(True, 200, latency, "generate", tokens=tokens)
                    elif resp.status_code == 429:
                        return RequestResult(False, 429, latency, "generate", error="Rate limited")
                    else:
                        return RequestResult(False, resp.status_code, latency, "generate",
                                             error=f"HTTP {resp.status_code}: {resp.text[:100]}")
            except httpx.TimeoutException:
                return RequestResult(False, 0, (time.time() - req_start) * 1000, "generate", error="Timeout")
            except Exception as e:
                return RequestResult(False, 0, (time.time() - req_start) * 1000, "generate", error=str(e)[:150])

    tasks = [worker(i) for i in range(total)]
    raw = await asyncio.gather(*tasks, return_exceptions=True)
    for r in raw:
        if isinstance(r, Exception):
            results.append(RequestResult(False, 0, 0, "generate", error=str(r)[:150]))
        else:
            results.append(r)

    duration = time.time() - start_time
    return BenchmarkReport(
        test_name="LLM推理并发压测 (/api/generate)",
        concurrent_level=concurrent,
        total_requests=total,
        duration_seconds=duration,
        results=results,
    )


# ============================================================
# 测试2: API代理层吞吐 (不涉及LLM)
# ============================================================
async def test_api_throughput(concurrent: int, total: int) -> BenchmarkReport:
    """测试纯API读取端点的吞吐量 (stats/messages/loras)"""
    endpoints = [
        ("GET", STATS_URL, None),
        ("GET", MESSAGES_URL + "?limit=20", None),
        ("GET", LORAS_URL, None),
    ]
    sem = asyncio.Semaphore(concurrent)
    results = []
    start_time = time.time()

    async def worker(idx: int):
        async with sem:
            method, url, body = endpoints[idx % len(endpoints)]
            req_start = time.time()
            try:
                async with httpx.AsyncClient(timeout=30.0) as client:
                    if method == "GET":
                        resp = await client.get(url)
                    else:
                        resp = await client.post(url, json=body)
                    latency = (time.time() - req_start) * 1000
                    if resp.status_code == 200:
                        return RequestResult(True, 200, latency, url.split("/")[-1])
                    else:
                        return RequestResult(False, resp.status_code, latency, url.split("/")[-1],
                                             error=f"HTTP {resp.status_code}")
            except Exception as e:
                return RequestResult(False, 0, (time.time() - req_start) * 1000, url.split("/")[-1],
                                     error=str(e)[:100])

    tasks = [worker(i) for i in range(total)]
    raw = await asyncio.gather(*tasks, return_exceptions=True)
    for r in raw:
        if isinstance(r, Exception):
            results.append(RequestResult(False, 0, 0, "api", error=str(r)[:100]))
        else:
            results.append(r)

    duration = time.time() - start_time
    return BenchmarkReport(
        test_name="API代理层吞吐 (stats/messages/loras)",
        concurrent_level=concurrent,
        total_requests=total,
        duration_seconds=duration,
        results=results,
    )


# ============================================================
# 测试3: 数据库读写并发
# ============================================================
async def test_db_concurrency(concurrent: int, total: int) -> BenchmarkReport:
    """测试数据库读写并发 (消息写入+统计读取)"""
    sem = asyncio.Semaphore(concurrent)
    results = []
    start_time = time.time()

    async def worker(idx: int):
        async with sem:
            req_start = time.time()
            try:
                async with httpx.AsyncClient(timeout=30.0) as client:
                    if idx % 3 == 0:
                        # 写: 生成回复(触发DB写入)
                        payload = {
                            "message": GROUP_MESSAGES[idx % len(GROUP_MESSAGES)],
                            "sessionType": "group",
                            "sessionId": f"db_test_{idx % 20}",
                            "sessionName": f"DB测试群{idx % 20}",
                            "userId": f"db_user_{idx % 100}",
                            "userName": f"DB用户{idx % 100}",
                        }
                        resp = await client.post(GENERATE_URL, json=payload,
                                                 timeout=httpx.Timeout(120.0, connect=10.0))
                    elif idx % 3 == 1:
                        # 读: 消息列表
                        resp = await client.get(MESSAGES_URL + "?limit=50&offset=0")
                    else:
                        # 读: 统计数据
                        resp = await client.get(STATS_URL)

                    latency = (time.time() - req_start) * 1000
                    if resp.status_code == 200:
                        return RequestResult(True, 200, latency, "db_rw")
                    else:
                        return RequestResult(False, resp.status_code, latency, "db_rw",
                                             error=f"HTTP {resp.status_code}")
            except Exception as e:
                return RequestResult(False, 0, (time.time() - req_start) * 1000, "db_rw",
                                     error=str(e)[:100])

    tasks = [worker(i) for i in range(total)]
    raw = await asyncio.gather(*tasks, return_exceptions=True)
    for r in raw:
        if isinstance(r, Exception):
            results.append(RequestResult(False, 0, 0, "db", error=str(r)[:100]))
        else:
            results.append(r)

    duration = time.time() - start_time
    return BenchmarkReport(
        test_name="数据库读写并发 (1/3写 + 2/3读)",
        concurrent_level=concurrent,
        total_requests=total,
        duration_seconds=duration,
        results=results,
    )


# ============================================================
# 测试4: 知识库搜索并发
# ============================================================
async def test_knowledge_search(concurrent: int, total: int) -> BenchmarkReport:
    """测试知识库语义搜索并发"""
    queries = ["胡桃", "原神攻略", "深渊配队", "圣遗物", "角色培养", "活动时间", "抽卡建议"]
    sem = asyncio.Semaphore(concurrent)
    results = []
    start_time = time.time()

    async def worker(idx: int):
        async with sem:
            query = queries[idx % len(queries)]
            payload = {"query": query, "top_k": 5}
            req_start = time.time()
            try:
                async with httpx.AsyncClient(timeout=30.0) as client:
                    resp = await client.post(KNOWLEDGE_SEARCH_URL, json=payload)
                    latency = (time.time() - req_start) * 1000
                    if resp.status_code == 200:
                        return RequestResult(True, 200, latency, "knowledge_search")
                    else:
                        return RequestResult(False, resp.status_code, latency, "knowledge_search",
                                             error=f"HTTP {resp.status_code}")
            except Exception as e:
                return RequestResult(False, 0, (time.time() - req_start) * 1000, "knowledge_search",
                                     error=str(e)[:100])

    tasks = [worker(i) for i in range(total)]
    raw = await asyncio.gather(*tasks, return_exceptions=True)
    for r in raw:
        if isinstance(r, Exception):
            results.append(RequestResult(False, 0, 0, "knowledge", error=str(r)[:100]))
        else:
            results.append(r)

    duration = time.time() - start_time
    return BenchmarkReport(
        test_name="知识库搜索并发",
        concurrent_level=concurrent,
        total_requests=total,
        duration_seconds=duration,
        results=results,
    )


# ============================================================
# 测试5: 模拟真实群聊场景 (持续压力)
# ============================================================
async def test_realistic_group_chat(num_groups: int, msgs_per_sec_per_group: float,
                                     duration_seconds: float) -> BenchmarkReport:
    """
    模拟真实群聊场景
    num_groups: 群数量
    msgs_per_sec_per_group: 每群每秒消息数
    duration_seconds: 持续时间
    """
    total_expected = int(num_groups * msgs_per_sec_per_group * duration_seconds)
    interval = 1.0 / msgs_per_sec_per_group if msgs_per_sec_per_group > 0 else 1.0
    results = []
    start_time = time.time()

    async def group_worker(group_id: int):
        """单个群的持续消息发送"""
        msg_idx = 0
        while time.time() - start_time < duration_seconds:
            msg = GROUP_MESSAGES[msg_idx % len(GROUP_MESSAGES)]
            payload = {
                "message": msg,
                "sessionType": "group",
                "sessionId": f"group_{group_id}",
                "sessionName": f"群聊{group_id}",
                "userId": f"user_{group_id}_{msg_idx % 3000}",
                "userName": f"群友{msg_idx % 3000}",
            }
            req_start = time.time()
            try:
                async with httpx.AsyncClient(timeout=httpx.Timeout(120.0, connect=10.0)) as client:
                    resp = await client.post(GENERATE_URL, json=payload)
                    latency = (time.time() - req_start) * 1000
                    if resp.status_code == 200:
                        data = resp.json()
                        tokens = len(data.get("reply", "")) // 2
                        results.append(RequestResult(True, 200, latency, f"group_{group_id}", tokens=tokens))
                    elif resp.status_code == 429:
                        results.append(RequestResult(False, 429, latency, f"group_{group_id}", error="Rate limited"))
                    else:
                        results.append(RequestResult(False, resp.status_code, latency, f"group_{group_id}",
                                                     error=f"HTTP {resp.status_code}"))
            except httpx.TimeoutException:
                results.append(RequestResult(False, 0, (time.time() - req_start) * 1000, f"group_{group_id}",
                                             error="Timeout"))
            except Exception as e:
                results.append(RequestResult(False, 0, (time.time() - req_start) * 1000, f"group_{group_id}",
                                             error=str(e)[:100]))

            msg_idx += 1
            # 按频率等待
            elapsed = time.time() - req_start / 1000
            wait = max(0, interval - elapsed)
            if wait > 0:
                await asyncio.sleep(wait)

    # 启动所有群的工作协程
    tasks = [group_worker(gid) for gid in range(num_groups)]
    await asyncio.gather(*tasks, return_exceptions=True)

    actual_duration = time.time() - start_time
    return BenchmarkReport(
        test_name=f"真实群聊模拟 ({num_groups}群 × {msgs_per_sec_per_group}msg/s/群, 持续{duration_seconds}s)",
        concurrent_level=num_groups,
        total_requests=len(results),
        duration_seconds=actual_duration,
        results=results,
    )


# ============================================================
# 测试6: 阶梯式极限探测
# ============================================================
async def test_staircase_probe(endpoint: str = "generate") -> List[BenchmarkReport]:
    """逐步增加并发，找到系统崩溃点"""
    if endpoint == "generate":
        plan = [
            (1,   5,   "基准"),
            (3,   10,  "低并发"),
            (5,   15,  "中低并发"),
            (10,  25,  "中并发 (LLM信号量上限)"),
            (15,  30,  "中高并发 (超出信号量)"),
            (20,  40,  "高并发"),
            (30,  50,  "高并发+"),
            (50,  80,  "极高并发"),
            (80,  100, "极限并发"),
            (100, 120, "超限并发"),
        ]
        test_fn = test_llm_concurrency
    elif endpoint == "api":
        plan = [
            (10,  30,  "低并发"),
            (30,  60,  "中并发"),
            (50,  100, "中高并发"),
            (100, 200, "高并发"),
            (200, 400, "极高并发"),
            (500, 800, "极限并发"),
        ]
        test_fn = test_api_throughput
    else:
        plan = [
            (5,   15,  "低并发"),
            (10,  25,  "中并发"),
            (20,  40,  "高并发"),
            (50,  80,  "极高并发"),
        ]
        test_fn = test_knowledge_search

    reports = []
    for concurrent, total, desc in plan:
        print(f"\n{'─'*50}")
        print(f"  阶梯测试: {desc} — {concurrent}并发, {total}请求")
        print(f"{'─'*50}")
        await check_gpu_status()

        report = await test_fn(concurrent, total)
        report.test_name = f"[{desc}] {report.test_name}"
        report.print_report()
        reports.append(report)

        # 成功率低于80%则停止
        if report.success_rate < 80:
            print(f"\n  [STOP] 成功率 {report.success_rate:.1f}% < 80%, 系统已达极限")
            print(f"  推荐最大稳定并发: {concurrent // 2}")
            break

        # P99超过30秒也停止
        if report.p99_ms > 30000:
            print(f"\n  [STOP] P99延迟 {report.p99_ms:.0f}ms > 30s, 用户体验不可接受")
            print(f"  推荐最大稳定并发: {concurrent // 2}")
            break

        await asyncio.sleep(3)

    return reports


# ============================================================
# 主流程
# ============================================================
async def main():
    parser = argparse.ArgumentParser(description="QQ智能助手 全链路并发压测")
    parser.add_argument("--quick", action="store_true", help="快速模式（减少请求数）")
    parser.add_argument("--target", choices=["generate", "api", "knowledge", "db", "realistic", "all", "staircase"],
                        default="staircase", help="测试目标")
    parser.add_argument("--groups", type=int, default=10, help="真实场景模拟群数")
    parser.add_argument("--duration", type=int, default=30, help="真实场景持续时间(秒)")
    args = parser.parse_args()

    print("=" * 70)
    print("  QQ智能助手 — 全链路并发压力测试")
    print(f"  后端: {BASE_URL}")
    print(f"  测试目标: {args.target}")
    print("=" * 70)

    # 服务检查
    if not await check_backend_health():
        print("[ERROR] 后端服务不可用，请先启动: python main.py")
        return

    # 模型探测
    model_info = await detect_model()
    provider = model_info.get("provider", "unknown")
    model_name = model_info.get("model_name", "unknown")
    lora = model_info.get("lora_name") or model_info.get("active_lora") or "无"
    print(f"  模型: {provider} / {model_name}")
    print(f"  LoRA: {lora}")
    await check_gpu_status()

    # 预热
    print("\n[WARM] 预热模型...")
    warm_start = time.time()
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(120.0, connect=10.0)) as client:
            resp = await client.post(GENERATE_URL, json={
                "message": "你好", "sessionType": "group",
                "sessionId": "warmup", "sessionName": "预热",
                "userId": "warmup_user", "userName": "预热用户",
            })
            if resp.status_code == 200:
                print(f"[WARM] 预热完成, 耗时 {time.time()-warm_start:.1f}s")
            else:
                print(f"[WARM] 预热返回 {resp.status_code}, 继续测试...")
    except Exception as e:
        print(f"[WARM] 预热失败: {e}, 继续测试...")

    all_reports = []

    if args.target == "staircase" or args.target == "all":
        print("\n" + "#" * 70)
        print("  阶段1: LLM推理阶梯压测")
        print("#" * 70)
        reports = await test_staircase_probe("generate")
        all_reports.extend(reports)

    if args.target == "all":
        print("\n" + "#" * 70)
        print("  阶段2: API代理层阶梯压测")
        print("#" * 70)
        reports = await test_staircase_probe("api")
        all_reports.extend(reports)

        print("\n" + "#" * 70)
        print("  阶段3: 知识库搜索阶梯压测")
        print("#" * 70)
        reports = await test_staircase_probe("knowledge")
        all_reports.extend(reports)

    if args.target == "generate":
        if args.quick:
            plan = [(1, 3, "基准"), (5, 8, "低并发"), (10, 15, "中并发")]
        else:
            plan = [
                (1,  5,  "基准"),
                (5,  15, "低并发"),
                (10, 25, "中并发"),
                (15, 30, "中高并发"),
                (20, 40, "高并发"),
                (30, 50, "极高并发"),
            ]
        for concurrent, total, desc in plan:
            report = await test_llm_concurrency(concurrent, total)
            report.test_name = f"[{desc}] {report.test_name}"
            report.print_report()
            all_reports.append(report)
            if report.success_rate < 80:
                print(f"\n  [STOP] 成功率低于80%")
                break
            await asyncio.sleep(2)

    if args.target == "api":
        reports = await test_staircase_probe("api")
        all_reports.extend(reports)

    if args.target == "knowledge":
        reports = await test_staircase_probe("knowledge")
        all_reports.extend(reports)

    if args.target == "db":
        if args.quick:
            plan = [(5, 10, "低并发"), (10, 20, "中并发"), (20, 30, "高并发")]
        else:
            plan = [(5, 15, "低并发"), (10, 30, "中并发"), (20, 50, "高并发"), (30, 60, "极高并发")]
        for concurrent, total, desc in plan:
            report = await test_db_concurrency(concurrent, total)
            report.test_name = f"[{desc}] {report.test_name}"
            report.print_report()
            all_reports.append(report)
            if report.success_rate < 80:
                break
            await asyncio.sleep(2)

    if args.target == "realistic":
        print(f"\n  模拟场景: {args.groups}个群 × 3msg/s/群 = {args.groups*3} req/s, 持续{args.duration}s")
        report = await test_realistic_group_chat(args.groups, 3.0, args.duration)
        report.print_report()
        all_reports.append(report)

    # ============================================================
    # 综合评估报告
    # ============================================================
    print("\n\n" + "=" * 70)
    print("  综 合 评 估 报 告")
    print("=" * 70)

    if all_reports:
        # 找到LLM测试的最大稳定并发
        llm_reports = [r for r in all_reports if "generate" in r.test_name.lower() or "LLM" in r.test_name]
        api_reports = [r for r in all_reports if "API" in r.test_name or "api" in r.test_name.lower()]
        knowledge_reports = [r for r in all_reports if "knowledge" in r.test_name.lower() or "知识" in r.test_name]

        if llm_reports:
            stable_llm = [r for r in llm_reports if r.success_rate >= 95]
            if stable_llm:
                max_stable = max(r.concurrent_level for r in stable_llm)
                best_stable = next(r for r in stable_llm if r.concurrent_level == max_stable)
                print(f"\n  LLM推理:")
                print(f"    最大稳定并发:  {max_stable}")
                print(f"    对应吞吐量:    {best_stable.throughput_qps:.1f} req/s")
                print(f"    P50延迟:       {best_stable.p50_ms:.0f}ms")
                print(f"    P99延迟:       {best_stable.p99_ms:.0f}ms")
                print(f"    成功率:        {best_stable.success_rate:.1f}%")
            else:
                print(f"\n  LLM推理: 所有并发级别均不稳定 (成功率<95%)")

        if api_reports:
            stable_api = [r for r in api_reports if r.success_rate >= 95]
            if stable_api:
                max_stable = max(r.concurrent_level for r in stable_api)
                best_stable = next(r for r in stable_api if r.concurrent_level == max_stable)
                print(f"\n  API代理层:")
                print(f"    最大稳定并发:  {max_stable}")
                print(f"    对应吞吐量:    {best_stable.throughput_qps:.1f} req/s")
                print(f"    P50延迟:       {best_stable.p50_ms:.0f}ms")

        if knowledge_reports:
            stable_kn = [r for r in knowledge_reports if r.success_rate >= 95]
            if stable_kn:
                max_stable = max(r.concurrent_level for r in stable_kn)
                best_stable = next(r for r in stable_kn if r.concurrent_level == max_stable)
                print(f"\n  知识库搜索:")
                print(f"    最大稳定并发:  {max_stable}")
                print(f"    对应吞吐量:    {best_stable.throughput_qps:.1f} req/s")

    # 场景推算
    print(f"\n{'─'*70}")
    print(f"  场景推算 (3000人群, 高峰3msg/s/群):")
    print(f"{'─'*70}")
    print(f"    10群高峰 (30 req/s):  需要 LLM 推理能力 ≥ 30 req/s")
    print(f"    30群高峰 (90 req/s):  需要 LLM 推理能力 ≥ 90 req/s")
    print(f"    50群高峰 (150 req/s): 需要 LLM 推理能力 ≥ 150 req/s")
    print(f"")
    print(f"  当前系统限制:")
    print(f"    LLM信号量:     10 并发")
    print(f"    Uvicorn连接:   500 并发")
    print(f"    限流器全局QPS: 100 req/s (如果启用)")
    print(f"    单GPU推理:     串行 (同步httpx阻塞事件循环)")

    print(f"\n{'─'*70}")
    print(f"  优化建议:")
    print(f"{'─'*70}")
    print(f"""
  1. [紧急] model_manager.py 使用同步 httpx.Client 阻塞事件循环
     → 改为 httpx.AsyncClient，或用 asyncio.to_thread() 包装同步调用

  2. [紧急] SQLite 无连接池、无WAL模式、无busy_timeout
     → 启用 resource_pool.py 中的 ConnectionPool (已有但未接入)
     → 或至少添加 PRAGMA journal_mode=WAL; PRAGMA busy_timeout=5000;

  3. [重要] LLM信号量无超时，超出10并发会无限挂起
     → 添加 asyncio.wait_for(semaphore.acquire(), timeout=30)
     → 或使用有界队列 + 超时拒绝策略

  4. [重要] QQ Bot路径 (qq_bot_hutao.py) 无任何并发控制
     → 添加推理信号量，防止GPU OOM
     → 添加消息队列，串行化推理请求

  5. [重要] TransformersPeftProvider.set_lora_adapter() 无锁
     → 添加 asyncio.Lock 防止并发LoRA切换导致状态混乱

  6. [建议] 对于50群×3msg/s=150req/s的高峰场景:
     - 单GPU(Qwen2.5-7B 4bit): 推理约2-5s/条, 实际吞吐约0.2-0.5 req/s
     - 需要 vLLM/TGI 等推理框架实现 Continuous Batching
     - 或部署多实例 + 负载均衡 (已有 load_balancer.py 但未接入)
     - 或使用更小模型 (3B) + 量化以提升吞吐

  7. [建议] Next.js API代理层无超时、无重试
     → 添加 AbortController + 30s超时
     → 添加指数退避重试 (仅对5xx)
     → 添加请求去重 (SWR模式)
""")

    # 最终GPU状态
    print("  最终GPU状态:")
    await check_gpu_status()
    print("\n" + "=" * 70)


if __name__ == "__main__":
    asyncio.run(main())
