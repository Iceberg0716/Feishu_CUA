# Baseline: IM Send Message

## Baseline statement

当前仓库中**已经跑通**的 IM 用例（例如 `testcases/im_send_message.yaml` + `skills/im.py` 的 `im.send_message`）是 baseline。

## Hard constraints for Recorded Skill sidecar

本次 Recorded Skill 开发必须遵守：

1. 不修改现有 `skills/im.py`。
2. 不修改 `testcases/im_send_message.yaml`。
3. 不修改现有 `im.send_message` 默认执行逻辑与默认配置行为。
4. Recorded Skill 只能通过 `python main.py recorded ...` 旁路运行，不能自动接管 baseline 的 Planner/Runner 主流程。

