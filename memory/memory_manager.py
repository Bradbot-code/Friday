from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from memory.obsidian import ObsidianNote, ObsidianVault
from memory.semantic_search import SemanticMemorySearch


@dataclass(frozen=True)
class MemoryProposal:
    title: str
    content: str
    reason: str


class MemoryManager:
    def __init__(
        self,
        vault: ObsidianVault,
        semantic_search: SemanticMemorySearch,
        memory_folder: str = "Inbox",
    ) -> None:
        self.vault = vault
        self.semantic_search = semantic_search
        self.memory_folder = memory_folder

    def retrieve_context(
        self,
        user_message: str,
        max_results: int = 5,
    ) -> str:
        semantic_results = self.semantic_search.search(
            query=user_message,
            max_results=max_results,
        )

        if semantic_results:
            notes = [
                note
                for _, note in semantic_results
            ]

            return self._format_notes(notes)

        # Keyword fallback if the index is empty or finds nothing.
        notes = self.vault.search(
            query=user_message,
            max_results=max_results,
        )

        if not notes:
            return ""

        return self._format_notes(notes)

    def rebuild_index(self) -> int:
        return self.semantic_search.rebuild_index()

    def save_proposal(
        self,
        proposal: MemoryProposal,
    ) -> Path:
        saved_path = self.vault.write_memory(
            folder_name=self.memory_folder,
            title=proposal.title,
            content=proposal.content,
        )

        # Keep semantic memory synchronized after saving.
        self.rebuild_index()

        return saved_path

    @staticmethod
    def _format_notes(
        notes: list[ObsidianNote],
    ) -> str:
        sections: list[str] = []

        for note in notes:
            sections.append(
                f"NOTE: {note.title}\n"
                f"PATH: {note.relative_path}\n"
                f"CONTENT:\n{note.content.strip()}"
            )

        return "\n\n---\n\n".join(sections)