# Whisper Transcriber

A CLI tool that uses OpenAI's Whisper to batch-transcribe audio files with an optional Gemini AI summarizer. An interactive TUI lets you configure language, model, and output settings before each run.

---

## Features

- **Interactive TUI** -- language, model size, task, and per-file selection at runtime
- **Auto language detection** -- Whisper auto-detects from the first 30 seconds, or choose from 17 curated languages
- **AI summarization** -- optional Gemini-powered transcript summaries (concise or bullet points)
- **Per-file selection** -- pick one or more audio files with file sizes and transcript indicators
- **Queue processing** -- files are transcribed sequentially with per-file error recovery and time estimates
- **Operation summary** -- results table with transcription and summary status after each run
- **Step navigation** -- Back/Exit on every prompt with step indicators and context display
- **Overwrite protection** -- prompts before overwriting existing transcripts
- **Fast startup** -- Whisper/torch are lazy-loaded; TUI appears instantly
- **GPU detection** -- shows compute device and elapsed time after transcription
- **Home page** -- ASCII art dashboard with stats, file management, and interactive settings
- **File management** -- view transcript previews, delete files from audio/ and transcripts/
- **Settings editor** -- change defaults interactively without editing config files
- **YAML config** -- all user presets in `config.yaml`, editable via TUI or directly
- **One-command setup** -- `setup.sh` handles all dependencies, system checks, and API key config

---

## Requirements

### Hardware

| Component | Minimum           | Recommended                      |
| --------- | ----------------- | -------------------------------- |
| CPU       | Any modern x86_64 | Multi-core for faster processing |
| RAM       | 4 GB              | 8 GB+ (for medium/large models)  |
| GPU       | Not required      | NVIDIA CUDA-capable              |
| Disk      | ~5 GB             | ~10 GB (models cached locally)   |

#### VRAM by Model Size

| Model  | VRAM Required |
| ------ | ------------- |
| tiny   | ~1 GB         |
| base   | ~1 GB         |
| small  | ~2 GB         |
| medium | ~5 GB         |
| large  | ~10 GB        |

CPU-only transcription works for all model sizes but is significantly slower.

### Software

- Python 3.10 - 3.13
- ffmpeg
- uv (recommended) or pip

---

## Getting Started

### Quick Start (Recommended)

```bash
git clone <repo-url> whisper-transcriber
cd whisper-transcriber
bash setup.sh
```

The setup script will:

1. Verify Python 3.10+ and ffmpeg
2. Install `uv` if needed
3. Check GPU/CUDA availability, VRAM, RAM, and disk space
4. Install all dependencies via `uv sync`
5. Optionally configure a Gemini API key for AI summarization
6. Launch the transcriber

The script is idempotent -- rerunning it skips completed steps.

### Manual Setup

```bash
# Prerequisites: Python 3.10+, ffmpeg, uv
sudo apt install ffmpeg -y
curl -LsSf https://astral.sh/uv/install.sh | sh

# Install and run
git clone <repo-url> whisper-transcriber
cd whisper-transcriber
uv sync
uv run transcriber
```

Place audio files in the `audio/` directory (created automatically on first run). Transcripts are written to `transcripts/`.

---

## AI Summarization

Transcript summarization is powered by Google's Gemini 2.0 Flash Lite (free tier).

### Setup

1. Get a free API key at [Google AI Studio](https://aistudio.google.com/apikey)
2. Either run `bash setup.sh` (which prompts for the key), or create a `.env` file manually:
   ```
   GEMINI_API_KEY=your-key-here
   ```

### Usage

When a Gemini API key is configured, the task selection step shows additional options:

- **transcribe + summarize** -- transcribe then summarize
- **translate + summarize** -- translate to English then summarize

You can choose between two summary styles:

- **Concise summary** -- a brief paragraph capturing the key points
- **Bullet points** -- structured list of topics and takeaways

Summaries are saved as `filename_summary.txt` alongside the transcript `filename.txt`.

---

## Project Structure

```
src/
├── __init__.py      # Package marker
├── __main__.py      # Entry point and main loop
├── config.py        # YAML config loader with fallback defaults
├── files.py         # File management (view, delete)
├── home.py          # Home page with ASCII art and stats
├── settings.py      # Interactive settings editor
├── summarizer.py    # Gemini AI summarization
├── transcriber.py   # Whisper transcription logic
└── ui.py            # TUI prompts with step navigation
config.yaml          # User-configurable presets
setup.sh             # One-time setup script
audio/               # Input audio files (generated at runtime)
transcripts/         # Output transcripts (generated at runtime)
```

---

## System Architecture

```mermaid
graph TD
    A["__main__.py\nEntry point & main loop"] -->|"run_setup()"| B["ui.py\nInteractive TUI"]
    B -->|"config dict"| A
    A -->|"load_model()\nprocess_queue()"| C["transcriber.py\nWhisper engine"]
    A -->|"summarize_file()"| S["summarizer.py\nGemini API"]
    B --> D["config.py\nDefaults & options"]
    C -->|"lazy import"| E["whisper / torch\nML inference"]
    S -->|"lazy import"| G2["google-genai\nGemini 2.0 Flash Lite"]
    C -->|"reads"| F["audio/\nInput files"]
    C -->|"writes"| T["transcripts/\n*.txt files"]
    S -->|"reads"| T
    S -->|"writes"| T2["transcripts/\n*_summary.txt files"]
```

**Data flow:** `main()` loads `.env`, checks Gemini availability, then loops: TUI setup -> transcription -> optional summarization -> results. The UI module collects user preferences into a config dict without importing heavy modules. When the user confirms, `__main__` lazy-imports the transcriber (triggering `whisper`/`torch`), runs the queue, optionally summarizes via Gemini, and displays results.

**Key constraints:**

- `ui.py` never imports `transcriber.py` or `summarizer.py` -- keeps TUI instant
- `summarizer.py` lazy-imports `google.genai` inside `summarize_file()` only
- Summarization is fully optional -- gated on `GEMINI_API_KEY` presence

---

## Output Format

Each transcript is a `.txt` file with millisecond-precision timestamps:

```
[00:00:00.000] First segment of transcribed text.

[00:00:03.456] Second segment continues here.
```

When summarization is enabled, a companion `_summary.txt` file is created alongside each transcript.

---

## Model Reference

From the [Whisper repo](https://github.com/openai/whisper):

| Model  | VRAM   | Relative Speed | Accuracy |
| ------ | ------ | -------------- | -------- |
| tiny   | ~1 GB  | ~10x           | Lower    |
| base   | ~1 GB  | ~7x            | Fair     |
| small  | ~2 GB  | ~4x            | Good     |
| medium | ~5 GB  | ~2x            | Better   |
| large  | ~10 GB | 1x             | Best     |

---

## Supported Formats

`.m4a`, `.mp3`, `.wav`, `.flac`, `.ogg`, `.aac`, `.opus`, `.webm`

Any format decodable by ffmpeg can be processed by Whisper.

---
