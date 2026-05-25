# Codex Cool

**AI API 代理转发服务** — 在 Codex App / Claude App 与多种 LLM 提供商之间做协议转换，让你用任意模型驱动官方桌面应用。

## ✨ 核心功能

| 功能 | 说明 |
|------|------|
| **多协议转换** | OpenAI Responses ↔ Chat ↔ Anthropic Messages 三种格式互转 |
| **Codex App 注入** | 一键注入代理到 `~/.codex/config.toml`，替换官方 API |
| **Claude App 注入** | 自动配置第三方推理网关（Developer Mode + 3P 模式） |
| **检查点机制** | 支持 `previous_response_id` 链式对话，实现 Codex 检查点功能 |
| **多模态清理** | 自动清理图片/文件内容，适配不支持多模态的模型（DeepSeek 等） |
| **熔断保护** | 内置 Circuit Breaker，上游故障自动切换 |
| **桌面应用** | macOS 原生 .app 打包，内置 WebUI 管理面板 |
| **i18n 国际化** | 中文 / English 双语界面 |

## 🚀 快速开始

### 安装

```bash
# 从源码运行
pip install -e .

# 或直接启动
codex-cool
```

### macOS 桌面端打包

```bash
pyinstaller codex-cool.spec
```

打包产物在 `dist/Codex Cool.app`。

### 首次使用

1. 启动后打开浏览器访问 `http://127.0.0.1:18080`
2. 点击「添加供应商」，选择预设模板或手动配置：
   - **名称**：自定义标识（如 `deepseek`）
   - **Base URL**：API 地址（如 `https://api.deepseek.com/v1`）
   - **API Key**：支持明文或 `env:VAR_NAME` 环境变量引用
   - **API 格式**：`chat`（OpenAI）/ `responses`（OpenAI）/ `anthropic`
   - **模型列表**：每行一个，支持别名映射 `alias=real_model_id`
3. 点击「注入代理」即可使用

## 📡 支持的接入方式

### Codex App（GUI）

仪表盘点击「注入代理」→ 选择模型 → 启动 Codex App 即可。

也可手动编辑 `~/.codex/config.toml`：

```toml
model = "deepseek-chat"
model_provider = "codex-cool"

[model_providers."codex-cool"]
name = "Codex-Cool"
base_url = "http://127.0.0.1:18080/v1"
wire_api = "responses"
```

### Codex CLI

同上配置 `~/.codex/config.toml` 后直接使用 `codex` 命令。

### Claude App

仪表盘点击「Claude App 代理注入」→ 选择模型（可多选）→ 重启 Claude App。

注入过程自动完成：
- 切换到第三方推理模式（3P）
- 开启 Developer Mode
- 配置推理网关地址和 API Key
- 设置 `NODE_ENV=production`（macOS）

### Claude Code

```bash
# 方式一：环境变量
export ANTHROPIC_BASE_URL=http://127.0.0.1:18080
claude

# 方式二：写入 settings.json
echo '{"apiBaseUrl": "http://127.0.0.1:18080"}' > ~/.claude/settings.json
```

### 通用 API 代理

任何兼容 OpenAI/Anthropic 的客户端均可连接：

```
Base URL: http://127.0.0.1:18080/v1
```

## 🔌 内置供应商模板

点击「添加供应商」时可选择以下预设：

| 名称 | Base URL | 格式 | 默认模型 |
|------|----------|------|----------|
| DeepSeek | `api.deepseek.com/v1` | chat | deepseek-chat, deepseek-reasoner |
| OpenAI | `api.openai.com/v1` | chat | gpt-4o, gpt-4o-mini, o1, o3-mini |
| Anthropic | `api.anthropic.com/v1` | anthropic | claude-sonnet-4, claude-3-5-haiku |
| Gemini | `generativelanguage.googleapis.com/v1beta/openai` | chat | gemini-2.5-pro/flash, gemini-2.0-flash |
| Kimi | `api.moonshot.cn/v1` | chat | moonshot-v1-8k/32k/128k |
| 智谱 | `open.bigmodel.cn/api/paas/v4` | chat | glm-4-plus/flash/long |
| 千问 | `dashscope.aliyun.com/compatible-mode/v1` | chat | qwen-turbo/plus/max |
| 豆包 | `ark.cn-beijing.volces.com/api/v3` | chat | （需手动填写） |

## 🏗️ 架构设计

```
┌─────────────┐     ┌──────────────┐     ┌──────────────────┐
│  Codex App  │     │  Claude App  │     │  第三方客户端      │
│ (Responses) │     │ (Anthropic)  │     │ (Chat/Responses) │
└──────┬──────┘     └──────┬───────┘     └────────┬─────────┘
       │                   │                      │
       └───────────┬───────┘──────────────────────┘
                   ▼
           ┌───────────────┐
           │   Codex Cool  │  ← 协议转换层
           │  Proxy Server  │
           └───────┬───────┘
                   │
       ┌───────────┼───────────┬───────────┐
       ▼           ▼           ▼           ▼
   ┌───────┐  ┌───────┐  ┌─────────┐  ┌─────────┐
   │DeepSeek│  │ OpenAI│  │Anthropic│  │ Gemini  │
   │(chat) │  │(chat) │  │(anthropic│  │ (chat)  │
   └───────┘  └───────┘  └─────────┘  └─────────┘
```

### 协议转换矩阵

| 客户端请求格式 | 上游 Provider 格式 | 转换器 |
|---------------|-------------------|--------|
| Responses → Chat | [responses_chat.py](src/codex_cool/converters/responses_chat.py) |
| Responses → Anthropic | [main.py](src/codex_cool/main.py) `_responses_body_to_anthropic_body()` |
| Chat → Responses | [responses_chat.py](src/codex_cool/converters/responses_chat.py) |
| Chat → Anthropic | [anthropic_chat.py](src/codex_cool/converters/anthropic_chat.py) |
| Anthropic → Responses | [anthropic_chat.py](src/codex_cool/converters/anthropic_chat.py) |
| Anthropic → Chat | [anthropic_chat.py](src/codex_cool/converters/anthropic_chat.py) |

### 关键特性说明

#### 检查点（Checkpoint）机制

Codex 的 `previous_response_id` 链式调用通过内存中的 Response Store 实现：

- 最大缓存 **200 条** response
- 自动合并历史 input 到当前请求（避免上下文丢失）
- 检测已有历史的 input，防止重复叠加导致 token 爆炸

#### 多模态内容处理

对于不支持多模态的 provider（DeepSeek、Kimi、智谱、千问、豆包），自动将消息中的图片/文件转换为占位符：

- `input_image` / `image_url` → `[image]`
- `input_file` / `file` → `[file]`

首次选择此类模型时会弹出提醒，后续不再重复提示。

#### Claude 模型别名映射

Claude App 注入时自动创建模型别名映射，将 Claude 官方模型名映射到你选择的实际模型：

```
claude-opus-4-20250514    → [最强模型]
claude-sonnet-4-20250514  → [均衡模型]
claude-haiku-4-5-20251001 → [轻量模型]
```

这样在 Claude App 中选择不同模型时，会路由到对应能力的替代模型。

## ⚙️ 配置说明

配置文件路径：`~/.codex-cool/config.yaml`

```yaml
host: 127.0.0.1          # 监听地址
port: 18080               # 监听端口
log_level: INFO           # 日志级别: DEBUG/INFO/WARNING/ERROR
default_provider: deepseek # 默认供应商
cors_origins: ["*"]       # CORS 允许来源

providers:
  - name: deepseek
    base_url: https://api.deepseek.com/v1
    api_key: sk-xxx              # 或 env:DEEPSEEK_API_KEY
    api_format: chat             # chat | responses | anthropic
    models:
      deepseek-chat: deepseek-chat
      claude-sonnet-4-20250514: deepseek-chat  # 别名映射
    enabled: true
    priority: 0                  # 优先级（数字越小越优先）
    timeout: 120.0               # 请求超时秒数
    max_retries: 3               # 最大重试次数
    extra_headers: {}            # 额外请求头
    extra_params: {}             # 额外请求参数
```

### API Key 环境变量引用

支持 `env:VAR_NAME` 格式引用环境变量，避免密钥明文写入配置文件：

```yaml
api_key: env:DEEPSEEK_API_KEY
api_key: env:ANTHROPIC_API_KEY
```

## 📋 API 端点

### 代理端点（LLM 转发）

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/v1/responses` | OpenAI Responses API |
| POST | `/v1/chat/completions` | OpenAI Chat Completions API |
| POST | `/v1/messages` | Anthropic Messages API |
| GET | `/v1/models` | 模型列表（自动识别客户端类型） |

### 管理 API（前缀 `/api`）

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/status` | 服务状态、运行时间、供应商列表 |
| GET | `/api/providers` | 供应商列表 |
| POST | `/api/providers` | 添加供应商 |
| PUT | `/api/providers/{name}` | 更新供应商 |
| DELETE | `/api/providers/{name}` | 删除供应商 |
| POST | `/api/providers/{name}/test` | 测试供应商连接 |
| POST | `/api/providers/{name}/models` | 获取供应商可用模型 |
| GET | `/api/config` | 获取全局配置 |
| PUT | `/api/config` | 更新全局配置 |
| POST | `/api/fetch-models` | 通过 URL 获取远程模型列表 |
| GET | `/api/templates` | 获取内置供应商模板 |
| POST | `/api/providers/from-template` | 从模板创建供应商 |
| GET | `/api/inject/status` | Codex 注入状态 |
| POST | `/api/inject` | 注入 Codex 代理 |
| POST | `/api/uninject` | 恢复 Codex 原始配置 |
| GET | `/api/claude/inject/status` | Claude 注入状态 |
| POST | `/api/claude/inject` | 注入 Claude 代理 |
| POST | `/api/claude/uninject` | 恢复 Claude 原始配置 |
| POST | `/api/reset-circuit-breaker/{name}` | 重置熔断器 |

### 系统

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/health` | 健康检查 |
| GET | `/` | WebUI 管理面板 |

## 🛠️ 开发

### 项目结构

```
codex-cool/
├── src/codex_cool/
│   ├── main.py                 # FastAPI 主入口、协议转发核心逻辑
│   ├── api.py                  # 管理 API 路由（供应商/配置/注入）
│   ├── config.py               # 配置模型（ProxyConfig/ProviderConfig）
│   ├── injector.py             # Codex/Claude 注入器（配置文件读写）
│   ├── cli.py                  # 命令行入口
│   ├── desktop.py              # 桌面应用（pywebview）
│   ├── proxy/
│   │   └── router.py           # 代理路由、Provider 解析、熔断器
│   ├── converters/
│   │   ├── responses_chat.py   # Responses ↔ Chat 格式转换
│   │   ├── anthropic_chat.py   # Anthropic ↔ Chat 格式转换
│   │   └── stream.py           # SSE 流式响应转换工具
│   ├── models/
│   │   ├── responses.py        # Responses API 请求/响应模型
│   ├── chat.py                # Chat API 请求/响应模型
│   │   └── anthropic.py        # Anthropic API 请求/响应模型
│   └── frontend/
│       ├── index.html          # WebUI 页面
│       ├── app.js              # 前端逻辑 + i18n
│       └── styles.css          # 样式
├── codex-cool.spec             # PyInstaller 打包配置
├── pyproject.toml              # 项目元信息
└── README.md
```

### 本地开发

```bash
# 克隆项目
cd codex-cool

# 创建虚拟环境
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate

# 安装依赖
pip install -e .

# 启动服务
codex-cool

# 浏览器打开 http://127.0.0.1:18080
```

### 依赖

- Python >= 3.12
- FastAPI + Uvicorn（Web 框架）
- httpx（异步 HTTP 客户端）
- PyYAML（配置解析）
- pywebview（桌面应用 GUI）
- Click（CLI）
- Rich（终端美化）

## 📝 License

MIT
