# src/config.py

from pathlib import Path

import yaml

# ─── Fixed paths (not user-configurable) ─────────────────────────────────────
ROOT: Path = Path(__file__).resolve().parent.parent
DEFAULT_INPUT_DIR: Path = ROOT / "audio"
DEFAULT_OUTPUT_DIR: Path = ROOT / "transcripts"
CONFIG_PATH: Path = ROOT / "config.yaml"

# ─── Structural constants (not user-configurable) ────────────────────────────
MODEL_SIZES: list[str] = ["tiny", "base", "small", "medium", "large"]
AUTO_DETECT: str = "Auto (detect)"
TASKS: list[str] = ["transcribe", "translate"]
SUMMARY_TASKS: list[str] = ["transcribe + summarize", "translate + summarize"]
STANDALONE_SUMMARY_TASK: str = "summarize"
SUMMARY_STYLES: list[str] = ["Concise summary", "Bullet points"]
SUMMARY_STYLE_MAP: dict[str, str] = {
    "Concise summary": "concise",
    "Bullet points": "bullet_points",
}

# ─── Defaults (used when config.yaml is missing or has invalid values) ───────
_DEFAULTS: dict = {
    "model_size": "small",
    "language": "auto",
    "task": "transcribe",
    "summary_style": "concise",
    "gemini_model": "gemini-3.1-flash-lite-preview",
    "languages": [
        "English", "Japanese", "Chinese", "Korean", "Spanish", "French",
        "German", "Portuguese", "Italian", "Dutch", "Russian", "Arabic",
        "Hindi", "Turkish", "Vietnamese", "Thai", "Indonesian",
    ],
    "file_extensions": [".m4a", ".mp3", ".wav", ".flac", ".ogg", ".aac", ".opus", ".webm"],
}


def _load_yaml() -> dict:
    """Read config.yaml, returning empty dict on any error."""
    try:
        with open(CONFIG_PATH, encoding="utf-8") as f:
            data = yaml.safe_load(f)
        return data if isinstance(data, dict) else {}
    except Exception:  # pylint: disable=broad-exception-caught
        return {}


# Module-level config: defaults merged with user YAML
_cfg: dict = {**_DEFAULTS, **_load_yaml()}

# ─── Derived values (read from _cfg with validation) ─────────────────────────
_ms = _cfg.get("model_size", _DEFAULTS["model_size"])
DEFAULT_MODEL_SIZE: str = _ms if _ms in MODEL_SIZES else _DEFAULTS["model_size"]

LANGUAGES: list[str] = _cfg.get("languages", _DEFAULTS["languages"])
LANGUAGE_MAP: dict[str, str] = {name: name.lower() for name in LANGUAGES}

_lang = _cfg.get("language", _DEFAULTS["language"])
DEFAULT_LANGUAGE: str = AUTO_DETECT if _lang == "auto" else _lang

_task = _cfg.get("task", _DEFAULTS["task"])
DEFAULT_TASK: str = _task if _task in TASKS else _DEFAULTS["task"]

_style = _cfg.get("summary_style", _DEFAULTS["summary_style"])
_REVERSE_STYLE_MAP: dict[str, str] = {v: k for k, v in SUMMARY_STYLE_MAP.items()}
DEFAULT_SUMMARY_STYLE: str = _REVERSE_STYLE_MAP.get(_style, "Concise summary")

FILE_EXTENSIONS: list[str] = _cfg.get("file_extensions", _DEFAULTS["file_extensions"])

GEMINI_MODEL: str = _cfg.get("gemini_model", _DEFAULTS["gemini_model"])


# ─── Config access / persistence ─────────────────────────────────────────────
def get_config() -> dict:
    """Return a copy of the current configuration."""
    return dict(_cfg)


def save_config(updates: dict) -> None:
    """Merge updates into config.yaml and update the in-memory config."""
    current = _load_yaml()
    current.update(updates)
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        yaml.safe_dump(current, f, default_flow_style=False, sort_keys=False)
    _cfg.update(updates)


def get_whisper_task(task: str) -> str:
    """Extract the base Whisper task from a combined task string."""
    return task.split(" + ")[0]
