# 项目状态

## 文档更新规则

- 从 2026-04-29 开始，每一轮问答结束后都要更新项目文档。
- 新一轮开始时，默认不主动读取项目文档，优先依赖当前对话上下文，以降低 token 消耗。
- 项目文档的作用是持久化兜底记忆，而不是每一轮的首要上下文来源。

## 当前运行稳定性状态

- 已增加执行前空闲等待：用户停止移动鼠标和敲击键盘后，程序才会截图并执行动作。
- 已将原先固定的执行后等待替换为再次等待输入稳定后再截图，以减少用户干扰导致的误判。
- 当前方案采用协作式保护：程序等待用户空闲，而不是强行锁定系统输入。
- 已增加窗口聚焦、页面状态识别、失败恢复骨架，主流程不再默认从任意前台窗口直接开始执行。

## 当前任务执行骨架

- 执行前先尝试聚焦目标应用窗口，目标应用名称由 `target_app_names` 配置控制。
- 截图后先做页面状态识别，判断当前是否看到了飞书/Lark，以及当前页面是否属于已知状态。
- 如果当前页面未知，先执行一轮保守恢复，再重新截图并重新识别状态。
- 如果执行后验证失败，当前会先恢复到稳定模块，再自动重跑当前任务，直到达到最大尝试次数。

## 当前知识管理方式

- 与飞书强相关的知识已从代码中抽离到 `knowledge/feishu.json`。
- 当前外置知识包括：应用名称、启动命令、已知页面状态、稳定模块、状态导航快捷键。
- 运行时通过 `cua_lark/knowledge_base.py` 加载知识文件，主流程和恢复逻辑从知识库读取这些信息。

## 后续架构演进方向

- 感知层优先借鉴 ShowUI 的工程思路：
  - 前台窗口裁剪
  - 分区截图分析
  - 二阶段定位
  - 局部视觉精修
- 动作层优先借鉴 LLaVA-VLA 的工程思路：
  - 正式动作 schema
  - action chunk
  - 历史轨迹输入
  - GUI 状态向量
- 当前约束：后续不走模型微调路线，所有能力增强优先通过 runtime、prompt、知识库、状态机和执行框架完成。
- 恢复层继续保留当前项目已有优势：
  - 窗口聚焦
  - 找不到应用时自动启动
  - 稳定模块恢复
  - 知识库驱动的导航与重试
- 数据层仍需要逐步升级为 trajectory 记录格式，但目的改为评测、回放、prompt 优化和规则改进，而不是微调模型。

## 当前恢复与导航策略

- 当前稳定模块由知识库中的 `stable_home_state` 控制，默认是 `messages`。
- 当前通过知识库中的 `state_navigation_hotkeys` 为各页面状态配置导航快捷键。
- 恢复流程默认是：聚焦目标应用 -> `Esc` 收敛局部异常状态 -> 导航到稳定模块 -> 重跑任务。
- 如果当前页面和可见窗口中都没有找到飞书，程序会先尝试直接启动飞书，再执行聚焦与恢复。
- 当前导航策略依赖目标应用快捷键约定，属于可配置骨架，不保证对所有版本和自定义快捷键环境都完全适配。

## 当前截图生命周期

- 截图现在按会话目录保存到 `logs/screenshots/<session_id>/`。
- 每张截图都带有角色标记，例如 `before`、`after`。
- 每个会话都会生成 `index.json`，记录当前会话中的截图。
- 默认情况下，执行成功的步骤只删除该步骤当前可丢弃的截图。
- 默认情况下，执行失败的步骤会保留截图，便于排查问题。
- 历史截图按保留策略清理，而不是全量删除。

## 重要默认配置

- `input_idle_timeout_s = 1.0`
- `input_poll_interval_s = 0.05`
- `post_action_settle_timeout_s = 2.0`
- `post_action_settle_poll_s = 0.2`
- `screenshot_keep_failed = True`
- `screenshot_keep_passed = False`
- `screenshot_keep_latest_sessions = 3`
- `screenshot_keep_max_age_hours = 24`
- `target_app_names = ("Feishu", "Lark", "飞书")`
- `known_page_states = ("messages", "calendar", "docs", "sheets", "meetings", "mail", "knowledge", "unknown")`
- `recovery_max_attempts = 2`
- `stable_home_state = "messages"`
- `state_navigation_hotkeys` 默认使用 `Ctrl+数字` 作为模块导航快捷键
- `target_app_launch_commands`：未检测到飞书时用于尝试启动飞书的候选命令列表
- `app_launch_wait_s = 3.0`
- `app_knowledge_path = "knowledge/feishu.json"`
