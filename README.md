# Whisper Transcriber

A CLI tool that uses OpenAI's Whisper to batch-transcribe audio files. An interactive TUI lets you configure language, model, and output settings before each run.

---

## Features

- **Interactive TUI** — configure all settings at runtime (language, model size, task, file extension, directories)
- **Multi-language** — 17 curated languages plus free-text entry for any Whisper-supported language
- **Batch processing** — transcribes all matching audio files in a directory
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
└── ui.py            # TUI prompts
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

The TUI prompts you through:

1. Language selection
2. Model size
3. Task (transcribe / translate)
4. Audio file extension
5. Input and output directories
6. Confirmation summary

After transcription completes (or if an error occurs), you're returned to the menu. Press **Ctrl+C** at any point to exit.

Place audio files in `audio/` at the repo root. Transcripts are written to `transcripts/` (auto-created).

---

## Output Format

Each transcript is a `.txt` file with timestamped segments:

```
[0.0s] First segment of transcribed text.

[3.2s] Second segment continues here.
```

---

## Model Reference

From the [Whisper repo](https://github.com/openai/whisper):

| Model | VRAM | Relative Speed | Accuracy |
|-------|------|----------------|----------|
| tiny | ~1 GB | ~10x | Lower |
| base | ~1 GB | ~7x | Fair |
| small | ~2 GB | ~4x | Good |
| medium | ~5 GB | ~2x | Better |
| large | ~10 GB | 1x | Best |

---

## Supported Formats

`.m4a` (default), `.mp3`, `.wav`, `.flac`, `.ogg`

---
