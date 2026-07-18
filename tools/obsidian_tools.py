from __future__ import annotations

import shutil
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path


@dataclass
class NoteOperationResult:
    success: bool
    message: str
    path: str | None = None


class ObsidianTools:
    def __init__(
        self,
        vault_path: Path,
        archive_folder: str = "_Friday Archive",
    ) -> None:
        self.vault_path = vault_path.resolve()
        self.archive_path = (
            self.vault_path / archive_folder
        )

        self.archive_path.mkdir(
            parents=True,
            exist_ok=True,
        )

    def _safe_path(
        self,
        relative_path: str,
    ) -> Path:
        candidate = (
            self.vault_path / relative_path
        ).resolve()

        if (
            candidate != self.vault_path
            and self.vault_path not in candidate.parents
        ):
            raise ValueError(
                "The requested path is outside the Obsidian vault."
            )

        return candidate

    def list_notes(
        self,
        folder: str = "",
    ) -> list[str]:
        root = self._safe_path(folder)

        if not root.exists():
            return []

        return sorted(
            str(path.relative_to(self.vault_path))
            for path in root.rglob("*.md")
        )

    def read_note(
        self,
        relative_path: str,
    ) -> str:
        path = self._safe_path(relative_path)

        if not path.exists():
            raise FileNotFoundError(
                f"Note not found: {relative_path}"
            )

        return path.read_text(
            encoding="utf-8"
        )

    def create_note(
        self,
        relative_path: str,
        content: str,
        overwrite: bool = False,
    ) -> NoteOperationResult:
        path = self._safe_path(relative_path)

        if path.suffix.lower() != ".md":
            path = path.with_suffix(".md")

        if path.exists() and not overwrite:
            return NoteOperationResult(
                success=False,
                message="The note already exists.",
                path=str(
                    path.relative_to(self.vault_path)
                ),
            )

        path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        path.write_text(
            content,
            encoding="utf-8",
        )

        return NoteOperationResult(
            success=True,
            message="Note created.",
            path=str(
                path.relative_to(self.vault_path)
            ),
        )

    def update_note(
        self,
        relative_path: str,
        content: str,
        create_backup: bool = True,
    ) -> NoteOperationResult:
        path = self._safe_path(relative_path)

        if not path.exists():
            return NoteOperationResult(
                success=False,
                message="The note does not exist.",
                path=relative_path,
            )

        if create_backup:
            self._backup_note(path)

        path.write_text(
            content,
            encoding="utf-8",
        )

        return NoteOperationResult(
            success=True,
            message="Note updated.",
            path=str(
                path.relative_to(self.vault_path)
            ),
        )

    def append_to_note(
        self,
        relative_path: str,
        content: str,
    ) -> NoteOperationResult:
        path = self._safe_path(relative_path)

        if not path.exists():
            return NoteOperationResult(
                success=False,
                message="The note does not exist.",
                path=relative_path,
            )

        with path.open(
            "a",
            encoding="utf-8",
        ) as file:
            file.write("\n")
            file.write(content.rstrip())
            file.write("\n")

        return NoteOperationResult(
            success=True,
            message="Content appended.",
            path=str(
                path.relative_to(self.vault_path)
            ),
        )

    def move_note(
        self,
        source_path: str,
        destination_path: str,
    ) -> NoteOperationResult:
        source = self._safe_path(source_path)
        destination = self._safe_path(destination_path)

        if not source.exists():
            return NoteOperationResult(
                success=False,
                message="The source note does not exist.",
                path=source_path,
            )

        if destination.suffix.lower() != ".md":
            destination = destination.with_suffix(".md")

        if destination.exists():
            return NoteOperationResult(
                success=False,
                message="The destination already exists.",
                path=str(
                    destination.relative_to(
                        self.vault_path
                    )
                ),
            )

        destination.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        shutil.move(
            str(source),
            str(destination),
        )

        return NoteOperationResult(
            success=True,
            message="Note moved.",
            path=str(
                destination.relative_to(
                    self.vault_path
                )
            ),
        )

    def rename_note(
        self,
        relative_path: str,
        new_name: str,
    ) -> NoteOperationResult:
        source = self._safe_path(relative_path)

        if not source.exists():
            return NoteOperationResult(
                success=False,
                message="The note does not exist.",
                path=relative_path,
            )

        clean_name = new_name.strip()

        if not clean_name.lower().endswith(".md"):
            clean_name += ".md"

        destination = source.with_name(clean_name)

        return self.move_note(
            str(source.relative_to(self.vault_path)),
            str(destination.relative_to(self.vault_path)),
        )

    def merge_notes(
        self,
        source_paths: list[str],
        destination_path: str,
        title: str,
        archive_originals: bool = True,
    ) -> NoteOperationResult:
        if not source_paths:
            return NoteOperationResult(
                success=False,
                message="No source notes were provided.",
            )

        sections: list[str] = [
            f"# {title}",
            "",
            (
                f"_Consolidated by Friday on "
                f"{datetime.now():%Y-%m-%d %H:%M}_"
            ),
            "",
        ]

        source_files: list[Path] = []

        for source_path in source_paths:
            path = self._safe_path(source_path)

            if not path.exists():
                return NoteOperationResult(
                    success=False,
                    message=(
                        f"Source note not found: "
                        f"{source_path}"
                    ),
                    path=source_path,
                )

            source_files.append(path)

            content = path.read_text(
                encoding="utf-8"
            ).strip()

            sections.extend(
                [
                    f"## Source: {path.stem}",
                    "",
                    content,
                    "",
                    "---",
                    "",
                ]
            )

        combined_content = "\n".join(
            sections
        ).rstrip() + "\n"

        result = self.create_note(
            destination_path,
            combined_content,
            overwrite=False,
        )

        if not result.success:
            return result

        if archive_originals:
            for source_file in source_files:
                self._archive_note(source_file)

        return NoteOperationResult(
            success=True,
            message=(
                "Notes merged successfully. "
                "Original notes were archived."
            ),
            path=result.path,
        )

    def archive_note(
        self,
        relative_path: str,
    ) -> NoteOperationResult:
        path = self._safe_path(relative_path)

        if not path.exists():
            return NoteOperationResult(
                success=False,
                message="The note does not exist.",
                path=relative_path,
            )

        archived_path = self._archive_note(path)

        return NoteOperationResult(
            success=True,
            message="Note archived.",
            path=str(
                archived_path.relative_to(
                    self.vault_path
                )
            ),
        )

    def delete_note(
        self,
        relative_path: str,
        permanent: bool = False,
    ) -> NoteOperationResult:
        path = self._safe_path(relative_path)

        if not path.exists():
            return NoteOperationResult(
                success=False,
                message="The note does not exist.",
                path=relative_path,
            )

        if not permanent:
            archived_path = self._archive_note(path)

            return NoteOperationResult(
                success=True,
                message=(
                    "Note moved to Friday's archive."
                ),
                path=str(
                    archived_path.relative_to(
                        self.vault_path
                    )
                ),
            )

        path.unlink()

        return NoteOperationResult(
            success=True,
            message="Note permanently deleted.",
            path=relative_path,
        )

    def create_folder(
        self,
        relative_path: str,
    ) -> NoteOperationResult:
        path = self._safe_path(relative_path)

        path.mkdir(
            parents=True,
            exist_ok=True,
        )

        return NoteOperationResult(
            success=True,
            message="Folder created.",
            path=str(
                path.relative_to(self.vault_path)
            ),
        )

    def _backup_note(
        self,
        path: Path,
    ) -> Path:
        timestamp = datetime.now().strftime(
            "%Y%m%d_%H%M%S"
        )

        backup_folder = (
            self.archive_path / "Backups"
        )

        backup_folder.mkdir(
            parents=True,
            exist_ok=True,
        )

        backup_path = (
            backup_folder
            / f"{path.stem}_{timestamp}{path.suffix}"
        )

        shutil.copy2(
            path,
            backup_path,
        )

        return backup_path

    def _archive_note(
        self,
        path: Path,
    ) -> Path:
        relative_parent = path.parent.relative_to(
            self.vault_path
        )

        destination_folder = (
            self.archive_path / relative_parent
        )

        destination_folder.mkdir(
            parents=True,
            exist_ok=True,
        )

        destination = (
            destination_folder / path.name
        )

        if destination.exists():
            timestamp = datetime.now().strftime(
                "%Y%m%d_%H%M%S"
            )

            destination = destination.with_name(
                f"{destination.stem}_{timestamp}"
                f"{destination.suffix}"
            )

        shutil.move(
            str(path),
            str(destination),
        )

        return destination