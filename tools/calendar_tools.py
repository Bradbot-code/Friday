from __future__ import annotations

from datetime import date, datetime, time, timedelta
from email.utils import getaddresses
from typing import Any

from tools.gmail_tools import GmailTools


class CalendarTools:
    """Google Calendar event access using Friday's shared Google OAuth token."""

    def __init__(self, google_auth: GmailTools) -> None:
        self.google_auth = google_auth
        self._service = None

    def list_events(
        self,
        days: int = 1,
        start_date: str = "",
        max_results: int = 25,
    ) -> list[dict[str, Any]]:
        """List events from a local date through the requested number of days."""
        day = date.fromisoformat(start_date) if start_date.strip() else date.today()
        zone = datetime.now().astimezone().tzinfo
        start = datetime.combine(day, time.min, tzinfo=zone)
        end = start + timedelta(days=max(1, min(int(days), 31)))
        response = (
            self._get_service()
            .events()
            .list(
                calendarId="primary",
                timeMin=start.isoformat(),
                timeMax=end.isoformat(),
                maxResults=max(1, min(int(max_results), 100)),
                singleEvents=True,
                orderBy="startTime",
            )
            .execute()
        )
        return [self._summarize(event) for event in response.get("items", [])]

    def search_events(
        self,
        query: str,
        days: int = 90,
        max_results: int = 25,
    ) -> list[dict[str, Any]]:
        """Search upcoming primary-calendar events by text."""
        clean_query = query.strip()
        if not clean_query:
            raise ValueError("A calendar search query is required.")
        now = datetime.now().astimezone()
        response = (
            self._get_service()
            .events()
            .list(
                calendarId="primary",
                q=clean_query,
                timeMin=now.isoformat(),
                timeMax=(now + timedelta(days=max(1, min(int(days), 365)))).isoformat(),
                maxResults=max(1, min(int(max_results), 100)),
                singleEvents=True,
                orderBy="startTime",
            )
            .execute()
        )
        return [self._summarize(event) for event in response.get("items", [])]

    def create_event(
        self,
        title: str,
        start: str,
        end: str,
        description: str = "",
        location: str = "",
        attendees: str = "",
    ) -> dict[str, Any]:
        """Create an event on the primary calendar from ISO date-times."""
        start_value = self._parse_datetime(start)
        end_value = self._parse_datetime(end)
        if end_value <= start_value:
            raise ValueError("Calendar event end must be after its start.")
        event = {
            "summary": self._required(title, "title"),
            "start": {"dateTime": start_value.isoformat()},
            "end": {"dateTime": end_value.isoformat()},
        }
        if description.strip():
            event["description"] = description.strip()
        if location.strip():
            event["location"] = location.strip()
        attendee_list = self._attendees(attendees)
        if attendee_list:
            event["attendees"] = attendee_list
        result = (
            self._get_service()
            .events()
            .insert(
                calendarId="primary",
                body=event,
                sendUpdates="all" if attendee_list else "none",
            )
            .execute()
        )
        return self._summarize(result)

    def update_event(
        self,
        event_id: str,
        title: str = "",
        start: str = "",
        end: str = "",
        description: str = "",
        location: str = "",
    ) -> dict[str, Any]:
        """Update supplied fields on an existing primary-calendar event."""
        clean_id = self._required(event_id, "event ID")
        service = self._get_service().events()
        event = service.get(calendarId="primary", eventId=clean_id).execute()
        if title.strip():
            event["summary"] = title.strip()
        if start.strip():
            event["start"] = {"dateTime": self._parse_datetime(start).isoformat()}
        if end.strip():
            event["end"] = {"dateTime": self._parse_datetime(end).isoformat()}
        if description.strip():
            event["description"] = description.strip()
        if location.strip():
            event["location"] = location.strip()
        result = service.update(
            calendarId="primary",
            eventId=clean_id,
            body=event,
            sendUpdates="all" if event.get("attendees") else "none",
        ).execute()
        return self._summarize(result)

    def cancel_event(self, event_id: str) -> dict[str, str]:
        """Cancel an event on the primary calendar."""
        clean_id = self._required(event_id, "event ID")
        self._get_service().events().delete(
            calendarId="primary",
            eventId=clean_id,
            sendUpdates="all",
        ).execute()
        return {"status": "cancelled", "event_id": clean_id}

    def _get_service(self):
        if self._service is None:
            try:
                from googleapiclient.discovery import build
            except ImportError as exc:
                raise RuntimeError(
                    "Google libraries are not installed. Run: "
                    "pip install -r requirements.txt"
                ) from exc
            self._service = build(
                "calendar",
                "v3",
                credentials=self.google_auth.get_google_credentials(),
                cache_discovery=False,
            )
        return self._service

    @staticmethod
    def _parse_datetime(value: str) -> datetime:
        clean = value.strip().replace("Z", "+00:00")
        try:
            parsed = datetime.fromisoformat(clean)
        except ValueError as exc:
            raise ValueError(
                "Use an ISO date-time such as 2026-07-21T14:30:00-05:00."
            ) from exc
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=datetime.now().astimezone().tzinfo)
        return parsed

    @staticmethod
    def _attendees(value: str) -> list[dict[str, str]]:
        if not value.strip():
            return []
        addresses = [address for _, address in getaddresses([value])]
        if not addresses or any("@" not in address for address in addresses):
            raise ValueError("Attendees contains an invalid email address.")
        return [{"email": address} for address in addresses]

    @staticmethod
    def _required(value: str, name: str) -> str:
        clean = value.strip()
        if not clean:
            raise ValueError(f"Calendar {name} is required.")
        return clean

    @staticmethod
    def _summarize(event: dict[str, Any]) -> dict[str, Any]:
        return {
            "id": event.get("id", ""),
            "title": event.get("summary", "(untitled)"),
            "start": event.get("start", {}).get("dateTime", event.get("start", {}).get("date", "")),
            "end": event.get("end", {}).get("dateTime", event.get("end", {}).get("date", "")),
            "location": event.get("location", ""),
            "description": event.get("description", "")[:2000],
            "status": event.get("status", ""),
            "link": event.get("htmlLink", ""),
            "attendees": [item.get("email", "") for item in event.get("attendees", [])],
        }
