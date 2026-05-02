# CUA-Lark

Computer-Use Agent for Lark/Feishu 桌面端 — 基于视觉多模态大模型，像真实用户一样操作飞书桌面客户端。

飞书 AI 校园竞赛 · 质量工程与智能测试赛道

## 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 配置 API Key

打开 `cua_lark/config.py`，找到 `dashscope_api_key` 字段，把 key 换成你自己的：

```python
# cua_lark/config.py 第 9-14 行
dashscope_api_key: str = field(
    default_factory=lambda: os.environ.get(
        "DASHSCOPE_API_KEY",
        "sk-你的key填在这里",  # ← 改这里
    )
)
```

或者设置环境变量（优先级更高）：
```powershell
# Windows PowerShell
$env:DASHSCOPE_API_KEY = "sk-你的key"

# macOS / Linux
export DASHSCOPE_API_KEY=sk-你的key
```

### 3. 切换 VLM 模型

在 `cua_lark/config.py` 第 15 行改 `model_name`，或在 `vlm_client.py` 第 49 行改 `base_url` 切换到其他兼容 OpenAI 接口的 VLM 服务：

```python
model_name: str = "mimov2.5"               # 改模型名
base_url: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"  # 改 API 地址
```

接入其他 VLM（GPT-4o / Claude / 本地部署等）只需要改这个 `base_url` 和 `api_key`。

### 4. 运行

```bash
# 单步执行
python main.py -i "点击飞书左侧导航栏的消息图标"

# 批量跑测试套件
python main.py -t tests/m1_single_actions.json

# 交互模式（逐条输入指令）
python main.py --interactive
```

## 整体架构

```
用户指令（自然语言）
       ↓
  ┌─ 感知层 ─────────────────────────┐
  │  屏幕截图 + VLM 视觉识别 + 坐标定位   │
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
├── test_api.py                     # API 连通性测试
├── tests/
│   └── m1_single_actions.json      # M1 测试用例
├── logs/
│   ├── screenshots/                # 执行截图自动保存
│   └── trace.jsonl                 # 执行轨迹记录
├── cua_lark/
│   ├── config.py                   # 配置中心（API key、模型名、定位模式、点击确认）
│   ├── orchestrator.py             # 主循环 + 自适应缩放 + 坐标补偿 + 点击确认
│   ├── recorder.py                 # JSONL 轨迹记录
│   ├── knowledge_base.py           # 知识库加载与模板匹配
│   ├── perception/
│   │   ├── screenshot.py           # 全屏截图 + 前台窗口裁剪
│   │   ├── vlm_client.py          # VLM 调用 + Prompt + 点击确认
│   │   └── state_classifier.py    # 页面状态分类
│   ├── execution/
│   │   ├── action_types.py         # 操作类型定义（含 ScrollAction x/y）
│   │   ├── operator.py             # PyAutoGUI 操作封装（含中文输入）
│   │   ├── parser.py              # VLM 响应解析（含滚动参数兼容）
│   │   ├── input_guard.py          # 用户输入空闲检测
│   │   ├── window_manager.py       # 窗口聚焦管理
│   │   └── recovery.py             # 失败恢复链路
│   └── verification/
│       └── verifier.py             # 截图语义对比验证
```

## 核心模块说明

| 模块 | 文件 | 功能 |
|------|------|------|
| 截图 | `perception/screenshot.py` | 全屏截图，自动编号存盘，自动检测分辨率，前台窗口裁剪 |
| VLM | `perception/vlm_client.py` | Qwen-VL 调用，analyze_screen + verify_result + confirm_click_target |
| 执行 | `execution/operator.py` | 单击/双击/输入/快捷键/滚动 + 随机延迟 + 中文剪贴板粘贴 |
| 解析 | `execution/parser.py` | VLM JSON → Action 对象，容错解析（含滚动参数多字段兼容） |
| 验证 | `verification/verifier.py` | 操作前后截图 VLM 语义对比 |
| 编排 | `orchestrator.py` | 主循环，坐标补偿，点击确认，模板匹配，自适应缩放 |
| 记录 | `recorder.py` | JSONL 轨迹记录，每步完整信息 |
| 知识 | `knowledge_base.py` | 知识库加载，模板前后条件匹配 |
| 状态 | `perception/state_classifier.py` | 页面状态识别（消息/日历/文档等） |
| 防护 | `execution/input_guard.py` | 用户输入空闲检测 |
| 窗口 | `execution/window_manager.py` | 目标窗口匹配与聚焦 |
| 恢复 | `execution/recovery.py` | 失败后恢复到稳定模块 |

## M1 进度

- [x] 截图 → VLM 识别 → 坐标定位
- [x] 五种基础操作
- [x] 操作前后截图对比验证
- [x] JSONL 轨迹记录
- [x] CLI 三种运行模式
- [x] 自适应高分辨率屏幕缩放
- [x] VLM 全屏定位 + 分区域定位双模式
- [x] 点击前目标确认（80x80 补丁 VLM 校验）
- [x] 中文/非 ASCII 输入（剪贴板粘贴）
- [x] 滚动光标定位
- [x] 知识库模板执行
- [x] 失败恢复 + 有限重试

## 后续规划

| 阶段 | 目标 |
|------|------|
| Phase 2 | 多步串联 + 自愈式执行 |
| Phase 3 | 录制回放 |
| Phase 4 | 多产品覆盖 |
| Phase 5 | 评估体系 + 可视化报告 |
