from __future__ import annotations

from tools.action_center import ActionCenter
from tools.calendar_tools import CalendarTools
from tools.gmail_tools import GmailTools
from tools.obsidian_tools import ObsidianTools
from tools.tool_manager import ToolManager
from tools.weather_tools import WeatherTools


def build_tool_manager(
    obsidian_tools: ObsidianTools,
    gmail_tools: GmailTools,
    calendar_tools: CalendarTools,
    action_center: ActionCenter,
    weather_tools: WeatherTools,
) -> ToolManager:
    manager = ToolManager()

    manager.register("weather_search_locations", "Find matching weather locations by city or postal code.", weather_tools.search_locations, False)
    manager.register("weather_save_location", "Save the user's default weather location after they explicitly request it.", weather_tools.save_location, True)
    manager.register("weather_get_forecast", "Get current conditions and a daily forecast for the saved location.", weather_tools.get_forecast, False)
    manager.register("weather_get_hourly_forecast", "Get the next 1 to 48 hours of weather for the saved location.", weather_tools.get_hourly_forecast, False)

    for name, description, function, protected in (
        ("calendar_list_events", "List primary-calendar events for a date range.", calendar_tools.list_events, False),
        ("calendar_search_events", "Search upcoming calendar events by text.", calendar_tools.search_events, False),
        ("calendar_create_event", "Create a primary-calendar event. Use ISO date-times with timezone offsets.", calendar_tools.create_event, True),
        ("calendar_update_event", "Update an existing calendar event by event ID.", calendar_tools.update_event, True),
        ("calendar_cancel_event", "Cancel a calendar event by event ID.", calendar_tools.cancel_event, True),
        ("action_center_add", "Add a proposed or follow-up action to Friday's local Action Center.", action_center.add_action, True),
        ("action_center_list", "List items in Friday's local Action Center.", action_center.list_actions, False),
        ("action_center_complete", "Mark an Action Center item completed.", action_center.complete_action, True),
        ("action_center_dismiss", "Dismiss an Action Center item.", action_center.dismiss_action, True),
    ):
        manager.register(name=name, description=description, function=function, requires_confirmation=protected)

    manager.register(
        name="gmail_search_emails",
        description=(
            "Search the user's Gmail mailbox with Gmail search syntax and "
            "read matching messages. Use only when the user asks about email."
        ),
        function=gmail_tools.search_emails,
        requires_confirmation=False,
    )

    manager.register(
        name="gmail_list_unread",
        description=(
            "Read recent unread inbox messages so they can be summarized."
        ),
        function=gmail_tools.list_unread,
        requires_confirmation=False,
    )

    manager.register(
        name="gmail_get_tracking_updates",
        description=(
            "Find recent shipment and delivery emails and extract carrier, "
            "tracking-number, and tracking-link information."
        ),
        function=gmail_tools.get_tracking_updates,
        requires_confirmation=False,
    )

    manager.register(
        name="gmail_create_draft",
        description=(
            "Create an unsent Gmail draft with To, subject, body, and optional "
            "Cc or Bcc fields when the user explicitly requests a draft."
        ),
        function=gmail_tools.create_draft,
        requires_confirmation=True,
    )

    manager.register(
        name="gmail_send_email",
        description=(
            "Send a new email only when the user explicitly requests sending "
            "and the recipients, subject, and body are clear."
        ),
        function=gmail_tools.send_email,
        requires_confirmation=True,
    )

    manager.register(
        name="gmail_reply_to_email",
        description=(
            "Reply to a Gmail message by its message ID, optionally replying "
            "to all. Use only when the user explicitly requests the reply and "
            "the reply content is clear."
        ),
        function=gmail_tools.reply_to_email,
        requires_confirmation=True,
    )

    manager.register(
        name="gmail_archive_message",
        description="Archive a Gmail message by removing it from the inbox.",
        function=gmail_tools.archive_message,
        requires_confirmation=True,
    )

    manager.register(
        name="gmail_mark_message_read",
        description="Mark one Gmail message as read using its message ID.",
        function=gmail_tools.mark_message_read,
        requires_confirmation=True,
    )

    manager.register(
        name="gmail_mark_message_unread",
        description="Mark one Gmail message as unread using its message ID.",
        function=gmail_tools.mark_message_unread,
        requires_confirmation=True,
    )

    manager.register(
        name="gmail_trash_message",
        description=(
            "Move one Gmail message to Trash using its message ID. This is "
            "reversible and never permanently deletes the message."
        ),
        function=gmail_tools.trash_message,
        requires_confirmation=True,
    )

    manager.register(
        name="gmail_restore_message",
        description="Restore one Gmail message from Trash.",
        function=gmail_tools.restore_message,
        requires_confirmation=True,
    )

    manager.register(
        name="gmail_bulk_manage_emails",
        description=(
            "Apply one reversible action to up to 100 Gmail messages matching "
            "a specific Gmail search query in a single operation. Allowed "
            "actions: archive, mark_read, mark_unread, trash, restore. Prefer "
            "this tool over repeated single-message calls whenever the user "
            "asks to change multiple messages. Delete means trash."
        ),
        function=gmail_tools.bulk_manage_emails,
        requires_confirmation=True,
    )

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
from tools.action_center import ActionCenter
from tools.calendar_tools import CalendarTools
