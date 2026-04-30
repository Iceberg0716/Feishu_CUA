# CUA-Lark

Computer-Use Agent for Lark/Feishu 桌面端 — 基于视觉多模态大模型，像真实用户一样操作飞书桌面客户端。

飞书 AI 校园竞赛 · 质量工程与智能测试赛道

## 快速开始

### 1. 安装依赖

```bash
# 安装 uv（如果尚未安装）
curl -LsSf https://astral.sh/uv/install.sh | sh

# 安装项目依赖
uv sync
```

### 2. 配置 API Key

复制 `.env.example` 为 `.env`，填入你的 DashScope API Key：

```bash
cp .env.example .env
```

编辑 `.env`：

```dotenv
DASHSCOPE_API_KEY=sk-你的实际key
```

### 3. 切换 VLM 模型

在 `cua_lark/config.py` 第 15 行改 `model_name`，或在 `vlm_client.py` 第 49 行改 `base_url` 切换到其他兼容 OpenAI 接口的 VLM 服务：

```python
model_name: str = "qwen-vl-max"            # 改模型名
base_url: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"  # 改 API 地址
```

接入其他 VLM（GPT-4o / Claude / 本地部署等）只需要改这个 `base_url` 和 `api_key`。

### 4. 运行

```bash
# 单步执行
uv run python main.py -i "点击飞书左侧导航栏的消息图标"

# 批量跑测试套件
uv run python main.py -t tests/m1_single_actions.json

# 交互模式（逐条输入指令）
uv run python main.py --interactive
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
├── pyproject.toml                  # 项目配置 & 依赖（uv）
├── test_api.py                     # API 连通性测试
├── tests/
│   └── m1_single_actions.json      # M1 测试用例
├── logs/
│   ├── screenshots/                # 执行截图自动保存
│   └── trace.jsonl                 # 执行轨迹记录
└── cua_lark/
    ├── config.py                   # 配置中心（API key、模型名）
    ├── orchestrator.py             # 主循环 + 自适应缩放
    ├── recorder.py                 # JSONL 轨迹记录
    ├── perception/
    │   ├── screenshot.py           # 全屏截图
    │   └── vlm_client.py          # VLM 调用 + Prompt
    ├── execution/
    │   ├── action_types.py         # 操作类型定义
    │   ├── operator.py             # PyAutoGUI 操作封装
    │   └── parser.py              # VLM 响应解析
    └── verification/
        └── verifier.py             # 截图语义对比验证
```

## 核心模块说明

| 模块 | 文件 | 功能 |
|------|------|------|
| 截图 | `perception/screenshot.py` | 全屏截图，自动编号存盘，自动检测分辨率 |
| VLM | `perception/vlm_client.py` | Qwen-VL 调用，analyze_screen + verify_result |
| 执行 | `execution/operator.py` | 单击/双击/输入/快捷键/滚动 + 随机延迟 |
| 解析 | `execution/parser.py` | VLM JSON → Action 对象，容错解析 |
| 验证 | `verification/verifier.py` | 操作前后截图 VLM 语义对比 |
| 编排 | `orchestrator.py` | 主循环，自适应缩放（>1920px 缩至 1280px） |
| 记录 | `recorder.py` | JSONL 轨迹记录，每步完整信息 |

## M1 进度

- [x] 截图 → VLM 识别 → 坐标定位
- [x] 五种基础操作
- [x] 操作前后截图对比验证
- [x] JSONL 轨迹记录
- [x] CLI 三种运行模式
- [x] 自适应高分辨率屏幕缩放

## 后续规划

| 阶段 | 目标 |
|------|------|
| Phase 2 | 多步串联 + 自愈式执行 |
| Phase 3 | 录制回放 |
| Phase 4 | 多产品覆盖 |
| Phase 5 | 评估体系 + 可视化报告 |
