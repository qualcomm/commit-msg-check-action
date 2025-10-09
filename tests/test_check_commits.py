# Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.
# SPDX-License-Identifier: BSD-3-Clause-Clear

import unittest
from unittest.mock import patch, MagicMock
from io import StringIO
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
import check_commits


class TestCheckCommits(unittest.TestCase):

    def setUp(self):
        self.sample_commit = {
            "sha": "abc123",
            "commit": {
                "message": (
                    "Valid subject\n\n"
                    "This is a valid description line.\n"
                    "It continues here.\n\n"
                    "Signed-off-by: Developer <dev@example.com>"
                )
            }
        }

    @patch('check_commits.parse_arguments')
    def test_parse_arguments(self, mock_parse_args):
        mock_args = MagicMock()
        mock_args.repo = "test/repo"
        mock_args.pr_number = "123"
        mock_args.desc_limit = 72
        mock_args.sub_limit = 50
        mock_args.check_blank_line = "true"
        mock_parse_args.return_value = mock_args

        args = check_commits.parse_arguments()

        self.assertEqual(args.repo, "test/repo")
        self.assertEqual(args.pr_number, "123")
        self.assertEqual(args.desc_limit, 72)
        self.assertEqual(args.sub_limit, 50)
        self.assertEqual(args.check_blank_line, "true")

    @patch('check_commits.requests.get')
    @patch('os.getenv')
    def test_fetch_commits_success(self, mock_getenv, mock_get):
        mock_getenv.return_value = "fake_token"
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = [self.sample_commit]
        mock_get.return_value = mock_response

        args = MagicMock()
        args.repo = "test/repo"
        args.pr_number = "123"

        result = check_commits.fetch_commits(args)

        self.assertEqual(result, [self.sample_commit])
        mock_get.assert_called_once()

    def test_validate_commit_message_valid(self):
        sha, errors = check_commits.validate_commit_message(
            self.sample_commit, 50, 72, check_blank_line="true"
        )
        self.assertEqual(sha, "abc123")
        self.assertEqual(errors, [])

    @patch('sys.stdout', new_callable=StringIO)
    def test_process_commits_all_valid(self, mock_stdout):
        commits = [self.sample_commit]
        failed_count = check_commits.process_commits(
            commits, 50, 72, check_blank_line="true"
        )
        self.assertEqual(failed_count, 0)
        self.assertIn("✅ Commit abc123 passed all checks", mock_stdout.getvalue())

    def test_validate_commit_message_subject_too_long(self):
        commit = {
            "sha": "def456",
            "commit": {
                "message": (
                    "This subject line is way too long and should definitely fail the check\n"
                    "Valid description line.\n\n"
                    "Signed-off-by: Developer <dev@example.com>"
                )
            }
        }
        sha, errors = check_commits.validate_commit_message(commit, 50, 72, check_blank_line="false") # check_blank_line is set to false
        self.assertIn("Subject exceeds 50 characters!", errors)
        self.assertIsNot("Commit subject and description must be separated by a blank line",errors)
    
    def test_validate_commit_message_subject_too_long_and_check_blank_line(self):
        commit = {
            "sha": "def456",
            "commit": {
                "message": (
                    "This subject line is way too long and should definitely fail the check\n"
                    "Valid description line.\n\n"
                    "Signed-off-by: Developer <dev@example.com>"
                )
            }
        }
        sha, errors = check_commits.validate_commit_message(commit, 50, 72, check_blank_line="true") # check_blank_line is set to true
        self.assertIn("Subject exceeds 50 characters!", errors)
        self.assertIn("Commit subject and description must be separated by a blank line",errors)


if __name__ == "__main__":
    unittest.main()
