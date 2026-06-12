"""直接测试vLLM推理"""
import httpx, time

BASE = "http://localhost:8001"
MODEL = "/root/autodl-tmp/models/Qwen/Qwen2___5-7B-Instruct"

print("测试vLLM直接推理...")
start = time.monotonic()
try:
    r = httpx.post(f"{BASE}/v1/chat/completions", json={
        "model": MODEL,
        "messages": [{"role": "user", "content": "你好"}],
        "max_tokens": 100,
    }, timeout=60)
    latency = (time.monotonic() - start) * 1000
    print(f"Status: {r.status_code}, Latency: {latency:.0f}ms")
    if r.status_code == 200:
        data = r.json()
        content = data["choices"][0]["message"]["content"]
        print(f"Reply: {content[:200]}")
        print(f"Tokens: prompt={data['usage']['prompt_tokens']}, completion={data['usage']['completion_tokens']}")
    else:
        print(f"Error: {r.text[:300]}")
except Exception as e:
    print(f"Exception: {e}")

# 测试后端generate
print("\n测试后端 /api/generate...")
BASE2 = "http://localhost:8000"
# 先登录
r = httpx.post(f"{BASE2}/api/auth/login", json={"username": "bench_tester", "password": "bench123456"}, timeout=5)
if r.status_code != 200:
    r = httpx.post(f"{BASE2}/api/auth/login", json={"username": "lihemu", "password": "lihemu"}, timeout=5)
print(f"Login: {r.status_code}")
if r.status_code == 200:
    cookies = r.cookies
    start = time.monotonic()
    try:
        r2 = httpx.post(f"{BASE2}/api/generate", json={
            "message": "你好",
            "lora_name": "minamo_lora"
        }, cookies=cookies, timeout=60)
        latency = (time.monotonic() - start) * 1000
        print(f"Status: {r2.status_code}, Latency: {latency:.0f}ms")
        print(f"Response: {r2.text[:300]}")
    except Exception as e:
        print(f"Exception: {e}")
