import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


load_dotenv()


@dataclass(frozen=True)
class Settings:
    openai_api_key: str
    openai_model: str
    assistant_name: str
    user_name: str
    obsidian_vault_path: Path
    obsidian_memory_folder: str
    openai_embedding_model: str
    memory_index_path: Path


def load_settings() -> Settings:
    api_key = os.getenv("OPENAI_API_KEY")
    vault_path_text = os.getenv("OBSIDIAN_VAULT_PATH")

    if not api_key:
        raise ValueError(
            "OPENAI_API_KEY was not found in the .env file."
        )

    if not vault_path_text:
        raise ValueError(
            "OBSIDIAN_VAULT_PATH was not found in the .env file."
        )

    vault_path = Path(vault_path_text).expanduser()

    if not vault_path.exists():
        raise ValueError(
            f"Obsidian vault does not exist at: {vault_path}"
        )

    if not vault_path.is_dir():
        raise ValueError(
            f"OBSIDIAN_VAULT_PATH is not a folder: {vault_path}"
        )

    return Settings(
        openai_api_key=api_key,
        openai_model=os.getenv("OPENAI_MODEL", "gpt-5"),
        assistant_name=os.getenv("FRIDAY_NAME", "Friday"),
        user_name=os.getenv("USER_NAME", "Brad"),
        obsidian_vault_path=vault_path,
        obsidian_memory_folder=os.getenv(
            "OBSIDIAN_MEMORY_FOLDER",
            "Inbox",

        ),
        openai_embedding_model=os.getenv(
            "OPENAI_EMBEDDING_MODEL",
            "text-embedding-3-small",
        ),
        memory_index_path=Path("data/memory_index.json"),
    )