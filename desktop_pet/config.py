from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Mapping


APP_NAME = "粉白桌宠"
MIN_SPRITE_HEIGHT = 220
MAX_SPRITE_HEIGHT = 440
DEFAULT_SPRITE_HEIGHT = 280


def default_settings_path() -> Path:
    local_app_data = os.environ.get("LOCALAPPDATA")
    base = Path(local_app_data) if local_app_data else Path.home() / "AppData" / "Local"
    return base / APP_NAME / "settings.json"


def _bounded_int(value: Any, default: int) -> int:
    if isinstance(value, bool):
        return default
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return default
    return max(MIN_SPRITE_HEIGHT, min(MAX_SPRITE_HEIGHT, parsed))


def _optional_int(value: Any) -> int | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


@dataclass(slots=True)
class PetSettings:
    sprite_height: int = DEFAULT_SPRITE_HEIGHT
    topmost: bool = True
    auto_action: bool = True
    start_with_windows: bool = False
    x: int | None = None
    y: int | None = None

    @classmethod
    def from_mapping(cls, values: Mapping[str, Any]) -> "PetSettings":
        return cls(
            sprite_height=_bounded_int(
                values.get("sprite_height"),
                DEFAULT_SPRITE_HEIGHT,
            ),
            topmost=bool(values.get("topmost", True)),
            auto_action=bool(values.get("auto_action", True)),
            start_with_windows=bool(values.get("start_with_windows", False)),
            x=_optional_int(values.get("x")),
            y=_optional_int(values.get("y")),
        )


class SettingsStore:
    def __init__(self, path: Path | None = None) -> None:
        self.path = path or default_settings_path()

    def load(self) -> PetSettings:
        try:
            raw = self.path.read_text(encoding="utf-8")
            decoded = json.loads(raw)
        except (FileNotFoundError, OSError, UnicodeError, json.JSONDecodeError):
            return PetSettings()

        if not isinstance(decoded, dict):
            return PetSettings()
        return PetSettings.from_mapping(decoded)

    def save(self, settings: PetSettings) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix(".tmp")
        payload = json.dumps(
            asdict(settings),
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        temporary.write_text(payload + "\n", encoding="utf-8")
        temporary.replace(self.path)
