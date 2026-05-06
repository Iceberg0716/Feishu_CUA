# LarkCUA-TestAgent (CUA + Feishu Desktop)

Windows 平台的 CUA 自动化测试 Agent：将自然语言测试用例（YAML）规划为结构化 Plan（JSON），通过 Skill/Tool 分层调用 GUI、截图、OCR、验证与报告生成能力。

## Architecture

`Agent Planner → Skill Layer → Tool Abstraction Layer → Provider Layer`

- Planner：只输出 JSON 计划（不输出 Python 代码 / 坐标脚本）
- Skill：封装飞书业务语义（IM / Docs）
- Tool：封装原子能力（点击、输入、截图、OCR、验证）
- Provider：适配具体实现（pywinauto / pyautogui / PaddleOCR / VLM / OpenAPI）

## Requirements

- Windows 10/11
- Python 3.11+
- Feishu / Lark Desktop Client

## Quickstart

1) 安装依赖（按需删减可选项）：

```bash
pip install -r requirements.txt
```

2) 复制配置：

```bash
copy config.example.yaml config.yaml
```

3) (可选) 配置环境变量：

- 复制 `.env.example` 为 `.env`
- 在 `.env` 中填写你本地的 `DASHSCOPE_API_KEY` / `VLM_BASE_URL` / `VLM_MODEL` 等（不要提交 `.env`）

4) 查看 CLI：

```bash
python main.py --help
```

5) 运行测试用例：

```bash
python main.py run testcases/im_send_message.yaml testcases/docs_create_document.yaml
```

输出会写入 `artifacts/runs/<run_id>/`，包括 `result.json`、`report.md`、`report.html`、截图与 JSONL 日志。

## Project Layout

参考 `AGENTS.md` 中的推荐目录结构（MVP：先完成骨架、Schema/Registry、GUI Tools、OCR/Verify、Runner、Report）。
