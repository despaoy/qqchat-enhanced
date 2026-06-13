"""推理专项压测 - 限流窗口重置后运行"""
import asyncio
import httpx
import time
import statistics
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
BASE = "http://localhost:8000"


async def main():
    # 登录
    async with httpx.AsyncClient(timeout=10.0) as c:
        r = await c.post(f"{BASE}/api/auth/login", json={
            "username": "bench_tester", "password": "bench123456"
        })
        cookies = r.cookies
        print(f"Login: {r.status_code}")

    if r.status_code != 200:
        print("登录失败，退出")
        return

    # 1. 串行推理 (5次) - 测单请求延迟
    print("\n=== 串行推理测试 (5次) ===")
    serial_latencies = []
    for i in range(5):
        start = time.monotonic()
        async with httpx.AsyncClient(timeout=60.0, cookies=cookies) as c:
            r = await c.post(f"{BASE}/api/generate", json={
                "message": f"你好{i}", "lora_name": "minamo_lora"
            })
        latency = (time.monotonic() - start) * 1000
        serial_latencies.append(latency)
        print(f"  #{i+1}: status={r.status_code}, latency={latency:.0f}ms")
        if r.status_code != 200:
            print(f"    body: {r.text[:100]}")

    if serial_latencies:
        print(f"  平均: {statistics.mean(serial_latencies):.0f}ms")
        print(f"  最小: {min(serial_latencies):.0f}ms")
        print(f"  最大: {max(serial_latencies):.0f}ms")

    # 等待限流窗口重置
    print("\n等待5秒...")
    await asyncio.sleep(5)

    # 2. 并发推理 (3并发)
    print("\n=== 并发推理测试 (3并发) ===")
    async def one_req(i):
        start = time.monotonic()
        async with httpx.AsyncClient(timeout=60.0, cookies=cookies) as c:
            r = await c.post(f"{BASE}/api/generate", json={
                "message": f"并发测试{i}", "lora_name": "minamo_lora"
            })
        latency = (time.monotonic() - start) * 1000
        return {"status": r.status_code, "latency": latency, "body": r.text[:80]}

    start = time.monotonic()
    results = await asyncio.gather(*[one_req(i) for i in range(3)])
    duration = time.monotonic() - start
    for r in results:
        print(f"  status={r['status']}, latency={r['latency']:.0f}ms")
    success = [r for r in results if r["status"] == 200]
    if success:
        print(f"  总耗时: {duration:.1f}s, QPS: {len(success)/duration:.2f}")

    # 等待限流窗口重置
    print("\n等待5秒...")
    await asyncio.sleep(5)

    # 3. 并发推理 (5并发)
    print("\n=== 并发推理测试 (5并发) ===")
    start = time.monotonic()
    results = await asyncio.gather(*[one_req(i) for i in range(5)])
    duration = time.monotonic() - start
    for r in results:
        print(f"  status={r['status']}, latency={r['latency']:.0f}ms")
    success = [r for r in results if r["status"] == 200]
    if success:
        print(f"  总耗时: {duration:.1f}s, QPS: {len(success)/duration:.2f}")

    # 4. 缓存测试 - 相同消息
    print("\n=== 缓存效果测试 (相同消息x5) ===")
    await asyncio.sleep(3)
    cache_latencies = []
    for i in range(5):
        start = time.monotonic()
        async with httpx.AsyncClient(timeout=60.0, cookies=cookies) as c:
            r = await c.post(f"{BASE}/api/generate", json={
                "message": "你好，请问你是谁？", "lora_name": "minamo_lora"
            })
        latency = (time.monotonic() - start) * 1000
        cache_latencies.append(latency)
        print(f"  #{i+1}: status={r.status_code}, latency={latency:.0f}ms")

    if len(cache_latencies) > 1 and cache_latencies[0] > 0:
        first = cache_latencies[0]
        rest_avg = statistics.mean(cache_latencies[1:])
        speedup = first / rest_avg if rest_avg > 0 else 0
        print(f"  首次: {first:.0f}ms, 后续平均: {rest_avg:.0f}ms, 加速比: {speedup:.1f}x")

    # 5. 纯API吞吐 (公开端点, 无需认证)
    print("\n=== 纯API吞吐 (/health, 200并发) ===")
    async def health_req():
        start = time.monotonic()
        async with httpx.AsyncClient(timeout=10.0) as c:
            r = await c.get(f"{BASE}/health")
        latency = (time.monotonic() - start) * 1000
        return {"status": r.status_code, "latency": latency}

    start = time.monotonic()
    results = await asyncio.gather(*[health_req() for _ in range(200)])
    duration = time.monotonic() - start
    success = [r for r in results if r["status"] == 200]
    latencies = sorted([r["latency"] for r in success])
    print(f"  QPS: {len(success)/duration:.1f}")
    print(f"  P50: {latencies[len(latencies)//2]:.0f}ms")
    print(f"  P95: {latencies[int(len(latencies)*0.95)]:.0f}ms")
    print(f"  P99: {latencies[int(len(latencies)*0.99)]:.0f}ms")


if __name__ == "__main__":
    asyncio.run(main())
