from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path


@dataclass
class UserPreferences:
    voice: str = "coral"
    input_device_label: str = ""
    output_device_label: str = ""
    speak_replies: bool = True


class PreferenceStore:
    def __init__(self, path: Path) -> None:
        self.path = path

    def load(self) -> UserPreferences:
        if not self.path.exists():
            return UserPreferences()

        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return UserPreferences()

        return UserPreferences(
            voice=str(raw.get("voice", "coral")),
            input_device_label=str(
                raw.get("input_device_label", "")
            ),
            output_device_label=str(
                raw.get("output_device_label", "")
            ),
            speak_replies=bool(raw.get("speak_replies", True)),
        )

    def save(self, preferences: UserPreferences) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary_path = self.path.with_suffix(".tmp")
        temporary_path.write_text(
            json.dumps(asdict(preferences), indent=2),
            encoding="utf-8",
        )
        temporary_path.replace(self.path)

