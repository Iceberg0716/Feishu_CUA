# Progress

Last updated: 2026-05-06

## Change Log
- 2026-05-06: Make OCR optional via `vision.ocr_enabled`; when disabled, OCR tools/providers are not initialized/called and `im.search_chat` runs VLM-only; `doctor` prints OCR import failures as WARN and skips checks when OCR is disabled.
- 2026-05-06: Tune VLM-only Ctrl+K click guard by introducing `im.search_box_region_max_y_ratio` and pass it into `vlm.find_chat_candidate` as `search_box_max_y` to avoid false failures on top results. Commands: `python -m compileall .`, `git diff --check`.

用于新会话快速了解“当前做到哪一步”。详细历史以 `git log` 为准（不再在此文件里堆叠长日志）。更新规范见 `AGENTS.md` 的 Progress Hook。

## 当前状态（截至 2026-05-06）

- 仓库：`d:\\Code\\Python-Learning\\CUA_new`
- MVP 骨架：已完成（Skills/Tools/Runner/Reports/单测齐全）
- IM 打开会话：已改为 **OCR/VLM 点击候选**（不再用 Enter/Down+Enter 打开会话）

## IM 会话打开策略（现状）

- 流程：`app.open_or_focus` → `Ctrl+K` → `Ctrl+A` → 粘贴 `chat_name` → 截图（裁剪到飞书窗口）→ OCR 选候选（不明确则 VLM JSON 兜底）→ 点击候选 → `verify_chat_opened`
- 关键 evidence：`open_strategy:ocr_vlm_click`、`screenshot:search_results:...`、`ocr_candidate_count:*`、`selected_candidate_source:*`、`selected_candidate_bbox:*`、`click:x,y`、`verify_chat_opened:true/false`

## 当前阻塞（需要优先解决）

- OCR 引擎在 Windows 环境崩溃，导致 `vision.ocr_extract` 失败，后续“选候选/点击/verify”都不会发生。
- 最新复现 run：`artifacts/runs/2026-05-06_214143/logs/run.jsonl`
  - 报错：`ocr_extract failed: (Unimplemented) ConvertPirAttribute2RuntimeAttribute ... onednn_instruction.cc:118`
  - 截图：`artifacts/runs/2026-05-06_214143/screenshots/search_results_20260506_214155_520631.png`（候选非常清晰，但 OCR 没跑起来）
- 环境信息（本机）：Python `3.13.7`，Paddle `3.3.1`

## 相关配置（常用项）

- `im.open_chat_strategy`: `"ocr_vlm_click"`
- `im.search_chat_max_retries`: `2`
- `im.after_ctrl_k_wait_seconds` / `im.after_ctrl_a_wait_seconds` / `im.after_paste_chat_name_wait_seconds` / `im.search_results_wait_seconds` / `im.after_open_chat_wait_seconds`
- `im.ocr_candidate_min_confidence` / `im.ocr_candidate_min_score`

## 下一步建议（讨论后再动手）

- 先解决 OCR 环境/依赖崩溃（否则 IM/verify 相关 OCR 全都会失败）。
- 再考虑是否允许 “OCR 失败时直接走 VLM-only 兜底”（属于策略变更）。
