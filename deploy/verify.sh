#!/bin/bash
# QQ智能助手 - 部署验证脚本
# 用法: bash deploy/verify.sh

set -euo pipefail
GREEN='\033[0;32m'; RED='\033[0;31m'; NC='\033[0m'
PASS=0; FAIL=0

check() {
    local name="$1"; shift
    if "$@" &>/dev/null; then
        echo -e "${GREEN}[PASS]${NC} $name"; ((PASS++))
    else
        echo -e "${RED}[FAIL]${NC} $name"; ((FAIL++))
    fi
}

echo "=== QQ智能助手 部署验证 ==="

# 1. 启动服务
echo "[1/6] 启动 Docker Compose..."
docker compose -f deploy/docker-compose.yml up -d 2>/dev/null || true

# 2. 等待 vLLM
echo "[2/6] 等待 vLLM 就绪（最多 120s）..."
for i in $(seq 1 24); do
    curl -sf http://localhost:8001/health &>/dev/null && break
    sleep 5
done
check "vLLM health" curl -sf http://localhost:8001/health

# 3. 等待 Backend
echo "[3/6] 等待 Backend 就绪（最多 60s）..."
for i in $(seq 1 12); do
    curl -sf http://localhost:8000/health &>/dev/null && break
    sleep 5
done
check "Backend /health" curl -sf http://localhost:8000/health
check "Backend /ready" curl -sf http://localhost:8000/ready

# 4. 等待 Frontend
echo "[4/6] 等待 Frontend 就绪..."
for i in $(seq 1 12); do
    curl -sf -o /dev/null http://localhost:5000 &>/dev/null && break
    sleep 5
done
check "Frontend 首页" curl -sf -o /dev/null http://localhost:5000

# 5. 业务全链路测试
echo "[5/6] 业务链路测试..."
TOKEN=""
# 注册
REG=$(curl -s -X POST http://localhost:8000/api/auth/register \
    -H "Content-Type: application/json" \
    -d '{"username":"verifyuser","password":"Verify123!@#"}')
check "注册" echo "$REG" | grep -q "success"

# 登录 + 获取 Cookie
LOGIN=$(curl -s -c /tmp/verify_cookie.txt -X POST http://localhost:8000/api/auth/login \
    -H "Content-Type: application/json" \
    -d '{"username":"verifyuser","password":"Verify123!@#"}')
check "登录" echo "$LOGIN" | grep -q "success"

# 创建知识库
KB=$(curl -s -b /tmp/verify_cookie.txt -X POST http://localhost:8000/api/knowledge/bases \
    -H "Content-Type: application/json" \
    -d '{"name":"部署验证库","description":"auto-test"}')
check "创建知识库" echo "$KB" | grep -q "success"

# 搜索
SEARCH=$(curl -s -X POST http://localhost:8000/api/knowledge/search \
    -H "Content-Type: application/json" \
    -d '{"query":"test","topK":3}')
check "知识搜索" echo "$SEARCH" | grep -q "success"

# 注销
LOGOUT=$(curl -s -b /tmp/verify_cookie.txt -X POST http://localhost:8000/api/auth/logout)
check "注销" echo "$LOGOUT" | grep -q "success"

rm -f /tmp/verify_cookie.txt

# 6. 统计
echo ""
echo "=== 验证完成 ==="
echo -e "通过: ${GREEN}${PASS}${NC}  失败: ${RED}${FAIL}${NC}"
if [[ $FAIL -gt 0 ]]; then
    echo "请检查失败项，查看日志: docker compose -f deploy/docker-compose.yml logs"
    exit 1
else
    echo "部署验证全部通过！"
fi
