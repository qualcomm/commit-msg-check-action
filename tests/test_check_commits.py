# Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.
# SPDX-License-Identifier: BSD-3-Clause-Clear

import os
import sys
import unittest
from io import StringIO
from unittest.mock import patch
from contextlib import redirect_stdout

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
import check_commits


class TestCommitCheck(unittest.TestCase):
    def setUp(self):
        self.sample_commit_valid = {
            "sha": "abc123",
            "commit": {
                "message": (
                    "Valid subject\n\n"
                    "This is a valid description line.\n"
                    "It continues here.\n\n"
                    "Signed-off-by: Developer <dev@example.com>"
                )
            },
        }

    def test_parse_arguments_with_base_head(self):
        argv = [
            "check_commits.py",
            "--base",
            "1111111",
            "--head",
            "2222222",
            "--body-limit",
            "72",
            "--sub-limit",
            "50",
            "--check-blank-line",
            "true",
        ]
        with patch.object(sys, "argv", argv):
            args = check_commits.parse_arguments()
        self.assertEqual(args.base, "1111111")
        self.assertEqual(args.head, "2222222")
        self.assertEqual(args.body_limit, 72)
        self.assertEqual(args.sub_limit, 50)
        self.assertEqual(args.check_blank_line, "true")

    def test_validate_commit_message_valid(self):
        sha, errors = check_commits.validate_commit_message(
            self.sample_commit_valid,
            sub_char_limit=50,
            body_char_limit=72,
            check_blank_line="true",
        )
        self.assertEqual(sha, "abc123")
        self.assertEqual(errors, [])

    def test_validate_commit_message_subject_too_long_no_blank_check(self):
        commit = {
            "sha": "def456",
            "commit": {
                "message": (
                    "This subject line is way too long and should definitely fail the check\n"
                    "Body line.\n\n"
                    "Signed-off-by: Developer <dev@example.com>"
                )
            },
        }
        _sha, errors = check_commits.validate_commit_message(
            commit, sub_char_limit=50, body_char_limit=72, check_blank_line="false"
        )
        self.assertIn("Subject exceeds 50 characters!", errors)
        self.assertTrue(
            all(
                "Subject and body must be separated by a blank line" not in e
                for e in errors
            )
        )

    def test_validate_commit_message_subject_too_long_with_blank_check(self):
        commit = {
            "sha": "def456",
            "commit": {
                "message": (
                    "This subject line is way too long and should definitely fail the check\n"
                    "Body line without blank separator\n\n"
                    "Signed-off-by: Developer <dev@example.com>"
                )
            },
        }
        _sha, errors = check_commits.validate_commit_message(
            commit, sub_char_limit=50, body_char_limit=72, check_blank_line="true"
        )
        self.assertIn("Subject exceeds 50 characters!", errors)
        self.assertIn("Subject and body must be separated by a blank line", errors)

    def test_process_commits_all_valid_prints_and_returns_zero(self):
        commits = [self.sample_commit_valid]
        buf = StringIO()
        with redirect_stdout(buf):
            failed = check_commits.process_commits(
                commits, sub_limit=50, body_limit=72, check_blank_line="true"
            )
        out = buf.getvalue()
        self.assertEqual(failed, 0)
        self.assertIn("✅ Commit abc123 passed all checks.", out)

    def test_process_commits_mixed_failures(self):
        bad_commit = {
            "sha": "bad999",
            "commit": {
                "message": (
                    "Bad subject with excessive length that violates the rule right away\n"
                    "Body line\n"
                )
            },
        }
        commits = [self.sample_commit_valid, bad_commit]
        buf = StringIO()
        with redirect_stdout(buf):
            failed = check_commits.process_commits(
                commits, sub_limit=50, body_limit=72, check_blank_line="true"
            )
        out = buf.getvalue()
        self.assertEqual(failed, 1)
        self.assertIn("❌ Errors in commit bad999", out)
        self.assertIn("Subject exceeds 50 characters!", out)


if __name__ == "__main__":
    unittest.main()
