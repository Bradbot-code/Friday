from pathlib import Path
import tkinter as tk

from openai import OpenAI

from brain.ai import FridayAI
from config.settings import load_settings
from interface.friday_gui import FridayGUI
from memory.conversation_manager import ConversationManager
from memory.memory_manager import MemoryManager
from memory.obsidian import ObsidianVault
from memory.semantic_search import SemanticMemorySearch
from tools.voice import VoiceService
from tools.friday_tools import build_tool_manager
from tools.gmail_tools import GmailTools
from tools.obsidian_tools import ObsidianTools
from tools.action_center import ActionCenter
from tools.calendar_tools import CalendarTools
from tools.weather_tools import WeatherTools

def build_friday() -> tuple[
    FridayAI,
    VoiceService,
    MemoryManager,
    ConversationManager,
    GmailTools,
    CalendarTools,
    ActionCenter,
    WeatherTools,
]:
    settings = load_settings()

    openai_client = OpenAI(
        api_key=settings.openai_api_key
    )

    vault = ObsidianVault(
        settings.obsidian_vault_path
    )

    obsidian_tools = ObsidianTools(
        vault_path=settings.obsidian_vault_path
    )

    gmail_tools = GmailTools()
    calendar_tools = CalendarTools(gmail_tools)
    action_center = ActionCenter()
    weather_tools = WeatherTools()

    tool_manager = build_tool_manager(
        obsidian_tools=obsidian_tools,
        gmail_tools=gmail_tools,
        calendar_tools=calendar_tools,
        action_center=action_center,
        weather_tools=weather_tools,
    )

    semantic_search = SemanticMemorySearch(
        client=openai_client,
        vault=vault,
        embedding_model=settings.openai_embedding_model,
        index_path=settings.memory_index_path,
    )

    memory_manager = MemoryManager(
        vault=vault,
        semantic_search=semantic_search,
        memory_folder=settings.obsidian_memory_folder,
    )

    conversation_manager = ConversationManager(
        data_folder=Path("data")
    )

    friday = FridayAI(
        settings=settings,
        memory_manager=memory_manager,
        conversation_manager=conversation_manager,
        tool_manager=tool_manager,
    )

    voice_service = VoiceService(
        client=openai_client
    )

    return (
        friday,
        voice_service,
        memory_manager,
        conversation_manager,
        gmail_tools,
        calendar_tools,
        action_center,
        weather_tools,
    )


def main() -> None:
    try:
        (
            friday,
            voice_service,
            memory_manager,
            conversation_manager,
            gmail_tools,
            calendar_tools,
            action_center,
            weather_tools,
        ) = build_friday()

    except Exception as exc:
        print(f"Friday could not start: {exc}")
        return

    root = tk.Tk()

    FridayGUI(
        root=root,
        friday=friday,
        voice_service=voice_service,
        memory_manager=memory_manager,
        conversation_manager=conversation_manager,
        gmail_tools=gmail_tools,
        action_center=action_center,
        weather_tools=weather_tools,
    )

    root.mainloop()


if __name__ == "__main__":
    main()
