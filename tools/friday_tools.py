from __future__ import annotations

from tools.obsidian_tools import ObsidianTools
from tools.tool_manager import ToolManager


def build_tool_manager(
    obsidian_tools: ObsidianTools,
) -> ToolManager:
    manager = ToolManager()

    manager.register(
        name="obsidian_list_notes",
        description=(
            "List Markdown notes inside the Obsidian vault "
            "or within a specific folder."
        ),
        function=obsidian_tools.list_notes,
        requires_confirmation=False,
    )

    manager.register(
        name="obsidian_read_note",
        description=(
            "Read the complete contents of one Markdown note "
            "from the Obsidian vault."
        ),
        function=obsidian_tools.read_note,
        requires_confirmation=False,
    )

    manager.register(
        name="obsidian_create_note",
        description=(
            "Create a new Markdown note in the Obsidian vault."
        ),
        function=obsidian_tools.create_note,
        requires_confirmation=True,
    )

    manager.register(
        name="obsidian_update_note",
        description=(
            "Replace the contents of an existing Obsidian note. "
            "A backup is created by default."
        ),
        function=obsidian_tools.update_note,
        requires_confirmation=True,
    )

    manager.register(
        name="obsidian_append_to_note",
        description=(
            "Append additional Markdown content to an existing note."
        ),
        function=obsidian_tools.append_to_note,
        requires_confirmation=True,
    )

    manager.register(
        name="obsidian_move_note",
        description=(
            "Move an Obsidian note to another folder or path."
        ),
        function=obsidian_tools.move_note,
        requires_confirmation=True,
    )

    manager.register(
        name="obsidian_rename_note",
        description=(
            "Rename an existing Obsidian note."
        ),
        function=obsidian_tools.rename_note,
        requires_confirmation=True,
    )

    manager.register(
        name="obsidian_merge_notes",
        description=(
            "Merge multiple Obsidian notes into one new note. "
            "The original notes can be archived."
        ),
        function=obsidian_tools.merge_notes,
        requires_confirmation=True,
    )

    manager.register(
        name="obsidian_archive_note",
        description=(
            "Move an Obsidian note into Friday's archive."
        ),
        function=obsidian_tools.archive_note,
        requires_confirmation=True,
    )

    manager.register(
        name="obsidian_delete_note",
        description=(
            "Archive or permanently delete an Obsidian note."
        ),
        function=obsidian_tools.delete_note,
        requires_confirmation=True,
    )

    manager.register(
        name="obsidian_create_folder",
        description=(
            "Create a new folder inside the Obsidian vault."
        ),
        function=obsidian_tools.create_folder,
        requires_confirmation=True,
    )

    return manager