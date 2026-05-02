# 会话日志

## 2026-04-29

### 第 1-10 轮摘要

- 解决了用户输入干预导致自动化不稳定的问题。
- 重构了截图保存与删除机制。
- 建立了中文项目文档体系。
- 增加了窗口聚焦、状态识别、恢复到稳定模块、找不到飞书时自动启动。
- 把飞书环境知识迁移到 `knowledge/feishu.json`。
- 完成了基础使用说明文档。
- 真机测试表明：当前环境下真实任务受外部 VLM 网络连接阻塞。

## 2026-04-30

### 第 1-11 轮摘要

- 明确后续不做模型微调。
- 基于本地 ShowUI / LLaVA-VLA 源码做了多轮 runtime 集成。
- 新增前台窗口裁剪、分区分析、二阶段定位。
- 新增 `wait`、`mouse_move`、`drag`、`ActionChunk`。
- 把分区优先级、验证策略、恢复路径、任务模板继续知识库化。
- 新增参数化模板，并支持模板失败回退到 VLM。
- 无模型闭环测试持续通过。

### 第 12 轮

- 用户要求实现“模板前后条件”。
- 已完成：
  - 在 `knowledge/feishu.json` 为模板增加 `preconditions` 和 `postconditions`
  - 在 `cua_lark/orchestrator.py` 增加模板前置检查
  - 在 `cua_lark/orchestrator.py` 增加模板后置检查
  - 模板后置条件失败时，先恢复，再回退到 VLM 路径
  - 重写 `knowledge/feishu.json`，修复原有编码/内容异常
  - 扩展 `tests/test_runtime_no_model.py`
- 本轮新增回归场景：
  - 模板前置条件不满足回退到 VLM
  - 模板后置条件失败回退到 VLM
- 本轮验证结果：
  - `tests/test_runtime_no_model.py` 通过
  - `py_compile` 通过

### 第 13 轮

- 用户要求：给本项目写测试。
- 已新增：
  - `tests/test_parser.py`
  - `tests/test_knowledge_and_screenshot.py`
  - `tests/test_recovery.py`
- 测试覆盖：
  - 解析器 JSON 提取、坐标裁剪、热键解析、`ActionChunk` 标志位
  - 知识库加载、模板条件读取
  - 截图窗口裁剪、区域划分、截图索引更新
  - 恢复链路中的聚焦、状态入口动作、全局恢复动作
- 本轮验证结果：
  - `python -m unittest tests.test_parser tests.test_knowledge_and_screenshot tests.test_recovery` 通过
  - `tests/test_runtime_no_model.py` 再次通过
  - 新增测试文件 `py_compile` 通过

### 第 14 轮

- 用户要求：给出真机飞书环境可直接执行的测试命令。
- 已提供：
  - 环境准备命令
  - 语法校验命令
  - 单元测试命令
  - 无模型闭环命令
  - 真机单步命令
  - 真机交互模式命令
  - 真机测试集命令
- 说明重点：
  - 真机测试前应先手动打开飞书并停手
  - 优先从模板类、模块切换类、搜索输入类指令开始
  - 真实任务仍依赖外部 VLM 接口连通性

### 第 15 轮

- 用户要求：切换到 MiMo / MiniMax M2.5，并做一次需要实际调用模型的真机测试。
- 已修改：
  - `cua_lark/config.py` 现在支持环境变量 `CUA_BASE_URL`
- 已执行真机调用测试：
  - `CUA_MODEL=MiniMax-M2.5`
  - `CUA_BASE_URL=https://api.minimaxi.com/v1`
  - 指令：`打开消息模块`
- 实测结果：
  - 未完成真实任务
  - 失败点在模型接口连接阶段
  - 异常为 `openai.APIConnectionError`
  - 底层为 `httpx.ConnectError: EOF occurred in violation of protocol (_ssl.c:997)`
- 当前判断：
  - 这次失败首先是 MiniMax 端点连接/协议层问题
  - 同时当前项目依赖截图图像输入，MiniMax M2.5 是否支持这条视觉输入链路仍需进一步核对官方文档

### 第 16 轮

- 用户要求：重新测试。
- 已再次执行同一条真机命令：
  - `CUA_MODEL=MiniMax-M2.5`
  - `CUA_BASE_URL=https://api.minimaxi.com/v1`
  - 指令：`打开消息模块`
- 复测结果：
  - 再次失败
  - 错误与上一轮一致
  - 仍为 `openai.APIConnectionError`
  - 底层仍为 `httpx.ConnectError: EOF occurred in violation of protocol (_ssl.c:997)`
- 结论：
  - 当前不是偶发网络抖动
  - 当前 MiniMax 端点在这台机器上的这条调用链路下不可用，至少无法完成本项目所需的真实视觉调用测试

### 第 17 轮

- 用户要求：使用 `gpt-4o-mini` 和新的 OpenAI key 做真机测试。
- 已执行两次：
  - 第一次未显式设置 OpenAI 端点，仍失败
  - 第二次显式设置 `CUA_BASE_URL=https://api.openai.com/v1` 后再次测试
- 第二次使用的关键环境：
  - `CUA_MODEL=gpt-4o-mini`
  - `CUA_BASE_URL=https://api.openai.com/v1`
  - 指令：`打开消息模块`
- 结果：
  - 仍然失败
  - 错误仍为 `openai.APIConnectionError`
  - 底层仍为 `httpx.ConnectError: EOF occurred in violation of protocol (_ssl.c:997)`
- 当前判断：
  - 失败已不再是模型或端点配置错误
  - 更像是当前机器到 OpenAI API 的 TLS/代理/网络环境问题

### 第 18 轮

- 用户要求：重新尝试。
- 已再次执行：
  - `CUA_MODEL=gpt-4o-mini`
  - `CUA_BASE_URL=https://api.openai.com/v1`
  - 指令：`打开消息模块`
- 结果：
  - 仍然失败
  - 报错与前一轮完全一致
  - 仍为 `openai.APIConnectionError`
  - 底层仍为 `httpx.ConnectError: EOF occurred in violation of protocol (_ssl.c:997)`
- 结论：
  - 当前可以排除偶发性
  - 当前机器的 API 访问链路存在稳定的 TLS/代理/网络问题

### 第 19 轮

- 用户要求：改回使用 MiMo / MiniMax M2.5 的版本。
- 已修改：
  - `cua_lark/config.py` 默认模型改回 `MiniMax-M2.5`
  - `cua_lark/config.py` 默认端点改回 `https://api.minimaxi.com/v1`
  - API Key 读取优先级改为：
    - `CUA_API_KEY`
    - `DASHSCOPE_API_KEY`
    - `OPENAI_API_KEY`
- 已验证：
  - `cua_lark/config.py` `py_compile` 通过
  - 默认配置实例输出为 `MiniMax-M2.5` 和 `https://api.minimaxi.com/v1`

### 第 20 轮

- 用户要求：改回千问的版本。
- 已修改：
  - `cua_lark/config.py` 默认模型改回 `qwen-vl-max`
  - `cua_lark/config.py` 默认端点改回 `https://dashscope.aliyuncs.com/compatible-mode/v1`
- 保留不变：
  - API Key 读取优先级仍为 `CUA_API_KEY` -> `DASHSCOPE_API_KEY` -> `OPENAI_API_KEY`
- 已验证：
  - `cua_lark/config.py` `py_compile` 通过
  - 默认配置实例输出为 `qwen-vl-max` 和 `https://dashscope.aliyuncs.com/compatible-mode/v1`

### 第 21 轮

- 用户要求：改回 MiMo 的版本。
- 已修改：
  - `cua_lark/config.py` 默认模型保留为 `mimov2.5`
  - `cua_lark/config.py` 默认端点改回 `https://api.minimaxi.com/v1`
- 已验证：
  - `cua_lark/config.py` `py_compile` 通过
  - 默认配置实例输出为 `mimov2.5` 和 `https://api.minimaxi.com/v1`

### 第 22 轮

- 用户提供：MiMo / MiniMax v2.5 的 API Key，并要求按当前默认配置做真机测试。
- 已执行：
  - 使用 `CUA_API_KEY=tp-...`
  - 不再显式覆盖 `CUA_MODEL` 和 `CUA_BASE_URL`
  - 指令：`打开消息模块`
- 结果：
  - 仍然失败
  - 错误仍为 `openai.APIConnectionError`
  - 底层仍为 `httpx.ConnectError: EOF occurred in violation of protocol (_ssl.c:997)`
- 结论：
  - 说明当前默认 MiMo 配置与用户提供的 key 组合下，真实调用链路仍卡在 TLS/连接层

### 第 23 轮

- 用户询问：当前开代理才能和 ChatGPT 交互，但开代理可能连不上 MiMo，应该怎么办。
- 当前建议：
  - 让 ChatGPT / 浏览器继续走代理
  - 让本项目的 Python 进程单独不走代理
- 可行方式：
  - 在专用 PowerShell 里清空 `HTTP_PROXY`、`HTTPS_PROXY`、`ALL_PROXY`
  - 只在这个终端里运行项目
- 用户进一步询问：这样是否可以一边继续和我协作修改代码，一边让本地 Python 直连 MiMo。
- 结论：
  - 可以
  - 前提是“对话侧代理”和“本地 Python 进程代理”是分开的
  - 最稳的做法是开两个终端或写单独启动脚本

### 第 24 轮

- 用户要求：执行。
- 已完成：
  - 新增 `scripts/run_mimo_direct.ps1`
  - 该脚本会清空当前 PowerShell 进程的代理环境变量
  - 该脚本会注入 `CUA_API_KEY`、`CUA_MODEL=mimov2.5`、`CUA_BASE_URL=https://api.minimaxi.com/v1`
- 已执行脚本：
  - `powershell -ExecutionPolicy Bypass -File scripts\run_mimo_direct.ps1 -Instruction "打开消息模块" -ApiKey "tp-..."`
- 实测结果：
  - 脚本本身已可正常启动
  - 真实模型调用仍失败
  - 错误仍为 `openai.APIConnectionError`
  - 底层仍为 `httpx.ConnectError: EOF occurred in violation of protocol (_ssl.c:997)`
- 当前判断：
  - 问题不是脚本、也不只是当前终端里的环境变量代理
  - 还可能涉及系统代理、TLS 中间层或网络出口策略

### 第 25 轮

- 用户要求：把 API Key 写到 `env` 文件里。
- 已完成：
  - 新增项目根目录 `.env`
  - 写入：
    - `CUA_API_KEY=tp-...`
    - `CUA_MODEL=mimov2.5`
    - `CUA_BASE_URL=https://api.minimaxi.com/v1`
  - 修改 `cua_lark/config.py`，启动时自动加载 `.env`
- 已验证：
  - `cua_lark/config.py` `py_compile` 通过
  - 配置实例已能读出 `.env` 中的 MiMo 模型、端点和 key

### 第 26 轮

- 用户提供了 MiMo 官方 curl 示例，要求按该示例方式连接。
- 已修改：
  - 重写 `cua_lark/perception/vlm_client.py`
  - 不再依赖 OpenAI SDK 发起 MiMo 请求
  - 改为直接 `POST {BASE_URL}/chat/completions`
  - MiMo 路径下使用 `api-key` 请求头
  - 默认模型名改为 `mimo-v2.5-pro`
  - `.env` 与 `scripts/run_mimo_direct.ps1` 同步改为 `mimo-v2.5-pro`
- 已新增：
  - `scripts/test_mimo_text.py`
  - 用于最小文本请求复现官方 curl 示例
- 已验证：
  - `cua_lark/config.py` `py_compile` 通过
  - `cua_lark/perception/vlm_client.py` `py_compile` 通过
  - 最小 MiMo 文本请求仍失败
  - 错误仍为 `httpx.ConnectError: EOF occurred in violation of protocol (_ssl.c:997)`
- 结论：
  - 现在可以排除“鉴权头写法不对”与“OpenAI SDK 兼容层问题”
  - 当前问题已经收敛到 MiMo 端点的 TLS/网络链路本身

### 第 27 轮

- 用户要求：模型改为可选，当前切回原来的 Qwen，API key 放在 `.env` 文件中。
- 已修改：
  - `cua_lark/config.py` 默认模型改回 `qwen-vl-max`
  - `cua_lark/config.py` 默认端点改回 `https://dashscope.aliyuncs.com/compatible-mode/v1`
  - `.env` 当前设置为：
    - `CUA_MODEL=qwen-vl-max`
    - `CUA_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1`
    - `CUA_API_KEY=tp-...`
- 保留：
  - 模型仍然可选，可继续通过 `.env` 或环境变量切换
  - `cua_lark/config.py` 自动加载 `.env`
- 已验证：
  - `cua_lark/config.py` `py_compile` 通过
  - 配置实例输出已确认是 Qwen 默认配置

### 第 28 轮

- 用户提供了阿里云百炼的参考代码，要求按该方式修改连接，模型保持当前选择不变。
- 已修改：
  - `cua_lark/perception/vlm_client.py` 改回 `OpenAI` 兼容调用方式
  - 使用：
    - `api_key=config.dashscope_api_key`
    - `base_url=config.base_url`
    - `client.chat.completions.create(...)`
  - 保留当前模型仍由 `.env` / `CUA_MODEL` 控制，不强制改模型名
- 当前 `.env` 仍为：
  - `CUA_MODEL=qwen-vl-max`
  - `CUA_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1`
- 已验证：
  - `cua_lark/config.py` `py_compile` 通过
  - `cua_lark/perception/vlm_client.py` `py_compile` 通过
  - 配置实例输出仍是 Qwen 当前配置

### 第 29 轮

- 用户指出：给出的阿里百炼示例代码可以成功连接，询问为什么当前项目代码连不上。
- 已确认的根因：
  - 示例代码使用的是百炼 `sk-...` key
  - 项目之前的 `.env` 同时存在 Qwen 和 MiMo 配置
  - 项目之前优先读取的是通用 `CUA_API_KEY`
  - 这导致当项目切到 DashScope 端点时，实际可能拿的是之前残留的 MiMo `tp-...` key，而不是 `QWEN_API_KEY`
- 已修复：
  - `cua_lark/config.py` 现在按 `base_url` 自动选择对应 provider 的 key
  - DashScope 路径优先读取 `QWEN_API_KEY`
  - MiniMax 路径优先读取 `MIMO_API_KEY`
  - `.env` 已改成分别保存两类 key，不再混用
- 已验证：
  - 当前 Qwen 配置实例读取出来的 key 已是 `sk-eb1bd...`

### 第 30 轮

- 用户反馈：执行 `python main.py -i "打开消息模块"` 时，实际上只看到一张截图，而且指令并未真正完成，但程序返回了 `PASS`。
- 当前判断：
  - 这是两个独立问题：
    1. 截图只剩一张：
       - 首次 `before` 截图发生在页面未知、恢复前
       - 恢复后又生成 `before_recovered`
       - 成功时当前代码只删除 `before_path` 和 `after_path`
       - 因此最早那张恢复前截图会残留，看起来像“只截了一张”
    2. 误判为成功：
       - 从 verifier 的自然语言理由看，它引用了 IDE/终端内容
       - 说明验证时很可能截到的仍是终端/IDE 前台，而不是真正的飞书窗口
       - 当前 `verify_step` 仍可能在错误前台窗口上做语义判断，导致假阳性
- 结论：
  - 当前需要补“验证前强制确认目标应用在前台”
  - 以及“恢复前遗留截图的清理一致性”


### 第 31 轮

- 用户提供了 trace.jsonl 执行轨迹，要求分析失败原因。
- 已从 trace 中识别出 4 个 bug：
  1. 滚动参数解析：VLM 输出 `direction`/`pixels`，但 parser 只读 `dy` 字段
  2. 模板 `verify_each_step` 被策略覆盖
  3. VLM 对搜索输入指令只输出 click，缺少 type 动作
  4. VLM 坐标是窗口内相对坐标，但 PyAutoGUI 需要屏幕绝对坐标
- 已修复全部 4 个问题。

### 第 32 轮

- 用户报告 VLM API 返回 400 错误，原因是恢复流程中截取到 <10px 的极小程序窗口。
- 已修复：在 3 层增加尺寸保护（screenshot.py / vlm_client.py），<20px 时回退到全屏或返回安全默认值。

### 第 33 轮

- 用户询问如何提高 VLM 定位准确性。
- 已实现 `localization_mode`（full_window/region）和 `preclick_confirmation`（点击前 80x80 补丁二次确认）两个配置项。

### 第 34 轮

- 滚动仍不生效 + 搜索误点击云文档搜索而非全局搜索。
- 滚动修复：ScrollAction 增加 x/y 字段，滚轮前先 moveTo 定位光标。
- ActionChunk 确认修复：`_confirm_click_target` 改为递归提取第一个 click 子动作做确认。

### 第 35 轮

- 模板 fallback 路径缺少点击确认，回退后仍可能误点击。
- 已修复：template fallback 分支增加 `_confirm_click_target` 调用，同步更新测试 mock。

### 第 36 轮

- 中文输入失败：输入「测试群」实际得到「1」。
- 根因：pyautogui.typewrite() 无法处理中文字符。
- 已修复：改用 pyperclip 剪贴板粘贴（Ctrl+V），新增依赖到 requirements.txt。

### 第 37 轮

- 输入内容出现多余前缀「 1 1测试群 并停留1秒」。
- 根因：搜索框中残留先前操作的内容。
- 已修复：粘贴前增加 Ctrl+A → Backspace 清空输入框。

### 第 38 轮

- 用户要求更新 docs 中文档。
- 已更新全部 6 份文档：使用说明、会话日志、项目状态、决策记录、实现日志、README。
