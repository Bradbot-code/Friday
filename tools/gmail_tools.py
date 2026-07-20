from __future__ import annotations

import base64
import html
import json
import re
from dataclasses import dataclass
from email.message import EmailMessage
from email.utils import getaddresses, parseaddr
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Any


GMAIL_MODIFY_SCOPE = "https://www.googleapis.com/auth/gmail.modify"


@dataclass(frozen=True)
class GmailStatus:
    connected: bool
    message: str


class GmailTools:
    """Gmail access with reversible mailbox changes and no permanent delete."""

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
            return GmailStatus(True, "Connected (send and manage)")
        except Exception as exc:
            return GmailStatus(False, f"Reconnect required: {exc}")

    def connect(self) -> GmailStatus:
        """Open Google's OAuth page and save a local Gmail token."""
        self._get_credentials(allow_browser=True)
        self._service = None
        self._get_service()
        return GmailStatus(True, "Connected (send and manage)")

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

    def create_draft(
        self,
        to: str,
        subject: str,
        body: str,
        cc: str = "",
        bcc: str = "",
    ) -> dict[str, str]:
        """Create an unsent Gmail draft."""
        raw = self._build_raw_message(to, subject, body, cc, bcc)
        result = (
            self._get_service()
            .users()
            .drafts()
            .create(userId="me", body={"message": {"raw": raw}})
            .execute()
        )
        return {
            "status": "draft_created",
            "draft_id": result.get("id", ""),
            "message_id": result.get("message", {}).get("id", ""),
            "to": to,
            "subject": subject,
        }

    def send_email(
        self,
        to: str,
        subject: str,
        body: str,
        cc: str = "",
        bcc: str = "",
    ) -> dict[str, str]:
        """Send a new email through the connected Gmail account."""
        raw = self._build_raw_message(to, subject, body, cc, bcc)
        result = (
            self._get_service()
            .users()
            .messages()
            .send(userId="me", body={"raw": raw})
            .execute()
        )
        return {
            "status": "sent",
            "message_id": result.get("id", ""),
            "thread_id": result.get("threadId", ""),
            "to": to,
            "subject": subject,
        }

    def reply_to_email(
        self,
        message_id: str,
        body: str,
        reply_all: bool = False,
    ) -> dict[str, Any]:
        """Send a reply in an existing Gmail thread."""
        clean_id = self._validate_message_id(message_id)
        original = (
            self._get_service()
            .users()
            .messages()
            .get(userId="me", id=clean_id, format="metadata")
            .execute()
        )
        headers = self._headers(original.get("payload", {}))
        sender = headers.get("reply-to") or headers.get("from", "")
        sender_address = parseaddr(sender)[1]
        if not sender_address:
            raise ValueError("The original message has no reply address.")

        recipients = [sender_address]
        cc_recipients: list[str] = []
        if reply_all:
            profile = self._get_service().users().getProfile(userId="me").execute()
            own_address = profile.get("emailAddress", "").lower()
            candidates = getaddresses(
                [headers.get("to", ""), headers.get("cc", "")]
            )
            for _, address in candidates:
                normalized = address.lower()
                if normalized and normalized != own_address and normalized != sender_address.lower():
                    cc_recipients.append(address)

        subject = headers.get("subject", "")
        if not subject.lower().startswith("re:"):
            subject = f"Re: {subject}"
        message = EmailMessage()
        message["To"] = ", ".join(recipients)
        if cc_recipients:
            message["Cc"] = ", ".join(dict.fromkeys(cc_recipients))
        message["Subject"] = self._clean_header(subject, "subject")
        original_message_id = headers.get("message-id", "")
        if original_message_id:
            message["In-Reply-To"] = self._clean_header(
                original_message_id, "message ID"
            )
            references = headers.get("references", "")
            message["References"] = self._clean_header(
                f"{references} {original_message_id}".strip(),
                "references",
            )
        message.set_content(self._clean_body(body))
        raw = base64.urlsafe_b64encode(message.as_bytes()).decode("ascii")
        result = (
            self._get_service()
            .users()
            .messages()
            .send(
                userId="me",
                body={"raw": raw, "threadId": original.get("threadId", "")},
            )
            .execute()
        )
        return {
            "status": "reply_sent",
            "message_id": result.get("id", ""),
            "thread_id": result.get("threadId", ""),
            "to": recipients,
            "cc": cc_recipients,
            "subject": subject,
        }

    def archive_message(self, message_id: str) -> dict[str, str]:
        """Archive a Gmail message by removing it from the inbox."""
        return self._modify_labels(message_id, remove=["INBOX"], status="archived")

    def mark_message_read(self, message_id: str) -> dict[str, str]:
        """Mark a Gmail message as read."""
        return self._modify_labels(message_id, remove=["UNREAD"], status="read")

    def mark_message_unread(self, message_id: str) -> dict[str, str]:
        """Mark a Gmail message as unread."""
        return self._modify_labels(message_id, add=["UNREAD"], status="unread")

    def trash_message(self, message_id: str) -> dict[str, str]:
        """Move a Gmail message to Trash; this is reversible."""
        clean_id = self._validate_message_id(message_id)
        result = (
            self._get_service()
            .users()
            .messages()
            .trash(userId="me", id=clean_id)
            .execute()
        )
        return {"status": "moved_to_trash", "message_id": result.get("id", clean_id)}

    def restore_message(self, message_id: str) -> dict[str, str]:
        """Restore a Gmail message from Trash."""
        clean_id = self._validate_message_id(message_id)
        result = (
            self._get_service()
            .users()
            .messages()
            .untrash(userId="me", id=clean_id)
            .execute()
        )
        return {"status": "restored", "message_id": result.get("id", clean_id)}

    def bulk_manage_emails(
        self,
        query: str,
        action: str,
        max_messages: int = 50,
    ) -> dict[str, Any]:
        """Apply one reversible mailbox action to messages matching a query."""
        clean_query = query.strip()
        if len(clean_query) < 3:
            raise ValueError("Use a specific Gmail search query for bulk actions.")

        clean_action = action.strip().lower().replace("-", "_").replace(" ", "_")
        aliases = {
            "read": "mark_read",
            "unread": "mark_unread",
            "archive": "archive",
            "trash": "trash",
            "restore": "restore",
            "untrash": "restore",
            "mark_read": "mark_read",
            "mark_unread": "mark_unread",
        }
        normalized_action = aliases.get(clean_action)
        if normalized_action is None:
            raise ValueError(
                "Bulk action must be archive, mark_read, mark_unread, trash, "
                "or restore."
            )

        limit = max(1, min(int(max_messages), 100))
        message_ids = self._list_message_ids(
            clean_query,
            limit,
            include_spam_trash=normalized_action == "restore",
        )
        if not message_ids:
            return {
                "status": "no_matches",
                "action": normalized_action,
                "query": clean_query,
                "matched_count": 0,
                "changed_count": 0,
                "message_ids": [],
            }

        messages = self._get_service().users().messages()
        failures: list[dict[str, str]] = []
        if normalized_action in {"archive", "mark_read", "mark_unread"}:
            add_labels = ["UNREAD"] if normalized_action == "mark_unread" else []
            remove_labels = []
            if normalized_action == "archive":
                remove_labels.append("INBOX")
            elif normalized_action == "mark_read":
                remove_labels.append("UNREAD")
            messages.batchModify(
                userId="me",
                body={
                    "ids": message_ids,
                    "addLabelIds": add_labels,
                    "removeLabelIds": remove_labels,
                },
            ).execute()
        else:
            operation = messages.trash if normalized_action == "trash" else messages.untrash
            for message_id in message_ids:
                try:
                    operation(userId="me", id=message_id).execute()
                except Exception as exc:
                    failures.append(
                        {"message_id": message_id, "error": str(exc)}
                    )

        changed_count = len(message_ids) - len(failures)
        return {
            "status": "completed" if not failures else "partially_completed",
            "action": normalized_action,
            "query": clean_query,
            "matched_count": len(message_ids),
            "changed_count": changed_count,
            "failed_count": len(failures),
            "message_ids": message_ids,
            "failures": failures,
            "limit_reached": len(message_ids) == limit,
        }

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
        scopes = [GMAIL_MODIFY_SCOPE]
        token_has_scope = self._token_has_required_scope()
        if self.token_path.exists() and token_has_scope:
            credentials = Credentials.from_authorized_user_file(
                str(self.token_path), scopes
            )

        if credentials and credentials.expired and credentials.refresh_token:
            credentials.refresh(Request())
            self._save_token(credentials.to_json())

        if credentials and credentials.valid:
            return credentials

        if not allow_browser:
            if self.token_path.exists() and not token_has_scope:
                raise RuntimeError(
                    "Gmail permissions changed; click Reconnect Gmail"
                )
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

    def _token_has_required_scope(self) -> bool:
        if not self.token_path.exists():
            return False
        try:
            data = json.loads(self.token_path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return False
        granted = data.get("scopes", [])
        if isinstance(granted, str):
            granted = granted.split()
        return GMAIL_MODIFY_SCOPE in granted

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
        headers = self._headers(payload)
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

    def _list_message_ids(
        self,
        query: str,
        max_results: int,
        include_spam_trash: bool = False,
    ) -> list[str]:
        response = (
            self._get_service()
            .users()
            .messages()
            .list(
                userId="me",
                q=query,
                maxResults=max_results,
                includeSpamTrash=include_spam_trash,
            )
            .execute()
        )
        return [
            item["id"]
            for item in response.get("messages", [])
            if item.get("id")
        ]

    def _modify_labels(
        self,
        message_id: str,
        add: list[str] | None = None,
        remove: list[str] | None = None,
        status: str = "modified",
    ) -> dict[str, str]:
        clean_id = self._validate_message_id(message_id)
        result = (
            self._get_service()
            .users()
            .messages()
            .modify(
                userId="me",
                id=clean_id,
                body={
                    "addLabelIds": add or [],
                    "removeLabelIds": remove or [],
                },
            )
            .execute()
        )
        return {"status": status, "message_id": result.get("id", clean_id)}

    @classmethod
    def _build_raw_message(
        cls,
        to: str,
        subject: str,
        body: str,
        cc: str = "",
        bcc: str = "",
    ) -> str:
        message = EmailMessage()
        message["To"] = cls._validate_recipients(to, "To")
        if cc.strip():
            message["Cc"] = cls._validate_recipients(cc, "Cc")
        if bcc.strip():
            message["Bcc"] = cls._validate_recipients(bcc, "Bcc")
        message["Subject"] = cls._clean_header(subject, "subject")
        message.set_content(cls._clean_body(body))
        return base64.urlsafe_b64encode(message.as_bytes()).decode("ascii")

    @classmethod
    def _validate_recipients(cls, value: str, field: str) -> str:
        clean = cls._clean_header(value, field)
        addresses = getaddresses([clean])
        if not addresses or any("@" not in address for _, address in addresses):
            raise ValueError(f"{field} contains an invalid email address.")
        return clean

    @staticmethod
    def _clean_header(value: str, field: str) -> str:
        clean = value.strip()
        if not clean:
            raise ValueError(f"Email {field} cannot be empty.")
        if "\r" in clean or "\n" in clean:
            raise ValueError(f"Email {field} cannot contain line breaks.")
        return clean

    @staticmethod
    def _clean_body(value: str) -> str:
        clean = value.strip()
        if not clean:
            raise ValueError("Email body cannot be empty.")
        return clean

    @staticmethod
    def _validate_message_id(message_id: str) -> str:
        clean = message_id.strip()
        if not clean or not re.fullmatch(r"[A-Za-z0-9_-]+", clean):
            raise ValueError("A valid Gmail message ID is required.")
        return clean

    @staticmethod
    def _headers(payload: dict[str, Any]) -> dict[str, str]:
        return {
            item.get("name", "").lower(): item.get("value", "")
            for item in payload.get("headers", [])
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
