from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass
from pathlib import Path

from openai import OpenAI

from memory.obsidian import ObsidianNote, ObsidianVault


@dataclass
class IndexedNote:
    title: str
    relative_path: str
    content: str
    content_hash: str
    embedding: list[float]


class SemanticMemorySearch:
    def __init__(
        self,
        client: OpenAI,
        vault: ObsidianVault,
        embedding_model: str,
        index_path: Path,
    ) -> None:
        self.client = client
        self.vault = vault
        self.embedding_model = embedding_model
        self.index_path = index_path
        self.index_path.parent.mkdir(parents=True, exist_ok=True)

        self.index: dict[str, IndexedNote] = {}
        self._load_index()

    def rebuild_index(self) -> int:
        updated_index: dict[str, IndexedNote] = {}

        for note_path in self.vault.list_notes():
            try:
                note = self.vault.read_note(note_path)
            except OSError:
                continue

            searchable_text = self._build_searchable_text(note)
            content_hash = self._hash_text(searchable_text)

            existing = self.index.get(note.relative_path)

            if existing and existing.content_hash == content_hash:
                updated_index[note.relative_path] = existing
                continue

            embedding = self._create_embedding(searchable_text)

            updated_index[note.relative_path] = IndexedNote(
                title=note.title,
                relative_path=note.relative_path,
                content=note.content,
                content_hash=content_hash,
                embedding=embedding,
            )

        self.index = updated_index
        self._save_index()

        return len(self.index)

    def search(
        self,
        query: str,
        max_results: int = 5,
        minimum_score: float = 0.20,
    ) -> list[tuple[float, ObsidianNote]]:
        if not self.index:
            return []

        query_embedding = self._create_embedding(query)

        scored_notes: list[tuple[float, ObsidianNote]] = []

        for indexed_note in self.index.values():
            score = self._cosine_similarity(
                query_embedding,
                indexed_note.embedding,
            )

            if score < minimum_score:
                continue

            scored_notes.append(
                (
                    score,
                    ObsidianNote(
                        title=indexed_note.title,
                        relative_path=indexed_note.relative_path,
                        content=indexed_note.content,
                    ),
                )
            )

        scored_notes.sort(
            key=lambda item: item[0],
            reverse=True,
        )

        return scored_notes[:max_results]

    def _create_embedding(self, text: str) -> list[float]:
        cleaned_text = text.strip()

        if not cleaned_text:
            cleaned_text = "Empty note"

        response = self.client.embeddings.create(
            model=self.embedding_model,
            input=cleaned_text,
        )

        return response.data[0].embedding

    @staticmethod
    def _build_searchable_text(note: ObsidianNote) -> str:
        return (
            f"Title: {note.title}\n"
            f"Path: {note.relative_path}\n\n"
            f"{note.content}"
        )

    @staticmethod
    def _hash_text(text: str) -> str:
        return hashlib.sha256(
            text.encode("utf-8")
        ).hexdigest()

    @staticmethod
    def _cosine_similarity(
        first: list[float],
        second: list[float],
    ) -> float:
        dot_product = sum(
            a * b
            for a, b in zip(first, second)
        )

        first_length = math.sqrt(
            sum(value * value for value in first)
        )

        second_length = math.sqrt(
            sum(value * value for value in second)
        )

        if first_length == 0 or second_length == 0:
            return 0.0

        return dot_product / (
            first_length * second_length
        )

    def _load_index(self) -> None:
        if not self.index_path.exists():
            return

        try:
            raw_data = json.loads(
                self.index_path.read_text(encoding="utf-8")
            )

            self.index = {
                path: IndexedNote(**data)
                for path, data in raw_data.items()
            }

        except (OSError, json.JSONDecodeError, TypeError):
            self.index = {}

    def _save_index(self) -> None:
        raw_data = {
            path: {
                "title": note.title,
                "relative_path": note.relative_path,
                "content": note.content,
                "content_hash": note.content_hash,
                "embedding": note.embedding,
            }
            for path, note in self.index.items()
        }

        self.index_path.write_text(
            json.dumps(raw_data),
            encoding="utf-8",
        )