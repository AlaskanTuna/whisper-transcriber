# src/config.py

from pathlib import Path

ROOT: Path = Path(__file__).resolve().parent.parent
DEFAULT_INPUT_DIR: Path = ROOT / "audio"
DEFAULT_OUTPUT_DIR: Path = ROOT / "transcripts"

MODEL_SIZES: list[str] = ["tiny", "base", "small", "medium", "large"]
DEFAULT_MODEL_SIZE: str = "small"

AUTO_DETECT: str = "Auto (detect)"

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
LANGUAGE_MAP: dict[str, str] = {name: name.lower() for name in LANGUAGES}
DEFAULT_LANGUAGE: str = AUTO_DETECT

TASKS: list[str] = ["transcribe", "translate"]
SUMMARY_TASKS: list[str] = ["transcribe + summarize", "translate + summarize"]
DEFAULT_TASK: str = "transcribe"

SUMMARY_STYLES: list[str] = ["Concise summary", "Bullet points"]
SUMMARY_STYLE_MAP: dict[str, str] = {
    "Concise summary": "concise",
    "Bullet points": "bullet_points",
}
DEFAULT_SUMMARY_STYLE: str = "Concise summary"

FILE_EXTENSIONS: list[str] = [".m4a", ".mp3", ".wav", ".flac", ".ogg", ".aac", ".opus", ".webm"]


def get_whisper_task(task: str) -> str:
    """Extract the base Whisper task from a combined task string."""
    return task.split(" + ")[0]
