# 项目状态

## 文档规则

- 每轮问答结束后更新 `docs/` 中文文档。
- 新一轮开始默认不主动读取文档，优先依赖当前对话上下文。
- 文档用于持久化项目状态、决策和实现日志。

## 当前能力

- 执行前后都有用户空闲等待，降低人工干预导致的误操作。
- 支持窗口聚焦；找不到飞书时可按知识库中的启动命令尝试启动。
- 支持页面状态识别、恢复到稳定模块、失败后有限重试。
- 截图已按会话管理，并支持按步骤精确删除与保留失败证据。
- 飞书环境知识已外置到 `knowledge/feishu.json`。
- 主流程已支持前台窗口裁剪、分区分析（但是默认是全屏截图）、二阶段定位。
- 已支持 `wait`、`mouse_move`、`drag`、`ActionChunk`。
- 已支持知识库模板优先执行、参数槽位填充、模板失败回退到 VLM。
- 已支持 VLM 全屏定位（`full_window`）和分区域定位（`region`）两种模式，默认全屏。
- 已支持点击前目标确认（`preclick_confirmation`），裁剪 80x80 补丁由 VLM 二次校验。
- 已支持中文/非 ASCII 输入：通过 `pyperclip` 剪贴板粘贴，粘贴前自动清空输入框。
- 滚动操作已支持前置光标定位（`ScrollAction.x/y`）。
- VLM 小图像保护：截图 <20px 时回退到全屏，避免 API 400 错误。
- ActionChunk 确认递归：对复合动作提取第一个 click 子动作做目标确认。
- 模板 fallback 路径同样走点击确认流程。

## 模板系统现状

- 已支持前置条件 `preconditions`：
  - `app_in_view`
  - `state_in`
  - `state_not_in`
- 已支持后置条件 `postconditions`：
  - `app_in_view`
  - `state_in`
  - `verify_instruction`
- 前置条件不满足时，模板不命中，直接走 VLM 路径。
- 后置条件失败时，主流程会先恢复，再回退到 VLM 路径，而不是直接整步失败。

## 当前验证情况

- 单元测试：
  - `tests/test_parser.py`
  - `tests/test_knowledge_and_screenshot.py`
  - `tests/test_recovery.py`
- `tests/test_runtime_no_model.py` 通过。
- `python -m unittest tests.test_parser tests.test_knowledge_and_screenshot tests.test_recovery` 通过。
- `cua_lark/config.py` `py_compile` 通过。

## 当前模型配置

- 模型保持可选，通过 `CUA_MODEL` 和 `CUA_BASE_URL` 控制。
- 当前 `.env` 选择的是：
  - `CUA_MODEL=qwen-vl-max`
  - `CUA_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1`
- 当前 `.env` 中已写入 API key。
- `cua_lark/config.py` 会自动加载 `.env`。
- 当前视觉调用层已改回阿里百炼 `OpenAI` 兼容写法，贴近官方示例。
- API Key 现在按端点自动选择：
  - DashScope / 阿里百炼：优先 `QWEN_API_KEY`，其次 `DASHSCOPE_API_KEY`
  - MiniMax / MiMo：优先 `MIMO_API_KEY`
  - 兜底才使用通用 `CUA_API_KEY`

## 当前边界

- 真实任务仍依赖外部 VLM/API 连通性。
- 当前项目模型可切换，但当前代码路径优先适配 Qwen / DashScope 兼容调用方式。
- 模板后置条件当前以状态和验证语句为主，还没有扩展到更细粒度控件级条件。
- 项目明确不走模型微调路线，后续能力增强优先通过 runtime、知识库、状态机和验证策略完成。
- 中文输入依赖系统剪贴板，纯 ASCII 仍用键盘模拟。
- 小图像保护阈值 20px 是保守值，极边缘情况可能仍需进一步调整。
