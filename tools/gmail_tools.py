from __future__ import annotations

import base64
import html
import re
from dataclasses import dataclass
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Any


GMAIL_READONLY_SCOPE = "https://www.googleapis.com/auth/gmail.readonly"


@dataclass(frozen=True)
class GmailStatus:
    connected: bool
    message: str


class GmailTools:
    """Read-only Gmail access for Friday's desktop OAuth connection."""

    def __init__(
        self,
        credentials_path: Path = Path("config/google_credentials.json"),
        token_path: Path = Path("data/google_token.json"),
    ) -> None:
        self.credentials_path = credentials_path
        self.token_path = token_path
        self._service = None

    def get_status(self) -> GmailStatus:
        credentials_path = self._resolve_credentials_path()
        if credentials_path is None:
            return GmailStatus(
                False,
                "OAuth JSON not found in config",
            )
        if not self.token_path.exists():
            return GmailStatus(False, "Ready to connect")

        try:
            self._get_credentials(allow_browser=False)
            return GmailStatus(True, "Connected (read-only)")
        except Exception as exc:
            return GmailStatus(False, f"Reconnect required: {exc}")

    def connect(self) -> GmailStatus:
        """Open Google's OAuth page and save a local read-only token."""
        self._get_credentials(allow_browser=True)
        self._service = None
        self._get_service()
        return GmailStatus(True, "Connected (read-only)")

    def search_emails(
        self,
        query: str,
        max_results: int = 10,
    ) -> list[dict[str, Any]]:
        """Search Gmail using Gmail query syntax and return message details."""
        clean_query = query.strip()
        if not clean_query:
            raise ValueError("A Gmail search query is required.")

        limit = max(1, min(int(max_results), 25))
        service = self._get_service()
        response = (
            service.users()
            .messages()
            .list(userId="me", q=clean_query, maxResults=limit)
            .execute()
        )
        return [
            self._get_message(item["id"])
            for item in response.get("messages", [])
        ]

    def list_unread(self, max_results: int = 10) -> list[dict[str, Any]]:
        """Return recent unread inbox messages for summarization."""
        return self.search_emails(
            "in:inbox is:unread newer_than:14d",
            max_results=max_results,
        )

    def get_tracking_updates(
        self,
        days: int = 30,
        max_results: int = 25,
    ) -> list[dict[str, Any]]:
        """Find shipment emails and extract likely tracking references."""
        safe_days = max(1, min(int(days), 180))
        query = (
            f"newer_than:{safe_days}d "
            "{subject:shipped subject:shipment subject:tracking "
            "subject:delivery subject:delivered subject:arriving}"
        )
        messages = self.search_emails(query, max_results=max_results)
        return [self._extract_tracking(message) for message in messages]

    def _get_credentials(self, allow_browser: bool):
        try:
            from google.auth.transport.requests import Request
            from google.oauth2.credentials import Credentials
            from google_auth_oauthlib.flow import InstalledAppFlow
        except ImportError as exc:
            raise RuntimeError(
                "Gmail libraries are not installed. Run: "
                "pip install -r requirements.txt"
            ) from exc

        credentials = None
        scopes = [GMAIL_READONLY_SCOPE]
        if self.token_path.exists():
            credentials = Credentials.from_authorized_user_file(
                str(self.token_path), scopes
            )

        if credentials and credentials.expired and credentials.refresh_token:
            credentials.refresh(Request())
            self._save_token(credentials.to_json())

        if credentials and credentials.valid:
            return credentials

        if not allow_browser:
            raise RuntimeError("Google authorization is not valid")
        credentials_path = self._resolve_credentials_path()
        if credentials_path is None:
            raise FileNotFoundError(
                "Put the downloaded Google Desktop OAuth JSON in config/"
            )

        flow = InstalledAppFlow.from_client_secrets_file(
            str(credentials_path), scopes
        )
        credentials = flow.run_local_server(
            port=0,
            open_browser=True,
            authorization_prompt_message=(
                "Your browser is opening so you can connect Friday to Gmail."
            ),
            success_message=(
                "Friday is connected to Gmail. You may close this tab."
            ),
        )
        self._save_token(credentials.to_json())
        return credentials

    def _save_token(self, token_json: str) -> None:
        self.token_path.parent.mkdir(parents=True, exist_ok=True)
        temporary_path = self.token_path.with_suffix(".tmp")
        temporary_path.write_text(token_json, encoding="utf-8")
        temporary_path.replace(self.token_path)

    def _resolve_credentials_path(self) -> Path | None:
        if self.credentials_path.exists():
            return self.credentials_path
        candidates = sorted(
            self.credentials_path.parent.glob("client_secret*.json")
        )
        return candidates[0] if candidates else None

    def _get_service(self):
        if self._service is None:
            try:
                from googleapiclient.discovery import build
            except ImportError as exc:
                raise RuntimeError(
                    "Gmail libraries are not installed. Run: "
                    "pip install -r requirements.txt"
                ) from exc
            self._service = build(
                "gmail",
                "v1",
                credentials=self._get_credentials(allow_browser=False),
                cache_discovery=False,
            )
        return self._service

    def _get_message(self, message_id: str) -> dict[str, Any]:
        resource = (
            self._get_service()
            .users()
            .messages()
            .get(userId="me", id=message_id, format="full")
            .execute()
        )
        payload = resource.get("payload", {})
        headers = {
            item.get("name", "").lower(): item.get("value", "")
            for item in payload.get("headers", [])
        }
        body = self._extract_body(payload)
        return {
            "id": resource.get("id", message_id),
            "thread_id": resource.get("threadId", ""),
            "from": headers.get("from", ""),
            "subject": headers.get("subject", "(no subject)"),
            "date": self._normalize_date(headers.get("date", "")),
            "snippet": resource.get("snippet", ""),
            "body": body[:6000],
        }

    @classmethod
    def _extract_body(cls, payload: dict[str, Any]) -> str:
        plain_parts: list[str] = []
        html_parts: list[str] = []

        def visit(part: dict[str, Any]) -> None:
            mime_type = part.get("mimeType", "")
            data = part.get("body", {}).get("data")
            if data and mime_type in {"text/plain", "text/html"}:
                decoded = base64.urlsafe_b64decode(data + "===").decode(
                    "utf-8", errors="replace"
                )
                (plain_parts if mime_type == "text/plain" else html_parts).append(
                    decoded
                )
            for child in part.get("parts", []):
                visit(child)

        visit(payload)
        if plain_parts:
            return "\n".join(plain_parts).strip()
        if html_parts:
            combined = "\n".join(html_parts)
            links = re.findall(
                r"href=[\"'](https?://[^\"']+)[\"']",
                combined,
                flags=re.I,
            )
            combined = re.sub(r"<(script|style).*?</\1>", " ", combined, flags=re.I | re.S)
            combined = re.sub(r"<[^>]+>", " ", combined)
            text = re.sub(r"\s+", " ", html.unescape(combined)).strip()
            return "\n".join((text, *links))
        return ""

    @staticmethod
    def _normalize_date(value: str) -> str:
        try:
            return parsedate_to_datetime(value).astimezone().isoformat()
        except (TypeError, ValueError, OverflowError):
            return value

    @staticmethod
    def _extract_tracking(message: dict[str, Any]) -> dict[str, Any]:
        text = " ".join(
            str(message.get(key, ""))
            for key in ("subject", "snippet", "body")
        )
        patterns = {
            "UPS": r"\b1Z[0-9A-Z]{16}\b",
            "USPS": r"\b(?:94|93|92|95)\d{18,20}\b|\b[A-Z]{2}\d{9}US\b",
            "FedEx": r"\b(?:\d{12}|\d{15})\b",
        }
        tracking: list[dict[str, str]] = []
        seen: set[str] = set()
        for carrier, pattern in patterns.items():
            for match in re.findall(pattern, text, flags=re.I):
                number = match.upper()
                if number not in seen:
                    seen.add(number)
                    tracking.append({"carrier": carrier, "number": number})

        links = re.findall(
            r"https?://[^\s<>\"']*(?:track|shipment|delivery)[^\s<>\"']*",
            text,
            flags=re.I,
        )
        return {
            "from": message.get("from", ""),
            "subject": message.get("subject", ""),
            "date": message.get("date", ""),
            "snippet": message.get("snippet", ""),
            "tracking": tracking,
            "tracking_links": links[:5],
        }
