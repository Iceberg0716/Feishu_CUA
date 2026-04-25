<<<<<<< HEAD
# CUA-Lark

Computer-Use Agent for Lark/Feishu 桌面端 — 基于视觉多模态大模型，像真实用户一样操作飞书桌面客户端，实现跨产品自动化功能测试。

飞书 AI 校园竞赛 · 质量工程与智能测试赛道

## 整体架构

```
用户指令（自然语言）
       ↓
  ┌─ 感知层 ─────────────────────────┐
  │  屏幕截图 (mss) + Qwen-VL 视觉识别  │
  └──────────────┬───────────────────┘
                 ↓
  ┌─ 解析层 ─────────────────────────┐
  │  VLM JSON → Action 结构化对象      │
  └──────────────┬───────────────────┘
                 ↓
  ┌─ 执行层 ─────────────────────────┐
  │  PyAutoGUI 鼠标/键盘模拟           │
  └──────────────┬───────────────────┘
                 ↓
  ┌─ 验证层 ─────────────────────────┐
  │  执行前后截图 VLM 语义对比判断成功   │
  └──────────────┬───────────────────┘
                 ↓
  ┌─ 记录层 ─────────────────────────┐
  │  JSONL 轨迹记录（支持录制回放）      │
  └──────────────────────────────────┘
```

## 目录结构

```
CUA/
├── main.py                         # CLI 入口
├── requirements.txt                # Python 依赖
├── tests/
│   └── m1_single_actions.json      # M1 测试用例
├── logs/
│   ├── screenshots/                # 执行截图自动保存
│   └── trace.jsonl                 # 执行轨迹记录
└── cua_lark/
    ├── config.py                   # 配置中心（API key、模型名、超时等）
    ├── orchestrator.py             # 主循环：截图→VLM→解析→执行→验证→记录
    ├── recorder.py                 # 轨迹记录器（录制回放基础）
    ├── perception/
    │   ├── screenshot.py           # 全屏截图（mss），自动编号存盘
    │   └── vlm_client.py          # Qwen-VL API 调用 + 结构化 Prompt
    ├── execution/
    │   ├── action_types.py         # 操作类型定义（单击/双击/输入/快捷键/滚动）
    │   ├── operator.py             # PyAutoGUI 操作封装（含随机延迟）
    │   └── parser.py              # VLM JSON 响应 → Action 对象解析
    └── verification/
        └── verifier.py             # 执行前后截图 VLM 语义验证
```

## 模块说明

### 感知层 (`cua_lark/perception/`)

| 文件 | 职责 |
|------|------|
| `screenshot.py` | 全屏截图，自动编号保存到 `logs/screenshots/` |
| `vlm_client.py` | 调用 Qwen-VL 模型，包含两个核心接口：`analyze_screen`（看图定位+规划动作）、`verify_result`（对比操作前后截图判断成功） |

### 执行层 (`cua_lark/execution/`)

| 文件 | 职责 |
|------|------|
| `action_types.py` | 操作类型数据类：`ClickAction`、`DoubleClickAction`、`TypeAction`、`HotkeyAction`、`ScrollAction` |
| `operator.py` | PyAutoGUI 封装，每次执行前加随机延迟模拟人类行为 |
| `parser.py` | 从 VLM 返回的 JSON 中解析出 Action 对象，坐标越界自动裁剪 |

### 验证层 (`cua_lark/verification/`)

| 文件 | 职责 |
|------|------|
| `verifier.py` | 将执行前后截图 + 预期描述发给 VLM，由模型语义判断操作是否成功 |

### 控制层

| 文件 | 职责 |
|------|------|
| `orchestrator.py` | 主流程编排：截图 → VLM 分析 → 解析 → 执行 → 再截图 → 验证 → 记录 |
| `recorder.py` | 每一步的完整信息（指令、VLM 原始响应、动作、验证结果、截图路径）写入 JSONL |
| `config.py` | 配置中心，通过环境变量 `DASHSCOPE_API_KEY` 传入 API Key |
| `main.py` | CLI 入口，支持单步执行、批量测试、交互模式 |

## 环境要求

- Python 3.10+
- Windows / macOS（PyAutoGUI 需要桌面环境）
- 飞书桌面客户端已安装并登录
- 阿里云 DashScope API Key（Qwen-VL 模型）

## 安装与配置

```bash
# 1. 安装依赖
pip install -r requirements.txt

# 2. 设置 API Key（Windows PowerShell）
$env:DASHSCOPE_API_KEY = "你的key"

# Windows CMD
set DASHSCOPE_API_KEY=你的key

# Linux / macOS
export DASHSCOPE_API_KEY=你的key

# 3. 可选：通过环境变量切换模型
set CUA_MODEL=qwen-vl-plus   # 默认 qwen-vl-max
```

## 使用方式

### 单步执行

```bash
python main.py -i "点击飞书左侧导航栏的消息图标"
```

### 批量运行测试套件

```bash
python main.py -t tests/m1_single_actions.json
```

测试用例 JSON 格式：

```json
[
  {
    "instruction": "自然语言操作描述",
    "expected_action": "click"
  }
]
```

### 交互模式

```bash
python main.py --interactive
```

逐条输入指令，实时查看执行结果和验证结论。

## M1 当前进度

- [x] 截图 → VLM 识别 → 坐标定位
- [x] 五种基础操作：单击、双击、文本输入、快捷键、滚动
- [x] 操作前后截图对比验证
- [x] JSONL 轨迹记录
- [x] CLI 三种运行模式

## 后续规划

| 阶段 | 目标 |
|------|------|
| M2 | 多步操作串联，完成端到端测试流程 |
| M3 | 扩展到 3 个以上飞书子产品 |
| M4 | 评测框架 + 可视化报告 |
| M5 | 自愈式执行、录制回放、多轮对话编排、混合定位策略 |

## 参考文献

- [UI-TARS: Pioneering Automated GUI Interaction with Native Agents](https://arxiv.org/abs/2501.12326) (ByteDance, 2025)
- [OS Agents: A Survey on MLLM-based Agents for Computer, Phone and Browser Use](https://arxiv.org/abs/2503.00607) (ACL 2025 Oral)
- [ScaleCUA: Scaling up Computer Use Agents](https://arxiv.org/abs/2503.03107) (ICLR 2026 Oral)
