# Progress

本文件用于在后续会话中持续追踪项目状态。每次 Codex 修改代码/配置/文档后，都应更新此文件（见 `AGENTS.md` 的 Progress Hook）。

## Current Status

- Repo: `d:\\Code\\Python-Learning\\CUA_new`
- Last updated: 2026-05-06

## Milestones (MVP)

- [x] Task 1: 项目骨架（可运行 `python main.py --help`）
- [x] Task 2: 基础 Schema/Registry + 单测
- [x] Task 3: GUI Provider（pyautogui/pywinauto）
- [x] Task 4: GUI Tools + screenshot tool
- [x] Task 5: OCR Provider + Vision/Verify tools
- [x] Task 6: IM Skill
- [x] Task 7: Docs Skill
- [x] Task 8: Rule-based Planner
- [x] Task 9: Runner（重试/恢复/日志/截图）
- [x] Task 10: Report（md/html/result.json）

## Change Log

### 2026-05-06

- Fixed: CLI now accepts `--config` after subcommands (e.g. `python main.py run ... --config config.yaml`) by registering the option on subparsers without overriding root defaults: `runtime/cli.py`.
- Improved: clearer error when `vlm.enabled: true` but `vlm.api_key/model/base_url` are missing after env expansion: `runtime/providers.py`.
- Improved: `im.search_chat` now selects and opens the first result (double-Enter) and closes the search overlay (Esc) to avoid typing the message into the search field: `skills/im.py`.
- Fixed: PaddleOCR 3.x compatibility by falling back when per-call `cls` is unsupported: `providers/paddleocr_provider.py`.
- Improved: `verify.text_visible` now falls back to VLM when OCR provider crashes (instead of failing the step and triggering retries): `tools/verify/text_visible.py`.
- Added: unit test coverage for OCR-error → VLM fallback: `tests/test_tools_ocr_and_verify.py`.
- Added: window-relative click tool to focus inputs robustly: `tools/gui/click_window_relative.py`, `providers/pywinauto_provider.py`, `tools/defaults.py`.
- Improved: `im.send_text` clicks into message input area before typing to avoid leaking keystrokes into the Ctrl+K search box; configurable via `im.message_input_*_ratio`: `skills/im.py`, `config.yaml`, `config.example.yaml`.
- Updated: unit tests for new tool and IM skill behavior: `tests/test_skills_im.py`, `tests/test_tool_registry_with_gui_tools.py`.
- Updated: IM skill unit test expectations for the new hotkey/wait sequence: `tests/test_skills_im.py`.
- Improved: Chinese/non-ASCII input stability by switching `PyAutoGUIProvider.type_text` to clipboard paste (Ctrl+V) via `pyperclip`, with optional `replace` to Ctrl+A+Backspace first: `providers/pyautogui_provider.py`, `tools/gui/type_text.py`.
- Improved: `gui.scroll` supports optional `(x, y)` cursor positioning before scrolling (reduces "scroll doesn't work" cases when focus is wrong): `providers/pyautogui_provider.py`, `tools/gui/scroll.py`.
- Improved: VLM uploads are now guarded/resized (min-dimension check + JPEG + max-long-side shrink) to reduce API errors and speed up requests: `providers/vlm_provider.py`.
- Improved: `docs.open_home` now selects existing query before typing keyword to avoid appending stale text: `skills/docs.py`.
- Added: `pyproject.toml` for `uv` / PEP 621 workflow (keeps `requirements.txt` for compatibility): `pyproject.toml`.
- Updated: add `pyperclip` dependency: `requirements.txt`.
- Chore: initialized `CUA_new` as a git repo and added the same `origin` remote as architecture A (for branch comparison): `.git/config`.
- Improved: `screen.screenshot` can crop to Feishu window rect (focus + get rect via `pywinauto`, then `pyautogui.screenshot(region=...)`) to avoid capturing the wrong foreground window: `tools/vision/screenshot.py`, `providers/pyautogui_provider.py`.
- Improved: IM/Docs verification now re-focuses Feishu and uses cropped screenshots for OCR/VLM to reduce false failures from foreground changes: `skills/im.py`, `skills/docs.py`.
- Improved: `im.search_chat` now uses Down+Enter and a longer post-search wait to more reliably open the top result before dismissing search: `skills/im.py`.
- Fixed: `im.search_chat` no longer presses Esc automatically (Esc could close search before navigation completes, leaving you on the previous page like “推荐”): `skills/im.py`.
- Improved: `im.search_chat` now closes the global search overlay after selecting the top result (Esc after Down+Enter + wait), so message typing doesn't stay in search: `skills/im.py`.
- Changed: simplified IM flow per latest manual observation — `im.search_chat` now only does `Ctrl+K` → `Ctrl+A` → type → `Enter` (no Down/extra Enter/Esc), and `im.send_text` no longer uses window-relative click; typing proceeds directly: `skills/im.py`.
- Ran: `python main.py doctor`
- Ran: `python -m unittest discover -s tests -p "test*.py" -q`
- Ran: `python -m compileall -q .`
- Ran: `python main.py --help`
- Fixed: single-key `gui.hotkey` now uses a real key press (`pyautogui.press`) instead of `pyautogui.hotkey`, and IM/Docs add a short wait after non-ascii typing before pressing Enter (avoids "typed but didn't submit"): `tools/gui/hotkey.py`, `providers/pyautogui_provider.py`, `skills/im.py`, `skills/docs.py`.
- Ran: `python -m unittest tests.test_tools_gui -q`
- Fixed: IM message text no longer gets typed into Ctrl+K global search; `im.search_chat` now closes the search overlay with `Esc`, and `im.send_text` clicks the message input via `gui.click_window_relative` before typing: `skills/im.py`.
- Ran: `python -m unittest tests.test_skills_im -q`
- Fixed: `gui.type_text` now always uses clipboard paste (even for ASCII) to avoid garbled/partial typing; disable retries for side-effect skills by default to avoid duplicate messages on verification failure: `providers/pyautogui_provider.py`, `runtime/runner.py`, `config.yaml`, `config.example.yaml`.
- Updated: unit test expectations for clipboard-based typing: `tests/test_providers_pyautogui.py`.
- Ran: `python -m unittest discover -s tests -p "test*.py" -q`
- Changed: IM skills now support an opt-in “minimal/manual path” by making `Esc` close-search and message-input click configurable (`im.close_search_overlay_after_open`, `im.click_message_input_before_typing`): `skills/im.py`, `config.yaml`, `config.example.yaml`.
- Improved: IM Ctrl+K search timing is now configurable to better match human pacing (`im.search_results_wait_seconds`, `im.open_chat_enter_times`, `im.open_chat_wait_seconds`) without changing the key sequence: `skills/im.py`, `config.yaml`, `config.example.yaml`.
- Improved: Ctrl+K search now optionally selects the first result via `Down` before `Enter` (`im.search_select_first_result`) since Enter-only can leave focus on the search box: `skills/im.py`, `config.yaml`, `config.example.yaml`.
- Changed: IM send path now defaults to the minimal manual flow `Ctrl+K` → `Ctrl+A` → paste `chat_name` → `Enter` (no `Down`) to match current操作习惯; keep `im.search_select_first_result: down_enter` as a fallback: `skills/im.py`, `config.yaml`, `config.example.yaml`.
- Improved: add a small post-paste delay after typing `chat_name` in Ctrl+K search (`im.after_paste_chat_name_wait_seconds`) to avoid Enter firing too fast: `skills/im.py`, `config.yaml`, `config.example.yaml`.
- Chore: ignore local `.claude/` settings from git: `.gitignore`.
- Ran: `python -m compileall -q .`
- Ran: `python -m unittest discover -s tests -p "test*.py" -q`

### 2026-05-02

- Added: project skeleton, CLI entrypoint, sample testcases.
- Added: `ToolSpec/ToolResult/BaseTool/ToolRegistry`, `SkillResult/BaseSkill`, `RunContext/StepLog/CaseResult`, schema tests.
- Updated: `config.example.yaml` uses env vars for API keys; added `runtime/config.py` env expansion helper.
- Added: GUI providers with structured errors: `providers/pyautogui_provider.py`, `providers/pywinauto_provider.py`, `providers/errors.py`.
- Updated: minor cleanup in provider modules (remove redundant exports).
- Added: provider unit tests: `tests/test_providers_pyautogui.py`, `tests/test_providers_pywinauto.py`.
- Added: GUI tools + screenshot tool: `tools/gui/*.py`, `tools/vision/screenshot.py`.
- Added: tool unit tests: `tests/test_tools_gui.py`, `tests/test_tools_screenshot.py`, `tests/test_tool_registry_with_gui_tools.py`.
- Ran: `python -m unittest discover -s tests -p "test*.py" -q`
- Added: OCR provider: `providers/paddleocr_provider.py` + exports in `providers/__init__.py`.
- Added: OCR/Vision/Verify tools: `tools/vision/ocr_extract.py`, `tools/vision/locate_text.py`, `tools/verify/text_visible.py`.
- Added: unit tests for OCR provider/tools: `tests/test_providers_paddleocr.py`, `tests/test_tools_ocr_and_verify.py`.
- Ran: `python -m unittest discover -s tests -p "test*.py" -q`

### 2026-05-03

- Added: IM skills: `skills/app.py`, `skills/im.py`, `skills/_helpers.py`.
- Updated: exports in `skills/__init__.py`.
- Added: IM skill unit tests: `tests/test_skills_im.py`.
- Added: Docs skills: `skills/docs.py` + unit tests `tests/test_skills_docs.py`.
- Added: `.env` support: `runtime/env.py`, `.env.example`, ignore `.env`, and config updates in `runtime/config.py`.
- Added: local debug config files: `.env` (placeholder-only), `config.yaml` (env-driven).
- Updated: VLM config in `config.example.yaml`; added `providers/vlm_provider.py`, `tools/semantic/vlm_judge_state.py` + tests.
- Updated: `tools/verify/text_visible.py` falls back to VLM when OCR is unavailable; `runtime/providers.py` allows running without PaddleOCR when VLM enabled.
- Added: skill/tool defaults & registries: `skills/registry.py`, `skills/defaults.py`, `tools/defaults.py`, `tests/test_skill_registry.py`.
- Added: rule planner: `agent/schemas.py`, `agent/planner.py`, `tests/test_planner_rule.py`.
- Added: runner + JSONL logger: `runtime/runner.py`, `runtime/logger.py`, `runtime/testcases.py`, `runtime/providers.py`, `tests/test_runtime_runner.py`.
- Added: report generator + templates: `reports/generator.py`, `reports/templates/*`, `tests/test_reports_generator.py`.
- Updated: CLI `runtime/cli.py` now runs testcases, generates reports, and improves `doctor` diagnostics; updated `README.md` run instructions.
- Updated: CLI `runtime/cli.py` prints report paths and first failure details after run.
- Updated: CLI `runtime/cli.py` doctor now performs VLM connectivity ping; added `runtime/diagnostics.py` + tests.
- Fixed: VLM ping now uses a valid 1x1 PNG to avoid `invalid_parameter_error` on strict endpoints (`runtime/diagnostics.py`).
- Fixed: VLM ping image size increased to satisfy model min-dimension restrictions (`runtime/diagnostics.py`).
- Ran: `python -m unittest discover -s tests -p "test*.py" -q`
- Ran: `pip install pywinauto pyautogui pillow opencv-python -q`
- Ran: `pip install paddleocr paddlepaddle -q`
- Ran: `python main.py doctor`

## Next

- Optional: add Feishu API/MCP verification (Task 12).
- Optional: improve Docs/IM navigation robustness via more vision tools (locate + click by OCR).

## Notes

- 禁止硬编码任何 API Key；统一走 `${ENV_VAR}` + 加载期展开。
- Skill 不直接 import Provider 或第三方库；一律通过 Tool 调用能力。
