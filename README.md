# Whisper Transcriber

A simple yet useful Python script that uses OpenAI's Whisper model to transcribe audio files with timestamped segments.

---

## Features

- Transcribes Japanese audio files (configurable for other languages).
- Outputs timestamped segments for better readability.
- Processes multiple audio files in batch.
- Supports various audio formats via ffmpeg.

---

## Prerequisites
>**Note:** The following instructions assume you're using Ubuntu/Debian CLI to run the setup.

### System Dependencies

```bash
# Install Python and required system packages
sudo apt install python3 python3-pip python3-venv -y

# Install ffmpeg
sudo apt install ffmpeg
```

### Python Dependencies

```bash
# Create and activate virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

---

## Setup

1. Create the following directory structure:

```bash
whisper-transcriber/
├── interview/ # <- Create this by `mkdir interview`
├── ...
└── transcribe.py
```

2. Place your audio files in the `interview/` directory

---

## Usage

```bash
# Activate virtual environment
source venv/bin/activate

# Run the transcriber
python3 transcribe.py
```

---

## Configuration

Edit the configurations in `transcribe.py` to customize, for example:

```python
MODEL_SIZE = "small"
LANGUAGE = "Japanese"
```

---

## Model Performance (From [Whisper Repo](https://github.com/openai/whisper))

| Model Size | VRAM Required | Speed | Accuracy |
|------------|---------------|-------|----------|
| tiny       | ~1 GB        | ~10x  | Lower    |
| small      | ~2 GB        | ~4x   | Good     |
| medium     | ~5 GB        | ~2x   | Better   |
| large      | ~10 GB       | 1x    | Best     |

---

## Supported Audio Formats

- .m4a (default)
- .mp3, .wav, .flac (modify `file_extension` parameter)

---