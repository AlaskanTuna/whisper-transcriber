# src/config.py

from pathlib import Path

ROOT: Path = Path(__file__).resolve().parent.parent
DEFAULT_INPUT_DIR: Path = ROOT / "audio"
DEFAULT_OUTPUT_DIR: Path = ROOT / "transcripts"

MODEL_SIZES: list[str] = ["tiny", "base", "small", "medium", "large"]
DEFAULT_MODEL_SIZE: str = "small"

LANGUAGES: list[str] = [
    "English",
    "Japanese",
    "Chinese",
    "Korean",
    "Spanish",
    "French",
    "German",
    "Portuguese",
    "Italian",
    "Dutch",
    "Russian",
    "Arabic",
    "Hindi",
    "Turkish",
    "Vietnamese",
    "Thai",
    "Indonesian",
]
DEFAULT_LANGUAGE: str = "Japanese"

TASKS: list[str] = ["transcribe", "translate"]
DEFAULT_TASK: str = "transcribe"

FILE_EXTENSIONS: list[str] = [".m4a", ".mp3", ".wav", ".flac", ".ogg"]
DEFAULT_FILE_EXTENSION: str = ".m4a"
