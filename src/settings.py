# src/settings.py

import questionary
from rich.console import Console
from rich.table import Table

from src import config
from src.ui import clear_screen

console = Console()

_BACK = "BACK"
_BACK_LABEL = [("bold", "BACK")]

# Settings that can be edited interactively
_EDITABLE_SETTINGS: list[dict] = [
    {"key": "model_size", "label": "Default Model Size", "choices": config.MODEL_SIZES},
    {"key": "language", "label": "Default Language", "choices": ["auto"] + [l.lower() for l in config.LANGUAGES]},
    {"key": "task", "label": "Default Task", "choices": config.TASKS},
    {"key": "summary_style", "label": "Summary Style", "choices": list(config.SUMMARY_STYLE_MAP.values())},
    {"key": "gemini_model", "label": "Gemini Model", "choices": None},  # free text
]

# Read-only list settings
_LIST_SETTINGS: list[dict] = [
    {"key": "languages", "label": "Supported Languages"},
    {"key": "file_extensions", "label": "File Extensions"},
]


def _edit_setting(setting: dict, current_value: str) -> str | None:
    """Edit a single setting. Returns new value or None if cancelled."""
    choices = setting["choices"]

    if choices is not None:
        all_choices = list(choices) + [
            questionary.Choice(title=_BACK_LABEL, value=_BACK),
        ]
        answer = questionary.select(
            f"Select new value for '{setting['label']}':",
            choices=all_choices,
            default=current_value if current_value in choices else None,
            instruction="",
        ).ask()

        if answer is None:
            raise KeyboardInterrupt
        if answer == _BACK:
            return None
        return answer
    else:
        answer = questionary.text(
            f"Enter new value for '{setting['label']}':",
            default=current_value,
        ).ask()

        if answer is None:
            raise KeyboardInterrupt
        if not answer.strip():
            return None
        return answer.strip()


def run_settings() -> None:
    """Interactive settings editor loop."""
    while True:
        clear_screen()
        cfg = config.get_config()

        console.print("\n[bold cyan]Settings[/bold cyan]\n")

        # Build menu choices
        menu_choices = []
        for s in _EDITABLE_SETTINGS:
            value = cfg.get(s["key"], "?")
            menu_choices.append(
                questionary.Choice(
                    f"{s['label']}: {value}",
                    value=s["key"],
                )
            )

        menu_choices.append(questionary.Separator())

        for s in _LIST_SETTINGS:
            value = cfg.get(s["key"], [])
            count = len(value) if isinstance(value, list) else "?"
            menu_choices.append(
                questionary.Choice(
                    f"{s['label']}: {count} items (edit config.yaml directly)",
                    value=None,
                    disabled="read-only",
                )
            )

        menu_choices.append(questionary.Separator())
        menu_choices.append(questionary.Choice("Back", value=_BACK))

        answer = questionary.select(
            "Select a setting to edit:",
            choices=menu_choices,
            instruction="",
        ).ask()

        if answer is None:
            raise KeyboardInterrupt

        if answer == _BACK:
            return

        # Find the setting definition and edit it
        setting = next((s for s in _EDITABLE_SETTINGS if s["key"] == answer), None)
        if setting is None:
            continue

        current = cfg.get(setting["key"], "")
        new_value = _edit_setting(setting, str(current))

        if new_value is not None and new_value != str(current):
            config.save_config({setting["key"]: new_value})
            console.print(f"\n[green]Updated '{setting['label']}' to '{new_value}'.[/green]")
            input("\nPress Enter to continue...")
