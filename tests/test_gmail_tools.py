from __future__ import annotations

import base64
import json
import tempfile
import unittest
from email import message_from_bytes
from pathlib import Path

from tools.gmail_tools import GMAIL_MODIFY_SCOPE, GmailTools


class _Request:
    def __init__(self, result):
        self.result = result

    def execute(self):
        return self.result


class _Messages:
    def __init__(self):
        self.calls = []

    def send(self, **kwargs):
        self.calls.append(("send", kwargs))
        return _Request({"id": "sent1", "threadId": "thread1"})

    def get(self, **kwargs):
        self.calls.append(("get", kwargs))
        return _Request(
            {
                "id": kwargs["id"],
                "threadId": "thread1",
                "payload": {
                    "headers": [
                        {"name": "From", "value": "Sender <sender@example.com>"},
                        {"name": "To", "value": "owner@example.com"},
                        {"name": "Subject", "value": "A question"},
                        {"name": "Message-ID", "value": "<original@example.com>"},
                    ]
                },
            }
        )

    def list(self, **kwargs):
        self.calls.append(("list", kwargs))
        return _Request(
            {"messages": [{"id": "one"}, {"id": "two"}, {"id": "three"}]}
        )

    def batchModify(self, **kwargs):
        self.calls.append(("batchModify", kwargs))
        return _Request({})

    def modify(self, **kwargs):
        self.calls.append(("modify", kwargs))
        return _Request({"id": kwargs["id"]})

    def trash(self, **kwargs):
        self.calls.append(("trash", kwargs))
        return _Request({"id": kwargs["id"]})

    def untrash(self, **kwargs):
        self.calls.append(("untrash", kwargs))
        return _Request({"id": kwargs["id"]})


class _Drafts:
    def __init__(self):
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(("create", kwargs))
        return _Request({"id": "draft1", "message": {"id": "message1"}})


class _Users:
    def __init__(self):
        self.message_resource = _Messages()
        self.draft_resource = _Drafts()

    def messages(self):
        return self.message_resource

    def drafts(self):
        return self.draft_resource

    def getProfile(self, **kwargs):
        return _Request({"emailAddress": "owner@example.com"})


class _Service:
    def __init__(self):
        self.user_resource = _Users()

    def users(self):
        return self.user_resource


class GmailModificationTests(unittest.TestCase):
    def setUp(self):
        self.gmail = GmailTools()
        self.service = _Service()
        self.gmail._service = self.service

    def test_build_message_validates_and_encodes_fields(self):
        raw = self.gmail._build_raw_message(
            "person@example.com",
            "Friday test",
            "Hello from Friday.",
            "copy@example.com",
        )
        parsed = message_from_bytes(base64.urlsafe_b64decode(raw))
        self.assertEqual(parsed["To"], "person@example.com")
        self.assertEqual(parsed["Cc"], "copy@example.com")
        self.assertEqual(parsed["Subject"], "Friday test")
        self.assertIn("Hello from Friday.", parsed.get_payload())

    def test_send_and_draft_return_receipts(self):
        sent = self.gmail.send_email(
            "person@example.com", "Subject", "Message"
        )
        draft = self.gmail.create_draft(
            "person@example.com", "Subject", "Message"
        )
        self.assertEqual(sent["status"], "sent")
        self.assertEqual(draft["status"], "draft_created")

    def test_mailbox_changes_are_reversible_operations(self):
        self.assertEqual(
            self.gmail.archive_message("abc123")["status"], "archived"
        )
        self.assertEqual(
            self.gmail.mark_message_read("abc123")["status"], "read"
        )
        self.assertEqual(
            self.gmail.mark_message_unread("abc123")["status"], "unread"
        )
        self.assertEqual(
            self.gmail.trash_message("abc123")["status"], "moved_to_trash"
        )
        self.assertEqual(
            self.gmail.restore_message("abc123")["status"], "restored"
        )

    def test_reply_stays_in_original_thread(self):
        result = self.gmail.reply_to_email("abc123", "Here is my answer.")
        self.assertEqual(result["status"], "reply_sent")
        self.assertEqual(result["thread_id"], "thread1")
        send_call = self.service.user_resource.message_resource.calls[-1]
        self.assertEqual(send_call[1]["body"]["threadId"], "thread1")

    def test_bulk_archive_uses_one_batch_request(self):
        result = self.gmail.bulk_manage_emails(
            "category:promotions older_than:30d",
            "archive",
        )
        self.assertEqual(result["changed_count"], 3)
        calls = self.service.user_resource.message_resource.calls
        batch_calls = [call for call in calls if call[0] == "batchModify"]
        self.assertEqual(len(batch_calls), 1)
        self.assertEqual(
            batch_calls[0][1]["body"]["removeLabelIds"], ["INBOX"]
        )

    def test_bulk_trash_reports_all_changed_messages(self):
        result = self.gmail.bulk_manage_emails(
            "from:newsletter@example.com",
            "trash",
            max_messages=10,
        )
        self.assertEqual(result["status"], "completed")
        self.assertEqual(result["changed_count"], 3)
        calls = self.service.user_resource.message_resource.calls
        self.assertEqual(len([call for call in calls if call[0] == "trash"]), 3)

    def test_bulk_restore_searches_trash(self):
        self.gmail.bulk_manage_emails("in:trash from:example.com", "restore")
        list_call = self.service.user_resource.message_resource.calls[0]
        self.assertTrue(list_call[1]["includeSpamTrash"])

    def test_bulk_action_rejects_unknown_or_broad_input(self):
        with self.assertRaises(ValueError):
            self.gmail.bulk_manage_emails("x", "archive")
        with self.assertRaises(ValueError):
            self.gmail.bulk_manage_emails("from:example.com", "permanent_delete")

    def test_old_readonly_token_requires_reauthorization(self):
        with tempfile.TemporaryDirectory() as folder:
            token_path = Path(folder) / "token.json"
            gmail = GmailTools(token_path=token_path)
            token_path.write_text(
                json.dumps(
                    {
                        "scopes": [
                            "https://www.googleapis.com/auth/gmail.readonly"
                        ]
                    }
                ),
                encoding="utf-8",
            )
            self.assertFalse(gmail._token_has_required_scope())
            token_path.write_text(
                json.dumps({"scopes": [GMAIL_MODIFY_SCOPE]}),
                encoding="utf-8",
            )
            self.assertTrue(gmail._token_has_required_scope())


if __name__ == "__main__":
    unittest.main()
