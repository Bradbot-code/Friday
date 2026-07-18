from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any


@dataclass
class ConversationSession:
    session_id: str
    title: str
    created_at: str
    updated_at: str
    messages: list[dict[str, str]]
    summary: str = ""


class ConversationManager:
    def __init__(self, data_folder: Path) -> None:
        self.data_folder = data_folder
        self.sessions_folder = data_folder / "conversations"
        self.current_session_path = data_folder / "current_session.json"

        self.data_folder.mkdir(parents=True, exist_ok=True)
        self.sessions_folder.mkdir(parents=True, exist_ok=True)

        self.current_session = self._load_current_session()

        if self.current_session is None:
            self.current_session = self.create_new_session()

    def create_new_session(
        self,
        title: str = "New Conversation",
    ) -> ConversationSession:
        now = datetime.now()

        session = ConversationSession(
            session_id=now.strftime("%Y-%m-%d_%H-%M-%S-%f"),
            title=title,
            created_at=now.isoformat(timespec="seconds"),
            updated_at=now.isoformat(timespec="seconds"),
            messages=[],
            summary="",
        )

        self.current_session = session
        self.save_current_session()

        return session

    def add_message(
        self,
        role: str,
        content: str,
    ) -> None:
        role = role.strip().lower()
        content = content.strip()

        if role not in {"user", "assistant"}:
            raise ValueError(
                "Conversation role must be 'user' or 'assistant'."
            )

        if not content:
            return

        self.current_session.messages.append(
            {
                "role": role,
                "content": content,
            }
        )

        self.current_session.updated_at = datetime.now().isoformat(
            timespec="seconds"
        )

        if (
            self.current_session.title == "New Conversation"
            and role == "user"
        ):
            self.current_session.title = self._create_title(content)

        self.save_current_session()

    def replace_messages(
        self,
        messages: list[dict[str, str]],
    ) -> None:
        cleaned_messages: list[dict[str, str]] = []

        for message in messages:
            role = str(message.get("role", "")).strip().lower()
            content = str(message.get("content", "")).strip()

            if role not in {"user", "assistant"}:
                continue

            if not content:
                continue

            cleaned_messages.append(
                {
                    "role": role,
                    "content": content,
                }
            )

        self.current_session.messages = cleaned_messages
        self.current_session.updated_at = datetime.now().isoformat(
            timespec="seconds"
        )

        self.save_current_session()

    def set_summary(self, summary: str) -> None:
        self.current_session.summary = summary.strip()
        self.current_session.updated_at = datetime.now().isoformat(
            timespec="seconds"
        )

        self.save_current_session()

    def clear_messages(self) -> None:
        self.current_session.messages.clear()
        self.current_session.summary = ""
        self.current_session.updated_at = datetime.now().isoformat(
            timespec="seconds"
        )

        self.save_current_session()

    def save_current_session(self) -> Path:
        session_path = self._get_session_path(
            self.current_session.session_id
        )

        serialized = json.dumps(
            asdict(self.current_session),
            indent=2,
            ensure_ascii=False,
        )

        session_path.write_text(
            serialized,
            encoding="utf-8",
        )

        self.current_session_path.write_text(
            serialized,
            encoding="utf-8",
        )

        return session_path

    def list_sessions(
        self,
        max_results: int = 20,
    ) -> list[ConversationSession]:
        sessions: list[ConversationSession] = []

        paths = sorted(
            self.sessions_folder.glob("*.json"),
            key=lambda path: path.stat().st_mtime,
            reverse=True,
        )

        for path in paths[:max_results]:
            session = self._load_session_file(path)

            if session:
                sessions.append(session)

        return sessions

    def load_session(
        self,
        session_id: str,
    ) -> ConversationSession:
        session_path = self._get_session_path(session_id)

        if not session_path.exists():
            raise FileNotFoundError(
                f"Conversation session not found: {session_id}"
            )

        session = self._load_session_file(session_path)

        if session is None:
            raise ValueError(
                f"Conversation session is invalid: {session_id}"
            )

        self.current_session = session
        self.save_current_session()

        return session

    def get_recent_messages(
        self,
        max_messages: int = 30,
    ) -> list[dict[str, str]]:
        if max_messages <= 0:
            return []

        return self.current_session.messages[-max_messages:]

    def get_transcript(
        self,
        max_messages: int | None = None,
    ) -> str:
        messages = self.current_session.messages

        if max_messages is not None:
            messages = messages[-max_messages:]

        lines: list[str] = []

        for message in messages:
            role = message["role"].capitalize()
            content = message["content"]

            lines.append(f"{role}: {content}")

        return "\n\n".join(lines)

    def _load_current_session(
        self,
    ) -> ConversationSession | None:
        if not self.current_session_path.exists():
            return None

        return self._load_session_file(
            self.current_session_path
        )

    def _load_session_file(
        self,
        path: Path,
    ) -> ConversationSession | None:
        try:
            raw_data: dict[str, Any] = json.loads(
                path.read_text(encoding="utf-8")
            )

            messages = raw_data.get("messages", [])

            if not isinstance(messages, list):
                messages = []

            return ConversationSession(
                session_id=str(raw_data["session_id"]),
                title=str(
                    raw_data.get(
                        "title",
                        "Untitled Conversation",
                    )
                ),
                created_at=str(raw_data["created_at"]),
                updated_at=str(raw_data["updated_at"]),
                messages=messages,
                summary=str(raw_data.get("summary", "")),
            )

        except (
            OSError,
            KeyError,
            TypeError,
            ValueError,
            json.JSONDecodeError,
        ):
            return None

    def _get_session_path(
        self,
        session_id: str,
    ) -> Path:
        safe_session_id = re.sub(
            r"[^a-zA-Z0-9_.-]",
            "_",
            session_id,
        )

        return self.sessions_folder / f"{safe_session_id}.json"

    @staticmethod
    def _create_title(
        first_message: str,
    ) -> str:
        cleaned = " ".join(first_message.split())

        if len(cleaned) <= 60:
            return cleaned

        return cleaned[:57].rstrip() + "..."