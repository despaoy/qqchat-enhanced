"""快速注册+登录测试用户"""
import requests
import sys

BASE = "http://localhost:8000"

# 注册
r = requests.post(f"{BASE}/api/auth/register", json={"username": "bench_user", "password": "bench123456"}, timeout=5)
print(f"Register: {r.status_code} {r.text[:200]}")

# 登录
r = requests.post(f"{BASE}/api/auth/login", json={"username": "bench_user", "password": "bench123456"}, timeout=5)
print(f"Login: {r.status_code} {r.text[:200]}")

if r.status_code == 200:
    cookie = r.headers.get("Set-Cookie", "")
    token_part = cookie.split(";")[0] if cookie else ""
    print(f"Cookie: {token_part}")

    # 测试受保护端点
    r2 = requests.get(f"{BASE}/api/loras", headers={"Cookie": token_part}, timeout=5)
    print(f"Loras: {r2.status_code} {r2.text[:100]}")

    # 测试generate
    r3 = requests.post(f"{BASE}/api/generate", json={"message": "你好", "lora_name": "minamo_lora"}, headers={"Cookie": token_part}, timeout=30)
    print(f"Generate: {r3.status_code} {r3.text[:200]}")
