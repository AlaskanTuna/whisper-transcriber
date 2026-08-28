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

## [2026-08-28] v4.0.0 -- Structured Documents and Frictionless I/O

Two problems drove this: the raw Whisper output was unusable as a document, and every run meant
converting video by hand, copying the file into `audio/`, then copying the transcript back out. A
third turned up on the way in: there was no headless mode at all.

### Input and output

- Accepts **any path** -- audio, video, or a folder of either, from anywhere on disk.
- **Video is extracted automatically** with ffmpeg. The MP3 is cached in `audio/` under the source
  name and reused on later runs; `--no-keep-audio` discards it instead.
- **Output goes next to the input file.** Files taken from the project's `audio/` library still land
  in `transcripts/`, and `-o` overrides both. This is what removes the copy-out step.
- New `paths.py` owns those rules; new `media.py` owns probing and extraction.

### Structured documents

- New `polish.py` + `prompts.py`: a two-pass Gemini pipeline producing a titled, sectioned Markdown
  document with a participants table, proper-noun correction key, linked table of contents, and a
  profile-shaped closing section.
- Pass A walks the recording in 12-minute windows with 30s overlap, carrying a running glossary of
  names and spellings into each later window so sections stay consistent with each other.
- Pass B writes the front matter and closing over the assembled body.
- `--profile {meeting,talk,general}` shapes the prompts; `--context` injects known names and is what
  makes proper-noun correction reliable rather than lucky.
- Prompts carry explicit anti-fabrication rules, and instruct the model to prefer "Speaker A" over a
  confidently wrong name -- Whisper does not diarise, and every document says so in its header.
- `normalize_markdown()` repairs the two Markdown mistakes the model reliably makes: flattening a
  table onto the end of a sentence, and running speaker turns together without blank lines.
- Polishing is additive. The raw `.txt` is written first, so an API failure never costs a
  transcription; a failed chunk falls back to its raw text and is reported as a warning.

### Headless CLI

- New `cli.py`. `transcriber <path>...` runs without prompting; no arguments still opens the TUI.
- `-o`, `-f/--format`, `-m`, `-l`, `--task`, `--polish`, `--profile`, `--context`, `--context-file`,
  `--summarize`, `--audio-bitrate`, `--no-keep-audio`, `--overwrite`, `--dry-run`, `-q`, `--version`.
- Reports full output paths, unwrapped, and exits non-zero on failure.

### Output formats

- New `formatter.py`: `txt`, `md`, `srt`, `vtt`, `json`, as pure functions over the segment list.
- Fixed a latent timestamp bug: a segment at 3599.9996s rendered as an impossible `00:59:59.1000`.
- `md` always brings `txt` along, so a polish failure leaves something behind.

### TUI

- Collapsed the six-step wizard. Two questions -- where the recording is, which file -- then a summary
  screen showing every setting and every output path, with **Start** or **Change settings…**.
- Home page gains an explicit path entry with filesystem tab-completion, so no file needs moving.
- Standalone summarize moved out of task selection onto the home menu, where it is discoverable.
- Progress display now steps aside during transcription instead of redrawing over Whisper's own
  progress bar, which carries an ETA.

### Structure

- New `pipeline.py` holds the single job runner both front-ends call, so the TUI and CLI cannot drift.
- New `llm.py` centralises the Gemini client, key loading and rate limiting, shared by the summarizer
  and the polisher.
- `transcriber.py` now returns Whisper's result instead of writing a file itself; queue orchestration
  and the interactive overwrite prompt moved out of it.
- A finished job no longer re-runs Whisper: if every output exists and `--overwrite` is absent, the
  file is skipped before the model loads.

### Tests

- Added `pytest` and a 125-test suite covering formatting, path rules, media handling, chunking,
  glossary carry-forward, Markdown normalization, CLI parsing and pipeline behaviour.
- Whisper and Gemini are mocked; ffmpeg tests generate their own fixtures and skip if it is absent.

### Config

- New keys: `output_format`, `polish`, `polish_profile`, `audio_bitrate`, `keep_extracted_audio`,
  `video_extensions`. A 3.2.0 config file still loads unchanged.
- `gemini_model` default moved to `gemini-3.5-flash-lite`.
