# CUA-Lark

Computer-Use Agent for Lark/Feishu 桌面端。项目通过截图、VLM 视觉理解、飞书知识库模板和 PyAutoGUI 动作执行，让程序像真实用户一样操作飞书桌面客户端。

飞书 AI 校园竞赛 · 质量工程与智能测试赛道

## 当前能力

- **跨平台支持**：Windows（Win32 API）和 macOS（AppleScript + System Events）均可运行。
- **飞书桌面端模板优先**：常见飞书任务优先走 `knowledge/feishu.json` 模板，减少 VLM 不稳定性。
- **消息协作**：打开消息模块、搜索并打开会话、给指定会话发送消息、滚动当前消息列表。
- **日程会议**：打开日历模块、创建日程并填写标题。
- **文档知识库**：搜索并打开文档、打开最近文档。
- **视觉兜底**：模板未命中时回退到 VLM 全窗口或分区域定位。
- **执行保护**：用户空闲等待、目标应用聚焦、点击前目标确认、失败恢复。
- **中文输入**：非 ASCII 文本通过剪贴板粘贴，避免 `pyautogui.typewrite()` 中文输入问题。
- **截图优化**：大截图自动缩放至 1280px 并以 JPEG 压缩，降低 VLM 延迟。
- **VLM 进度日志**：每次请求打印 `[VLM-REQ]` / `[VLM-RSP]`，含耗时和响应长度。
- **测试闭环**：支持不调用外部模型的无模型运行测试。

## 快速开始

### 1. 安装依赖

推荐使用 `uv`：

```bash
uv sync
```

如果尚未安装 `uv`：

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
uv sync
```

### 2. 配置 API Key

复制 `.env.example` 为 `.env`：

```bash
cp .env.example .env
```

编辑 `.env`，填入对应服务的 Key：

```dotenv
DASHSCOPE_API_KEY=sk-your-api-key-here
CUA_MODEL=qwen-vl-max
CUA_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
```

**推荐模型**：`qwen-vl-max`（DashScope），GUI grounding 准确率高，响应速度快（2-5s）。

> ⚠️ **模型兼容性说明**：小米 `mimo-v2.5` 支持视觉输入但 GUI 坐标定位能力不足（`analyze_screen` 大量返回空响应），`mimo-v2.5-pro` 不支持视觉输入。这两个模型不推荐用于桌面自动化主流程。

也可以使用 provider 专用变量：

- **DashScope / Qwen**：`QWEN_API_KEY` 或 `DASHSCOPE_API_KEY`
- **小米 MiMo / MiLM**：`MIMO_API_KEY`
- **OpenAI 兼容服务**：`CUA_API_KEY` 或 `OPENAI_API_KEY`

模型和端点通过环境变量切换，不需要改源码：

```dotenv
CUA_MODEL=qwen-vl-max
CUA_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
```

`config.py` 会根据 `CUA_BASE_URL` 自动选择对应的 API Key。项目主链路使用 OpenAI SDK 的兼容调用方式，任何 OpenAI-compatible 端点均可直接接入。

> **注意**：如果 shell 中已有 `CUA_MODEL` / `CUA_BASE_URL` 环境变量，会覆盖 `.env` 文件。切换模型后请执行 `unset CUA_MODEL CUA_BASE_URL` 确保 `.env` 生效。

### 3. 运行

```bash
uv run python main.py -i "打开消息模块"
uv run python main.py -i "搜索并打开会话 测试群"
uv run python main.py -i "给 测试群 发送消息 ：这是一条自动化测试消息"
uv run python main.py -i "创建日程 项目同步会 时间 明天10点"
uv run python main.py -i "打开文档 项目计划"
uv run python main.py --interactive
```

如果希望每条命令等待一段时间后再真正执行，可以加 `--delay-seconds`：

```bash
uv run python main.py -i "打开消息模块" --delay-seconds 3
uv run python main.py --interactive --delay-seconds 2
uv run python main.py -t tests/m1_single_actions.json --delay-seconds 1.5
```

## 飞书专用指令示例

| 场景 | 示例指令 | 当前路径 |
|------|----------|----------|
| 打开消息 | `打开消息模块` | 知识库模板 |
| 打开日历 | `打开日历模块` | 知识库模板 |
| 搜索输入 | `在搜索框中输入 测试群 并停留1秒` | 知识库模板 |
| 打开会话 | `搜索并打开会话 测试群` | 知识库模板 |
| 发送消息 | `给 测试群 发送消息 ：上线完成` | 知识库模板 |
| 创建日程 | `创建日程 项目同步会 时间 明天10点` | 知识库模板 |
| 打开文档 | `打开文档 项目计划` | 知识库模板 |
| 最近文档 | `打开最近文档` | 知识库模板 |
| 消息滚动 | `在当前消息列表向下滚动` | 知识库模板 |

## 整体架构

```text
用户指令
  ↓
Orchestrator 编排
  ↓
目标应用聚焦 + 截图 + 前台窗口裁剪
  ↓
页面状态识别
  ↓
知识库模板匹配 ── 未命中 → VLM 视觉定位
  ↓
Action / ActionChunk 解析
  ↓
PyAutoGUI 执行
  ↓
截图验证 + 失败恢复 + JSONL 记录
```

## 目录结构

```text
Feishu_CUA/
├── main.py
├── pyproject.toml
├── uv.lock
├── knowledge/
│   └── feishu.json
├── tests/
│   ├── m1_single_actions.json
│   ├── test_parser.py
│   ├── test_knowledge_and_screenshot.py
│   ├── test_recovery.py
│   └── test_runtime_no_model.py
├── scripts/
│   ├── run_mimo_direct.ps1
│   └── test_mimo_text.py
└── cua_lark/
    ├── config.py
    ├── orchestrator.py
    ├── knowledge_base.py
    ├── recorder.py
    ├── perception/
    ├── execution/
    └── verification/
```

## 核心模块

| 模块 | 文件 | 作用 |
|------|------|------|
| 编排 | `cua_lark/orchestrator.py` | 主流程、模板匹配、VLM fallback、执行和验证 |
| 知识库 | `knowledge/feishu.json` | 飞书状态、快捷键、区域偏好、任务模板 |
| 配置 | `cua_lark/config.py` | 模型、端点、API Key、截图和恢复参数 |
| VLM | `cua_lark/perception/vlm_client.py` | 视觉分析、验证、页面状态分类、点击确认 |
| 截图 | `cua_lark/perception/screenshot.py` | 截图、前台窗口裁剪、截图会话清理 |
| 执行 | `cua_lark/execution/operator.py` | 鼠标、键盘、滚动、中文粘贴 |
| 解析 | `cua_lark/execution/parser.py` | VLM JSON 到 Action / ActionChunk |
| 恢复 | `cua_lark/execution/recovery.py` | 聚焦飞书、恢复到稳定模块 |
| 记录 | `cua_lark/recorder.py` | 记录 trace JSONL |

## 如何测试

建议按“从不依赖外部环境到真实飞书环境”的顺序测试。

### 第 1 层：配置文件和语法测试

不调用模型，不操作桌面，用于确认 JSON、TOML 和 Python 语法没问题：

```bash
.venv/bin/python -m json.tool knowledge/feishu.json >/dev/null
.venv/bin/python -m json.tool tests/m1_single_actions.json >/dev/null
.venv/bin/python -m py_compile \
  cua_lark/orchestrator.py \
  cua_lark/execution/parser.py \
  cua_lark/execution/input_guard.py \
  cua_lark/execution/window_manager.py \
  cua_lark/perception/vlm_client.py \
  tests/test_knowledge_and_screenshot.py \
  tests/test_runtime_no_model.py
```

预期：无报错。

### 第 2 层：单元测试

不调用真实 VLM，不操作真实飞书，验证解析器、知识库、截图工具和恢复链路：

```bash
.venv/bin/python -m unittest \
  tests.test_parser \
  tests.test_knowledge_and_screenshot \
  tests.test_recovery
```

当前预期：

```text
Ran 15 tests
OK
```

### 第 3 层：无模型运行闭环

不调用外部模型，不操作真实飞书，通过 mock 验证主流程和模板路径：

```bash
.venv/bin/python tests/test_runtime_no_model.py
```

当前预期：

```text
NO_MODEL_RUNTIME_TEST: PASS
```

这一层会验证首批飞书专用模板是否跳过 VLM，包括：

- `搜索并打开会话 测试群`
- `给 测试群 发送消息 ：上线完成 并停留1秒`
- `创建日程 项目同步会 时间 明天10点`
- `打开文档 项目计划 然后等待`
- `在当前消息列表向下滚动`
- `打开最近文档`

### 第 4 层：真实 VLM 连通性测试

用于确认 `.env`、API Key、模型端点可用：

```bash
uv run python main.py -i "打开消息模块"
```

如果这一步失败，优先检查：

- `.env` 中的 API Key 是否正确
- `CUA_MODEL` 是否支持视觉输入
- `CUA_BASE_URL` 是否是 OpenAI-compatible endpoint
- 当前网络/代理是否能访问对应服务

### 第 5 层：真实飞书桌面端测试

支持 Windows 和 macOS。测试前请确认：

- 飞书桌面端已登录且窗口可见（不要最小化）
- macOS 用户已授权终端的「屏幕录制」和「辅助功能」权限
- 使用测试群、测试联系人、测试文档
- 不要在执行期间移动鼠标或键盘输入
- 已执行 `unset CUA_MODEL CUA_BASE_URL` 确保 `.env` 配置生效

推荐逐条运行：

```bash
uv run python main.py -i "打开消息模块"
uv run python main.py -i "搜索并打开会话 测试群"
uv run python main.py -i "给 测试群 发送消息 ：这是一条自动化测试消息"
uv run python main.py -i "打开日历模块"
uv run python main.py -i "创建日程 项目同步会 时间 明天10点"
uv run python main.py -i "打开文档 项目计划"
uv run python main.py -i "打开最近文档"
uv run python main.py -i "在当前消息列表向下滚动"
```

也可以跑测试集：

```bash
uv run python main.py -t tests/m1_single_actions.json
```

测试集中的单条用例也可以单独设置延迟，字段名是 `delay_seconds`：

```json
{
  "instruction": "打开消息模块",
  "expected_action": "chunk",
  "delay_seconds": 3
}
```

## 日志和截图

- **执行记录**：`logs/trace.jsonl`
- **截图目录**：`logs/screenshots/<session_id>/`
- **默认策略**：成功截图可清理，失败截图保留，便于排查

## 平台说明

项目同时支持 Windows 和 macOS：

| 功能 | Windows | macOS |
|------|---------|-------|
| 窗口聚焦/激活 | Win32 API (`user32`) | AppleScript + System Events (`AXRaise`) |
| 应用启动 | `os.startfile` | `open -a` |
| 前台窗口检测 | `GetForegroundWindow` | `frontmost` process query |
| 截图 | `mss` | `mss`（需授权屏幕录制权限） |
| 键鼠操作 | PyAutoGUI | PyAutoGUI（需授权辅助功能权限） |

### macOS 权限要求

在 **系统设置 → 隐私与安全性** 中，为运行命令的终端应用（Terminal / iTerm / Windsurf 等）授权：

1. **屏幕录制** — `mss` 截图需要此权限，否则只能拍到桌面壁纸
2. **辅助功能** — PyAutoGUI 键鼠操作需要此权限

授权后需重启终端应用。

## 当前边界

- 真实任务依赖 VLM 接口连通性和视觉理解准确率。
- 飞书快捷键和 UI 布局可能因版本、语言和企业配置不同而变化。
- 发送消息、创建日程属于有副作用操作，建议只在测试群和测试账号上验证。
- 当前工作流以知识库模板为主，复杂跨模块任务仍需继续扩展。
