# 危机求生 / Story Relay 本地模拟器

这个目录包含两套可运行的版本：
- CLI 版：`simulation.py`（在终端里玩）
- Web 版：`server.py` + `static/`（浏览器里玩，FastAPI + WebSocket）

> 说明：项目支持“无 Key 的降级模式”（会使用内置 fallback 内容跑完整流程），用于验证流程/UI；配置好 DeepSeek Key 后会调用真实 LLM。

## 1) 环境要求

- Python 3.10+（推荐）
- DeepSeek API Key（可选）

获取 DeepSeek API Key：

```text
https://platform.deepseek.com/api_keys
```

## 2) 安装依赖

在本目录执行：

```powershell
python -m pip install -r requirements.txt
```

（可选，推荐）使用虚拟环境：

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

## 3) 配置 DEEPSEEK_API_KEY（推荐）
1.参数在 `config.py`（回合数、人数、模型名、base_url 等）。
只需要在这里面调整deepseek的API key就可以使用了,其他想改的话，可以自己修改。

2.为安全起见，仓库里不会默认写死 Key，也可用环境变量配置。

Windows PowerShell（只对当前终端有效）：

```powershell
$env:DEEPSEEK_API_KEY="sk-你的key"
```

Windows 持久化（新开终端生效）：

```powershell
setx DEEPSEEK_API_KEY "sk-你的key"
```

macOS/Linux：

```bash
export DEEPSEEK_API_KEY="sk-你的key"
```

## 4) 运行 CLI 版

```powershell
python simulation.py
```


## 5) 运行 Web 版（本地服务器）

方式 A（最简单；直接运行 `server.py`）：

```powershell
python server.py
```

方式 B（开发推荐；支持热重载）：

```powershell
python -m uvicorn server:app --reload --port 8000
```

然后用浏览器打开：

```text
http://127.0.0.1:8000/
```

重要：
- 不要直接双击打开 `static/index.html`（file://），必须通过后端 `http://127.0.0.1:8000/` 访问，否则 WebSocket 无法连接。

## 6) 玩法说明（Web）

- 🤖 单人模式：立即开一局（你 + 2 个 Bot）
- 👥 多人模式：进入匹配队列；如果长时间匹配不到，约 30 秒后会用 Bot 补位开局

## 7) 常见问题

- 终端提示 `'uvicorn' 不是内部或外部命令`：
  - 优先用 `python -m uvicorn ...`（不依赖 uvicorn 命令是否在 PATH）
  - 或直接用 `python server.py`
- 浏览器点“单人模式”没反应：
  - 请确认后端已启动，并且你是通过 `http://127.0.0.1:8000/` 打开的页面（不是 `static/index.html`）。
- 控制台出现 `[Warning] DEEPSEEK_API_KEY is not set`：
  - 你正在使用降级模式；配置环境变量后即可调用真实 LLM。
