# LarkCUA-TestAgent 项目方案（Codex 实施版）

> 目标：在 Windows 平台上实现一个面向飞书桌面客户端的 CUA-Lark 智能测试 Agent。系统通过自然语言描述测试用例，自动规划步骤、操作飞书 GUI、验证执行状态，并生成可视化测试报告。  
> 架构选择：采用推荐方案，即 **Agent Planner → Skill Layer → Tool Abstraction Layer → Provider Layer**。  
> 核心原则：Agent 只通过 Skill / Tool Schema 调用能力，不直接依赖 pyautogui、pywinauto、OCR、VLM 或飞书 API 的具体实现。

---

## 1. 项目背景

比赛要求设计一个完整的 CUA 测试框架，用于自动测试飞书桌面客户端，覆盖以下能力：

1. 屏幕截图采集、UI 元素识别与定位。
2. 自然语言测试用例解析与步骤规划。
3. 模拟鼠标、键盘等 GUI 操作。
4. 执行后状态验证。
5. 生成测试报告。
6. 至少覆盖飞书两个子产品，例如 IM、Docs、Calendar、Base、VC、Mail。

本项目优先覆盖：

- **IM 即时通讯**
- **Docs 云文档**

Calendar 可作为第二阶段扩展。

---

## 2. 技术选型

### 2.1 运行平台

- Windows 10 / Windows 11
- Python 3.11+
- 飞书桌面客户端
- Node.js LTS，可选，用于飞书 OpenAPI MCP / Lark CLI

### 2.2 核心技术栈

| 模块 | 技术 | 说明 |
|---|---|---|
| 主语言 | Python | 单体项目，降低实现复杂度 |
| GUI 控制 | pywinauto + PyAutoGUI | pywinauto 负责 Windows UIA/窗口控件，PyAutoGUI 负责鼠标键盘、截图、兜底坐标操作 |
| OCR | PaddleOCR，备选 EasyOCR | 中文 GUI 文本识别 |
| VLM | GPT-4o / Qwen-VL / Claude，可选 | 用于复杂界面语义判断，不作为第一优先执行路径 |
| Agent Planner | OpenAI / Qwen / DeepSeek API | 只输出 JSON 计划，不直接生成 GUI 坐标代码 |
| 飞书集成 | OpenAPI MCP / Lark CLI / Feishu OpenAPI | 用于测试数据准备、状态校验、环境清理 |
| 配置 | YAML | 测试用例、环境变量、工具开关 |
| 日志 | JSONL + loguru | 便于生成报告和失败复盘 |
| 报告 | Markdown + HTML | 简单、稳定、适合参赛展示 |
| 数据存储 | 本地文件 + 可选 SQLite | MVP 阶段不引入复杂数据库 |

---

## 3. 总体架构

```text
Natural Language Test Case
        │
        ▼
┌──────────────────────────────────────────────┐
│ Agent Planner                                │
│ - 测试意图识别                               │
│ - 步骤规划                                   │
│ - Skill / Tool 调用编排                      │
└──────────────────────┬───────────────────────┘
                       ▼
┌──────────────────────────────────────────────┐
│ Skill Layer                                  │
│ - IM Skill                                   │
│ - Docs Skill                                 │
│ - Calendar Skill                             │
│ - Common App Skill                           │
└──────────────────────┬───────────────────────┘
                       ▼
┌──────────────────────────────────────────────┐
│ Tool Abstraction Layer                       │
│ - GUI Tools                                  │
│ - Screen / Vision Tools                      │
│ - OCR Tools                                  │
│ - VLM Semantic Tools                         │
│ - Feishu API / MCP Tools                     │
│ - Verification Tools                         │
└──────────────────────┬───────────────────────┘
                       ▼
┌──────────────────────────────────────────────┐
│ Provider Layer                               │
│ - PyAutoGUIProvider                          │
│ - PywinautoProvider                          │
│ - PaddleOCRProvider                          │
│ - VLMProvider                                │
│ - FeishuMCPProvider                          │
│ - FeishuOpenAPIProvider                      │
└──────────────────────────────────────────────┘
```

---

## 4. 架构原则

### 4.1 Agent 不直接操作鼠标和键盘

禁止让 Agent 直接输出：

```python
pyautogui.click(521, 812)
pyautogui.write("Hello World")
```

Agent 只能输出结构化计划：

```json
{
  "goal": "在 IM 中发送消息并验证",
  "steps": [
    {
      "type": "skill",
      "name": "im.send_message",
      "params": {
        "chat_name": "测试群",
        "message": "Hello World"
      }
    }
  ]
}
```

### 4.2 Skill 封装业务语义

Skill 是飞书业务动作，例如：

- `im.search_chat`
- `im.send_message`
- `docs.create_document`
- `docs.input_title`
- `calendar.create_event`

Skill 内部可以调用多个 Tool。

### 4.3 Tool 封装原子能力

Tool 是标准能力接口，例如：

- `gui.click`
- `gui.type_text`
- `screen.screenshot`
- `vision.ocr_extract`
- `vlm.judge_state`
- `feishu.docs.query`
- `verify.text_visible`

### 4.4 Provider 封装具体实现

Provider 是具体库或服务的适配层，例如：

- `PyAutoGUIProvider`
- `PywinautoProvider`
- `PaddleOCRProvider`
- `OpenAIVLMProvider`
- `FeishuMCPProvider`

替换 OCR、VLM、GUI 执行器时，只修改 Provider，不修改 Agent Planner 和 Skill。

---

## 5. Tool Abstraction Layer 设计

### 5.1 ToolSpec

```python
from typing import Any
from pydantic import BaseModel, Field


class ToolSpec(BaseModel):
    name: str
    description: str
    input_schema: dict[str, Any]
    output_schema: dict[str, Any]
    timeout: int = 30
    retryable: bool = True
    side_effect: bool = False
```

### 5.2 ToolResult

```python
from typing import Any
from pydantic import BaseModel


class ToolResult(BaseModel):
    success: bool
    data: dict[str, Any] = {}
    error: str | None = None
    evidence: list[str] = []
    confidence: float | None = None
```

### 5.3 BaseTool

```python
from abc import ABC, abstractmethod


class BaseTool(ABC):
    spec: ToolSpec

    @abstractmethod
    def execute(self, params: dict, context: "RunContext") -> ToolResult:
        pass
```

### 5.4 ToolRegistry

```python
class ToolRegistry:
    def __init__(self):
        self._tools: dict[str, BaseTool] = {}

    def register(self, tool: BaseTool) -> None:
        self._tools[tool.spec.name] = tool

    def get(self, name: str) -> BaseTool:
        if name not in self._tools:
            raise KeyError(f"Tool not found: {name}")
        return self._tools[name]

    def list_specs(self) -> list[ToolSpec]:
        return [tool.spec for tool in self._tools.values()]
```

---

## 6. 推荐第一批 Tool

MVP 阶段不要定义太多 Tool。优先实现以下工具。

### 6.1 GUI Tools

| Tool 名称 | 说明 |
|---|---|
| `gui.focus_window` | 聚焦飞书窗口 |
| `gui.click` | 点击坐标、文本或图像目标 |
| `gui.type_text` | 输入文本 |
| `gui.hotkey` | 组合快捷键 |
| `gui.scroll` | 页面滚动 |
| `gui.wait` | 等待固定时间或条件 |

### 6.2 Screen / Vision Tools

| Tool 名称 | 说明 |
|---|---|
| `screen.screenshot` | 当前屏幕截图 |
| `vision.locate_text` | OCR 定位文本 |
| `vision.ocr_extract` | 提取截图中文字 |
| `vision.locate_image` | 图像模板匹配，可选 |

### 6.3 VLM Semantic Tools

| Tool 名称 | 说明 |
|---|---|
| `vlm.judge_state` | 根据截图判断状态是否满足预期 |
| `vlm.find_element` | 根据自然语言描述找界面元素，可选 |

### 6.4 Verification Tools

| Tool 名称 | 说明 |
|---|---|
| `verify.text_visible` | 判断界面是否可见某段文本 |
| `verify.message_sent` | 判断 IM 消息是否发送成功 |
| `verify.document_created` | 判断文档是否创建成功 |

### 6.5 Feishu API / MCP Tools

| Tool 名称 | 说明 |
|---|---|
| `feishu.im.query_message` | 查询消息是否存在，用于校验 |
| `feishu.docs.query_document` | 查询文档是否存在 |
| `feishu.docs.read_document` | 读取文档内容 |
| `feishu.cleanup_test_data` | 清理测试数据，可选 |

注意：飞书 API / MCP 主要用于验证、准备数据、清理数据，不应替代 GUI 操作主路径。

---

## 7. Skill Layer 设计

### 7.1 SkillResult

```python
from pydantic import BaseModel


class SkillResult(BaseModel):
    success: bool
    data: dict = {}
    error: str | None = None
    evidence: list[str] = []
```

### 7.2 BaseSkill

```python
from abc import ABC, abstractmethod


class BaseSkill(ABC):
    name: str
    description: str
    input_schema: dict

    @abstractmethod
    def execute(self, params: dict, context: "RunContext") -> SkillResult:
        pass
```

### 7.3 IM Skill

优先实现：

- `im.search_chat`
- `im.send_text`
- `im.verify_message`
- `im.send_message`

`im.send_message` 是组合 Skill：

```text
im.send_message
  ├─ app.open_or_focus
  ├─ im.search_chat
  ├─ im.send_text
  └─ im.verify_message
```

### 7.4 Docs Skill

优先实现：

- `docs.open_home`
- `docs.create_document`
- `docs.input_title`
- `docs.input_body`
- `docs.verify_document`

### 7.5 Calendar Skill，第二阶段

- `calendar.open`
- `calendar.create_event`
- `calendar.modify_event`
- `calendar.verify_event`

---

## 8. Agent Planner 设计

### 8.1 输入

```text
在 IM 中搜索“测试群”，发送一条消息“Hello World”，并确认发送成功。
```

### 8.2 输出

Planner 必须输出严格 JSON：

```json
{
  "case_id": "im_send_message_001",
  "goal": "在 IM 中搜索测试群并发送消息",
  "steps": [
    {
      "id": "s1",
      "type": "skill",
      "name": "im.send_message",
      "params": {
        "chat_name": "测试群",
        "message": "Hello World"
      },
      "expect": {
        "type": "message_visible",
        "text": "Hello World"
      }
    }
  ]
}
```

### 8.3 Planner 约束

- 只能调用注册过的 Skill 或 Tool。
- 优先调用 Skill，不要直接调用原子 GUI Tool。
- 禁止输出 Python 代码。
- 禁止输出屏幕绝对坐标，除非作为 fallback 并由 Tool 层确认。
- 所有输出必须通过 Pydantic Schema 校验。

---

## 9. 测试用例格式

使用 YAML。

### 9.1 IM 测试用例

```yaml
id: im_send_message_001
name: IM 发送文本消息
product: im
instruction: 在 IM 中搜索“测试群”，发送一条消息“Hello World from CUA Agent”，并确认发送成功。

params:
  chat_name: 测试群
  message: Hello World from CUA Agent

expected:
  type: message_visible
  text: Hello World from CUA Agent

verification:
  - ocr
  - screenshot
  - vlm
```

### 9.2 Docs 测试用例

```yaml
id: docs_create_document_001
name: 创建项目周报文档
product: docs
instruction: 在飞书中创建一个名为“项目周报”的新文档，并输入标题“2026年Q2项目进展”。

params:
  doc_name: 项目周报
  title: 2026年Q2项目进展
  body: 本文档由 LarkCUA-TestAgent 自动创建。

expected:
  type: document_content_visible
  text:
    - 项目周报
    - 2026年Q2项目进展

verification:
  - ocr
  - screenshot
  - vlm
  - feishu_api
```

---

## 10. 状态验证策略

### 10.1 多源验证

不要只依赖单一截图或单一 API。

推荐验证方式：

```text
GUI Screenshot
  + OCR Text Check
  + VLM Semantic Judge
  + Feishu API / MCP Business Oracle
```

### 10.2 判定规则

每个验证工具返回：

```json
{
  "success": true,
  "confidence": 0.91,
  "evidence": [
    "artifacts/screenshots/step_004_after.png",
    "ocr: Hello World from CUA Agent"
  ]
}
```

最终判定建议：

- OCR 和 VLM 同时通过：通过。
- OCR 通过、API 通过：通过。
- VLM 通过但 OCR/API 不通过：标记为不确定，需要重试一次。
- 所有验证失败：失败。

### 10.3 IM 消息验证

```text
1. 截图当前聊天窗口。
2. OCR 提取文本。
3. 判断目标消息是否出现。
4. 可选：VLM 判断最后一条消息是否为目标文本。
5. 可选：飞书 API / MCP 查询消息记录。
```

### 10.4 Docs 文档验证

```text
1. 截图当前文档页面。
2. OCR 判断标题和正文是否可见。
3. 可选：VLM 判断是否处于目标文档页面。
4. 可选：飞书 API / MCP 查询文档标题和内容。
```

---

## 11. 失败恢复机制

每个 Step 执行流程：

```text
before screenshot
  ↓
execute skill/tool
  ↓
after screenshot
  ↓
verify
  ↓
if failed: retry or recover
  ↓
write step log
```

### 11.1 通用恢复动作

| 失败类型 | 恢复策略 |
|---|---|
| 飞书窗口未激活 | 调用 `gui.focus_window` |
| 找不到搜索框 | 使用快捷键 `Ctrl + K` 或全局搜索 |
| 输入框未聚焦 | 重新点击输入区域 |
| OCR 未识别 | 扩大截图区域，重试 OCR |
| VLM 判断低置信度 | 退回 OCR / API 验证 |
| 页面状态错误 | 按 Esc / 返回主页 / 重新进入流程 |

### 11.2 Retry 规则

- 默认重试 2 次。
- GUI 点击类 Tool 可重试。
- 文本输入类 Tool 重试前要确认是否已输入，避免重复输入。
- 发送消息类 Skill 默认不自动重复发送，除非确认前一次未发送成功。

---

## 12. 报告设计

每次运行生成独立目录：

```text
artifacts/runs/2026-05-02_153000/
  result.json
  report.md
  report.html
  screenshots/
    s1_before.png
    s1_after.png
    s2_before.png
    s2_after.png
  logs/
    run.jsonl
```

### 12.1 报告内容

```markdown
# LarkCUA-TestAgent Report

## Summary

| Metric | Value |
|---|---|
| Total Cases | 2 |
| Passed | 2 |
| Failed | 0 |
| Pass Rate | 100% |

## Case: IM 发送文本消息

- Status: Passed
- Duration: 14.2s
- Verification:
  - OCR: Passed
  - VLM: Passed
  - API: Skipped

## Evidence

- Before Screenshot: screenshots/s1_before.png
- After Screenshot: screenshots/s1_after.png
- OCR Text: Hello World from CUA Agent
```

---

## 13. 推荐项目目录结构

```text
lark-cua-test-agent/
  README.md
  requirements.txt
  config.example.yaml
  main.py

  agent/
    __init__.py
    planner.py
    schemas.py

  runtime/
    __init__.py
    context.py
    runner.py
    logger.py

  skills/
    __init__.py
    base.py
    app.py
    im.py
    docs.py
    calendar.py

  tools/
    __init__.py
    base.py
    registry.py
    schema.py

    gui/
      __init__.py
      focus_window.py
      click.py
      type_text.py
      hotkey.py
      scroll.py
      wait.py

    vision/
      __init__.py
      screenshot.py
      ocr_extract.py
      locate_text.py
      locate_image.py

    semantic/
      __init__.py
      vlm_judge_state.py

    feishu/
      __init__.py
      mcp_client.py
      openapi_client.py
      query_message.py
      query_document.py

    verify/
      __init__.py
      text_visible.py
      message_sent.py
      document_created.py

  providers/
    __init__.py
    pyautogui_provider.py
    pywinauto_provider.py
    paddleocr_provider.py
    vlm_provider.py
    feishu_mcp_provider.py
    feishu_openapi_provider.py

  reports/
    __init__.py
    generator.py
    templates/
      report.md.j2
      report.html.j2

  testcases/
    im_send_message.yaml
    docs_create_document.yaml

  artifacts/
    screenshots/
    runs/
```

---

## 14. Codex 实施任务拆分

### Task 1：创建项目骨架

创建上述目录结构，并补充：

- `README.md`
- `requirements.txt`
- `config.example.yaml`
- `main.py`

验收标准：

- `python main.py --help` 可以运行。
- 项目结构清晰。
- 无循环导入。

---

### Task 2：实现基础 Schema

实现：

- `ToolSpec`
- `ToolResult`
- `BaseTool`
- `ToolRegistry`
- `SkillResult`
- `BaseSkill`
- `RunContext`
- `StepLog`
- `CaseResult`

验收标准：

- 所有 Schema 使用 Pydantic。
- Tool 和 Skill 执行结果格式统一。
- 单元测试覆盖基本序列化。

---

### Task 3：实现 GUI Provider

实现：

- `PyAutoGUIProvider`
- `PywinautoProvider`

最低能力：

- 聚焦飞书窗口。
- 截图。
- 点击。
- 输入文本。
- 快捷键。
- 滚动。

验收标准：

- 可以聚焦飞书桌面客户端。
- 可以保存当前屏幕截图到指定路径。
- 可以输入一段中文文本。

---

### Task 4：实现 GUI Tools

实现：

- `gui.focus_window`
- `gui.click`
- `gui.type_text`
- `gui.hotkey`
- `gui.scroll`
- `gui.wait`
- `screen.screenshot`

验收标准：

- 所有 Tool 均可注册到 `ToolRegistry`。
- 所有 Tool 返回 `ToolResult`。
- 失败时返回结构化错误，不直接抛出未处理异常。

---

### Task 5：实现 OCR Provider 和 Vision Tools

实现：

- `PaddleOCRProvider`
- `vision.ocr_extract`
- `vision.locate_text`
- `verify.text_visible`

验收标准：

- 对截图执行 OCR。
- 能判断指定文本是否出现在截图中。
- OCR 结果写入 ToolResult evidence。

---

### Task 6：实现 IM Skill

实现：

- `app.open_or_focus`
- `im.search_chat`
- `im.send_text`
- `im.verify_message`
- `im.send_message`

推荐执行路径：

```text
focus Feishu
  → Ctrl + K 或点击搜索框
  → 输入群名
  → Enter
  → 输入消息
  → Enter
  → 截图
  → OCR / VLM 验证
```

验收标准：

- 能在目标测试群发送消息。
- 能通过 OCR 或 VLM 判断消息出现。
- 生成 step log 和截图证据。

---

### Task 7：实现 Docs Skill

实现：

- `docs.open_home`
- `docs.create_document`
- `docs.input_title`
- `docs.input_body`
- `docs.verify_document`

推荐执行路径：

```text
focus Feishu
  → 打开云文档入口
  → 新建文档
  → 输入标题
  → 输入正文
  → 截图
  → OCR / VLM 验证
```

验收标准：

- 能创建一个文档。
- 能输入标题和正文。
- 能验证目标文本可见。

---

### Task 8：实现 Planner

实现简单 Planner：

- MVP 阶段可以先使用规则解析。
- 后续再接 LLM。

规则示例：

```text
如果 instruction 包含 "IM" 和 "发送"：
  生成 im.send_message

如果 instruction 包含 "文档" 和 "创建"：
  生成 docs.create_document
```

验收标准：

- 输入测试用例 YAML 后能生成标准 Plan JSON。
- Plan 只调用已注册 Skill。
- Plan 可被 Runner 执行。

---

### Task 9：实现 Runner

Runner 负责：

- 加载测试用例。
- 调用 Planner。
- 顺序执行步骤。
- 记录截图、日志、ToolResult、SkillResult。
- 执行失败恢复和重试。
- 汇总 CaseResult。

验收标准：

- 能执行单个 YAML 测试用例。
- 能执行多个测试用例。
- 每一步都有 before/after 截图。
- 每一步都有 JSONL 日志。

---

### Task 10：实现报告生成

实现：

- `report.md`
- `report.html`
- `result.json`

验收标准：

- 报告包含 summary、case 列表、step 列表、截图证据、OCR/VLM 证据、失败原因。
- HTML 可本地打开。
- Markdown 可直接提交比赛材料。

---

### Task 11：接入 VLM，可选增强

实现：

- `VLMProvider`
- `vlm.judge_state`
- `vlm.find_element`

验收标准：

- 输入截图和 expectation。
- 返回 JSON：
  ```json
  {
    "success": true,
    "evidence": "截图中可见目标消息",
    "confidence": 0.92
  }
  ```

---

### Task 12：接入 Feishu MCP / OpenAPI，可选增强

实现：

- `FeishuMCPProvider`
- `FeishuOpenAPIProvider`
- `feishu.im.query_message`
- `feishu.docs.query_document`
- `feishu.docs.read_document`

验收标准：

- 可配置是否启用 MCP / OpenAPI。
- API 只用于测试准备、状态校验、环境清理。
- API 不替代 GUI 主路径。

---

## 15. MVP 验收标准

MVP 必须做到：

1. Windows 上可运行。
2. 可以读取 YAML 测试用例。
3. 可以执行 IM 发送消息用例。
4. 可以执行 Docs 创建文档用例。
5. 每个步骤保存截图。
6. 至少使用 OCR 进行状态验证。
7. 生成 Markdown 报告。
8. Agent Planner 不直接输出 GUI 坐标。
9. Skill、Tool、Provider 三层边界清晰。
10. 代码结构允许未来替换 OCR/VLM/GUI Provider。

---

## 16. 非目标

MVP 阶段不要实现：

- 复杂 Web Dashboard。
- 分布式任务队列。
- 多用户权限系统。
- 远程执行 Agent。
- 完整飞书所有子产品覆盖。
- 完全依赖 VLM 的端到端坐标点击。
- Agent 动态生成 Python 并执行。

---

## 17. 风险与规避

### 17.1 飞书 Electron 界面控件无法被 UIA 完整识别

规避：

- UIA 优先。
- OCR 兜底。
- 图像模板匹配兜底。
- VLM 语义判断兜底。
- 必要时使用相对坐标，但封装在 Tool 内。

### 17.2 OCR 中文识别不稳定

规避：

- 截图时裁剪目标区域。
- 增大缩放比例。
- 失败时使用 VLM 判断。
- 结果验证采用多源判定。

### 17.3 发送消息重复执行

规避：

- `im.send_text` 默认不自动重试发送。
- 重试前先截图验证消息是否已经出现。
- 对有副作用的 Skill 标记 `side_effect=True`。

### 17.4 API / MCP 被误用为业务执行主路径

规避：

- 在文档和代码中明确：GUI 是主执行路径。
- API / MCP 只做验证、准备和清理。
- 报告中区分 GUI Evidence 和 API Evidence。

---

## 18. README 建议内容

README 应包含：

1. 项目简介。
2. 架构图。
3. 技术栈。
4. 安装步骤。
5. 配置说明。
6. 如何运行 IM Demo。
7. 如何运行 Docs Demo。
8. 测试报告示例。
9. 扩展新 Skill 的方法。
10. 扩展新 Tool / Provider 的方法。

---

## 19. requirements.txt 建议

```txt
pyautogui
pywinauto
pillow
opencv-python
pydantic
pyyaml
jinja2
loguru
rich
requests
paddleocr
paddlepaddle
```

如 PaddleOCR 安装困难，可以先临时替换为 EasyOCR：

```txt
easyocr
```

---

## 20. config.example.yaml 建议

```yaml
app:
  feishu_window_title_keywords:
    - 飞书
    - Feishu
    - Lark

runtime:
  screenshot_dir: artifacts/screenshots
  run_dir: artifacts/runs
  default_timeout_seconds: 30
  retry_times: 2

ocr:
  provider: paddleocr
  language: ch

vlm:
  enabled: false
  provider: openai
  model: gpt-4o

feishu:
  mcp_enabled: false
  openapi_enabled: false
  app_id: ${FEISHU_APP_ID}
  app_secret: ${FEISHU_APP_SECRET}

planner:
  mode: rule
  llm_enabled: false
```

---

## 21. Codex 编码约束

请 Codex 严格遵守：

1. 不要把业务逻辑写进 `main.py`。
2. 不要让 Planner 输出 Python 代码。
3. 不要让 Skill 直接 import `pyautogui` 或 `pywinauto`；Skill 必须通过 Tool 调用能力。
4. 不要让 Agent 直接调用 Provider。
5. 所有 Tool 必须返回 `ToolResult`。
6. 所有 Skill 必须返回 `SkillResult`。
7. 所有外部依赖调用必须有异常处理。
8. 所有截图、OCR、验证结果必须写入 evidence。
9. 对有副作用的操作设置 `side_effect=True`。
10. 优先实现可运行 MVP，不要过度抽象。
11. TDD
---

## 22. 推荐开发顺序

```text
1. 项目骨架
2. Schema / Registry
3. GUI Provider
4. GUI Tools
5. Screenshot + OCR
6. Verify Tools
7. IM Skill
8. Docs Skill
9. Rule-based Planner
10. Runner
11. Markdown / HTML Report
12. VLM 增强
13. Feishu MCP / OpenAPI 增强
```

---

## 23. 最终答辩表述

本项目采用可扩展的分层 CUA 测试架构。系统将自然语言测试用例解析为结构化执行计划，由 Agent Planner 调用飞书业务 Skill；Skill 不直接依赖底层实现，而是通过 Tool Abstraction Layer 调用 GUI 操作、截图、OCR、VLM 语义判断和飞书 API / MCP 校验能力；Tool 层再通过 Provider 适配 pywinauto、PyAutoGUI、PaddleOCR、VLM 模型以及飞书开放平台能力。该设计既保证了飞书桌面客户端的真实 GUI 自动化操作，又支持在不修改规划逻辑的情况下替换 OCR/VLM 模型、切换 GUI 执行器、扩展飞书子产品，并为后续多轮 Agent Tool Calling、失败自恢复和测试报告证据链提供统一基础。

---

## Progress Hook（必读）

为保证后续会话可持续迭代：每次 Codex 对仓库做出任何变更（新增/修改/删除文件、调整配置、实现功能、修复 bug、补测试），都必须同步更新 `progress.md`：

1. 更新 `Last updated` 日期
2. 在 `Change Log` 追加当日记录（关键变更点 + 影响的文件/模块）
3. 必要时更新 `Milestones` 勾选状态与 `Next` 计划
4. 若运行了命令（单测/编译等），在当日记录中注明
