# Progress Log

## [2026-03-18] Quality-of-Life Improvements

- File selector now shows file sizes and `[has transcript]` indicator for files with existing transcripts.
- Timestamps upgraded from `[HH:MM:SS]` to `[HH:MM:SS.mmm]` with millisecond precision.
- Progress bar now includes time remaining estimate.
- GPU/CPU detection feedback displayed when model loads (e.g., "Model 'small' loaded on GPU (NVIDIA GeForce RTX 3080).").
- Elapsed time shown after transcription completes (e.g., "Completed in 2m 34s").

## [2026-03-18] Setup Script

- Created `setup.sh` for one-time project initialization.
- Checks: Python 3.10+, uv, ffmpeg, GPU/CUDA/VRAM, RAM, disk space.
- Runs `uv sync` for dependency installation.
- Optional Gemini API key configuration (writes to `.env`).
- Idempotent: safe to rerun, skips completed steps.
- Launches transcriber at the end.
- Added `.env` to `.gitignore`.

## [2026-03-18] Gemini AI Summarizer

- Added `google-genai` dependency for Gemini API integration.
- New module `src/summarizer.py` with `summarize_file()`, rate limiting (4s between requests), and `.env` loading.
- Task selection now includes "transcribe + summarize" and "translate + summarize" (shown when `GEMINI_API_KEY` is set).
- New TUI step for summary style: "Concise summary" or "Bullet points" (conditional on summarize task).
- Summaries saved as `filename_summary.txt` alongside transcripts.
- Graceful error handling: API failures do not crash the queue.
- Results table now shows separate Transcription and Summary columns when summarizing.
- TUI state machine refactored from integer steps to named states for clarity.
- Feature is fully optional: no changes to basic transcribe/translate flow without API key.

## [2026-03-18] Documentation Update

- Updated README.md: added setup script usage, AI summarization section, updated architecture diagram, output format, and features list.
- Updated CLAUDE.md: added summarizer to architecture, updated execution flow, documented `.env` and key constraints.
- PROGRESS.md maintained throughout all commit iterations.

## [2026-03-18] YAML Config Refactor

- Created `config.yaml` at project root with all user-configurable presets.
- Refactored `src/config.py` into a YAML loader with hardcoded fallbacks and validation.
- Added `get_config()` and `save_config()` for runtime config access and persistence.
- Moved Gemini model name from hardcoded `summarizer.py` constant to config.
- Added `pyyaml` dependency.

## [2026-03-18] Home Page

- New `src/home.py` module with ASCII art header, program stats, and main menu.
- Stats: audio/transcript/summary counts, average transcript size, recent files.
- Home page options: "Start", "Manage Files", "Settings", "Exit".
- `__main__.py` restructured to dispatch from home page loop.
- Renamed `_format_size` to `format_size` in `ui.py` (public API for home.py).
- Stub modules for `files.py` and `settings.py` (implemented in later commits).

## [2026-03-18] Standalone Summarize Task

- Added standalone "summarize" option in TUI task selection (shown when Gemini API key is set).
- Choosing "summarize" bypasses language/model selection entirely (no Whisper loading).
- New flow: Task -> Transcript Files -> Summary Style -> Confirm.
- New `_scan_transcript_files()` and `_select_transcript_files()` with `[has summary]` indicators.
- Dedicated `_run_standalone_summarization()` and `_show_summary_results()` in `__main__.py`.
- `_show_summary()` adapts display for summarize-only settings (no language/model rows).

## [2026-03-18] Manage Files

- Implemented `src/files.py` with file management sub-flow.
- "View transcript": preview first 20 lines, option to open in $EDITOR.
- "Delete file(s)": multi-select from both audio/ and transcripts/, confirmation required.
- File listing table shows directory, count, and total size.
- Accessible from home page "Manage Files" option.

## [2026-03-18] Settings + Hardware Requirements

- Implemented `src/settings.py` with interactive config editor.
- Editable settings: model size, language, task, summary style, Gemini model.
- List settings (languages, file extensions) shown as read-only with hint to edit config.yaml.
- Changes persisted to `config.yaml` immediately via `save_config()`.
- Added hardware/software requirements section to README (CPU, RAM, GPU, VRAM, disk).
- Updated project structure in README with all new modules.
