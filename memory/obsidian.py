from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from datetime import datetime


@dataclass(frozen=True)
class ObsidianNote:
    title: str
    relative_path: str
    content: str


class ObsidianVault:
    def __init__(self, vault_path: Path) -> None:
        self.vault_path = vault_path

        if not self.vault_path.exists():
            raise FileNotFoundError(
                f"Obsidian vault was not found: {self.vault_path}"
            )

    def list_notes(self) -> list[Path]:
        """
        Return all Markdown notes while excluding Obsidian's
        internal configuration folder.
        """
        notes: list[Path] = []

        for path in self.vault_path.rglob("*.md"):
            if ".obsidian" in path.parts:
                continue

            if path.is_file():
                notes.append(path)

        return notes

    def read_note(self, note_path: Path) -> ObsidianNote:
        try:
            content = note_path.read_text(
                encoding="utf-8",
                errors="replace",
            )
        except OSError as exc:
            raise OSError(
                f"Could not read Obsidian note: {note_path}"
            ) from exc

        return ObsidianNote(
            title=note_path.stem,
            relative_path=str(
                note_path.relative_to(self.vault_path)
            ),
            content=content,
        )

    def count_notes(self) -> int:
        return len(self.list_notes())

    def search(
        self,
        query: str,
        max_results: int = 5,
        max_characters_per_note: int = 4_000,
    ) -> list[ObsidianNote]:
        query_terms = self._extract_terms(query)

        if not query_terms:
            return []

        scored_notes: list[tuple[int, ObsidianNote]] = []

        for note_path in self.list_notes():
            try:
                note = self.read_note(note_path)
            except OSError:
                continue

            title_text = note.title.lower()
            path_text = note.relative_path.lower()
            body_text = note.content.lower()

            score = 0

            for term in query_terms:
                # Titles and folder names are stronger indicators.
                score += title_text.count(term) * 10
                score += path_text.count(term) * 5
                score += body_text.count(term)

            if score <= 0:
                continue

            shortened_note = ObsidianNote(
                title=note.title,
                relative_path=note.relative_path,
                content=note.content[:max_characters_per_note],
            )

            scored_notes.append((score, shortened_note))

        scored_notes.sort(
            key=lambda item: item[0],
            reverse=True,
        )

        return [
            note
            for _, note in scored_notes[:max_results]
        ]
    def write_memory(
        self,
        folder_name: str,
        title: str,
        content: str,
    ) -> Path:
        target_folder = self.vault_path / folder_name
        target_folder.mkdir(parents=True, exist_ok=True)

        safe_title = self._sanitize_filename(title)

        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        filename = f"{timestamp} - {safe_title}.md"

        target_path = target_folder / filename

        note_text = (
            "---\n"
            "type: friday-memory\n"
            f"created: {datetime.now().isoformat(timespec='seconds')}\n"
            "status: inbox\n"
            "source: conversation\n"
            "---\n\n"
            f"# {title.strip()}\n\n"
            f"{content.strip()}\n"
        )

        target_path.write_text(
            note_text,
            encoding="utf-8",
        )

        return target_path

    @staticmethod
    def _sanitize_filename(title: str) -> str:
        illegal_characters = '<>:"/\\|?*'

        cleaned = "".join(
            "_" if character in illegal_characters else character
            for character in title
        )

        cleaned = cleaned.strip().strip(".")

        if not cleaned:
            return "Untitled Memory"

        return cleaned[:100]

    @staticmethod
    def _extract_terms(text: str) -> set[str]:
        words = re.findall(r"[a-zA-Z0-9_-]+", text.lower())

        stop_words = {
            "a",
            "an",
            "and",
            "are",
            "about",
            "can",
            "do",
            "for",
            "from",
            "how",
            "i",
            "in",
            "is",
            "it",
            "me",
            "my",
            "of",
            "on",
            "or",
            "the",
            "this",
            "to",
            "was",
            "what",
            "with",
            "you",
        }

        return {
            word
            for word in words
            if len(word) >= 3 and word not in stop_words
        }