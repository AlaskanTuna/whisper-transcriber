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
