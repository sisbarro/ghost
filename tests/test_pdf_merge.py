import base64
import unittest
from unittest.mock import patch

import app


class _RecordingProvider:
    def __init__(self):
        self.calls = []

    def send(self, *args, **kwargs):
        self.calls.append((args, kwargs))


class PdfMailMergeTests(unittest.TestCase):
    def setUp(self):
        self.config = {
            "enabled": True,
            "filename": "Invoice-{{First_Name}}.pdf",
            "html_content": "<h1>Hello {{First_Name}}</h1><p>Account: <b>{{Account}}</b></p>",
        }

    def test_render_pdf_attachment_merges_filename_and_content(self):
        ada = app.render_pdf_attachment(self.config, {"First_Name": "Ada", "Account": "A-101"})
        grace = app.render_pdf_attachment(self.config, {"First_Name": "Grace", "Account": "G-202"})

        self.assertEqual(ada["filename"], "Invoice-Ada.pdf")
        self.assertEqual(grace["filename"], "Invoice-Grace.pdf")
        self.assertTrue(base64.b64decode(ada["content"]).startswith(b"%PDF-"))
        self.assertNotEqual(ada["content"], grace["content"])

    def test_bulk_worker_adds_pdf_without_mutating_common_attachments(self):
        provider = _RecordingProvider()
        common = [{"filename": "terms.txt", "content": "dGVybXM="}]
        recipient = {"Email": "ada@example.com", "First_Name": "Ada", "Account": "A-101"}

        with (
            patch.object(app, "create_provider", return_value=provider),
            patch.object(app, "get_job", return_value={"status": "running"}),
            patch.object(app, "update_job"),
            patch.object(app, "complete_job"),
        ):
            app._bulk_send_worker(
                "test-job",
                [recipient],
                "Hello {{First_Name}}",
                "<p>Hi {{First_Name}}</p>",
                1,
                common,
                "sender@example.com",
                "Sender",
                "resend",
                "test-key",
                self.config,
            )

        self.assertEqual(len(provider.calls), 1)
        attachments = provider.calls[0][1]["attachments"]
        self.assertEqual([item["filename"] for item in attachments], ["terms.txt", "Invoice-Ada.pdf"])
        self.assertEqual(common, [{"filename": "terms.txt", "content": "dGVybXM="}])


if __name__ == "__main__":
    unittest.main()