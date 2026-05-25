# 酷法典


**API 代理转发服务** — 这是一个非常简单的应用，就是将deepseek v4等API接入 Codex App 和 Claude App 。 没有嵌入任何广告和推荐，轻量简单。
同类产品有些只做了codex中转，有些只做了codex中转，有些不支持deepseek接入，然后我就用claude CLI做了这个小玩意，纯本地中转很方便。
多模态、部分功能无法使用是codex和Claude的限制，和中转无关。

有macos桌面端和win桌面端（还在测试），也可以用下面的命令在终端运行。
<img width="1594" height="1656" alt="macos" src="https://github.com/user-attachments/assets/5ed557ed-275b-40b7-b27d-3753758a6cbc" />

## 🚀 快速开始

### 安装

```bash
# 从源码运行
pip install -e .

### 首次使用

1. 启动后打开浏览器访问 `http://127.0.0.1:18080`
2. 点击「添加供应商」，选择预设模板或手动配置：
   - **名称**：自定义标识（如 `deepseek`）
   - **Base URL**：API 地址（如 `https://api.deepseek.com/v1`）
   - **API Key**：支持明文或 `env:VAR_NAME` 环境变量引用
   - **API 格式**：`chat`（OpenAI）/ `responses`（OpenAI）/ `anthropic`
   - **模型列表**：每行一个，支持别名映射 `alias=real_model_id`
3. 点击「注入代理」即可使用

## 📡桌面端接入方式

### Codex App

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

### Codex CLI和Claude CLI没有做，这个太简单了，直接手动改就行，软件内有文档


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
