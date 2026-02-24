# Whisper Transcriber

A CLI tool that uses OpenAI's Whisper to batch-transcribe audio files. An interactive TUI lets you configure language, model, and output settings before each run.

---

## Features

- **Interactive TUI** — language, model size, task, and per-file selection at runtime
- **Auto language detection** — Whisper auto-detects from the first 30 seconds, or choose from 17 curated languages
- **Per-file selection** — pick one or more audio files via multi-select checkbox
- **Queue processing** — files are transcribed sequentially with per-file error recovery
- **Operation summary** — results table showing per-file success/failure after each run
- **Step navigation** — Back/Exit options on every prompt; summary rejection returns to start
- **Minimal output** — `rich` progress bar only, no verbose transcription text
- **Persistent menu** — returns to setup after each run or error; Ctrl+C to exit

---

## Project Structure

```
src/
├── __init__.py      # Package marker
├── __main__.py      # Entry point and main loop
├── config.py        # Defaults and option lists
├── transcriber.py   # Whisper transcription logic
└── ui.py            # TUI prompts with step navigation
audio/               # Input audio files
transcripts/         # Output transcripts
```

---

## Prerequisites

**System:** Python 3.10+, ffmpeg

```bash
# Ubuntu/Debian
sudo apt install python3 python3-pip python3-venv ffmpeg -y
```

**Python:**

```bash
python3 -m venv venv
source venv/bin/activate        # Linux/macOS
# venv\Scripts\activate          # Windows
pip install -r requirements.txt
```

---

## Usage

```bash
source venv/bin/activate
python -m src
```

---

## Output Format

Each transcript is a `.txt` file with timestamped segments:

```
[00:00:00] First segment of transcribed text.

[00:00:03] Second segment continues here.
```

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

`.m4a`, `.mp3`, `.wav`, `.flac`, `.ogg`

---
