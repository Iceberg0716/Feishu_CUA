# Recorded Skills (Sidecar System)

## What is a Recorded Skill?

Recorded Skill 是一个**可检索、可组合、可截断执行**的 Skill Macro（宏）。它的核心目标是把“常见 GUI 操作片段”用 YAML 结构化描述出来，并提供：

- **Registry 检索**：按 `product/intent`、`postconditions`、参数可满足性与 `preconditions` 兼容性筛选。
- **可组合**：通过 `composed_of` 串联多个 recorded skill，形成更大的业务动作。
- **可截断执行**：支持 `start_step` / `end_step` 只执行一个片段的一部分步骤（用于调试或复用）。

Recorded Skill **不是**替代现有的 Python Skill（例如 `skills/im.py` 内的 `im.send_message`）。它作为旁路扩展存在：

- Planner/Runner 默认仍然只调用现有 Python Skill。
- Recorded Skill 只能通过 `python main.py recorded ...` 命令显式调用。

## Why split into small macros?

推荐把大操作拆分为可复用片段。例如 IM 发送消息可以拆为：

- `recorded.im.open_chat_by_search.v1`：只负责打开会话，postcondition 为 `active_chat_opened`
- `recorded.im.send_text_in_current_chat.v1`：只负责在当前会话发送消息，postcondition 为 `message_sent`
- `recorded.im.send_message_composed.v1`：组合示例（仅示范，不替代现有 `im.send_message`）

好处是：如果新任务与已有示例“前半段相同、后半段不同”，Planner 未来可以复用相同 `postcondition` 的片段（例如先用 `open_chat_by_search` 达到 `active_chat_opened`，再规划新的后续动作）。

## Future recorder (not implemented in v1)

未来录制器设计方向（本次不实现 recorder）：

1. 人工操作 → 生成 `trace.jsonl`
2. `trace_normalizer` 归一化成工具调用序列
3. 参数化（抽取可变字段，如 `chat_name` / `message`）
4. 输出 `generated_skill.yaml`（Recorded Skill）

## CLI usage

Recorded Skill 的 CLI 是旁路命令，不影响现有 `run`：

- `python main.py recorded list`
- `python main.py recorded show <skill_id_or_path>`
- `python main.py recorded plan --product im --intent send_message --param chat_name=测试群 --param message=Hello --state feishu_window_available`
  - (兼容) 也支持旧的 positional 形式：`python main.py recorded plan im send_message ...`
- `python main.py recorded run <skill_id_or_path> --param key=value --yes`

## Reuse & Missing Capability (Planning-only)

- Recorded Skill 是**可复用片段**，不要求必须端到端覆盖一个完整任务。
- 例如，“搜索测试群发 HelloWorld”和“搜索测试群发表情”都可以复用 `recorded.im.open_chat_by_search.v1` 来完成前半段的 `open_chat`。
- 当后半段缺少能力（例如 `send_emoji` 还没有对应 recorded skill）时：
  - `recorded plan` 必须返回 `missing_capability`，明确说明缺失原因，并给出建议录制的 skill id（例如 `recorded.im.send_emoji_in_current_chat.v1`）。
  - 规划阶段不会为了“凑”出计划而生成任何 GUI Tool 操作，也不会执行任何 Tool。
- 默认不允许系统依赖 VLM 去“随机探索”未知 GUI 操作；未来如需探索模式，必须显式开启并在报告中标注。

安全默认值：

- `recorded run` 默认 **dry-run**（不执行 Tool）。只有显式传 `--yes` 才会执行（可能产生 GUI 副作用）。
