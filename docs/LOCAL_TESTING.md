# 本地基础验证指南

适用机器：Windows 本地开发机，例如 i9-13900H + RTX 4060。目标是先验证前后端、数据库、接口代理和 Mock 推理链路，不强制启动 vLLM 或训练大模型。

## 1. 快速验证后端基础功能

在项目根目录运行：

```powershell
pnpm verify:local
```

它会执行：

- Python 语法检查
- 后端核心测试 `backend/tests/test_core.py`
- `git diff --check` 空白检查

如果需要顺带跑前端类型检查：

```powershell
pnpm verify:local:frontend
```

前端检查依赖 `node_modules` 正常。如果项目目录移动过，建议重新安装依赖。

## 2. 以 Mock 模式启动后端

```powershell
pnpm local:backend
```

默认地址：

```text
http://127.0.0.1:8000
```

这个启动方式会设置：

- `MODEL_PROVIDER=mock`
- `VLLM_ENABLED=false`
- `VLLM_BASE_URLS=`

因此不会加载大模型，适合本地验证登录、消息、知识库元数据、配置、前端 API 代理等基础链路。

## 3. 本地建议验证顺序

1. `pnpm verify:local`
2. `pnpm local:backend`
3. 打开 `http://127.0.0.1:8000/docs`
4. 另开终端运行 `pnpm dev`
5. 打开 `http://localhost:5000`

RTX 4060 可以后续尝试 Ollama 或小量化模型，但项目基础修复阶段优先用 Mock 模式。
