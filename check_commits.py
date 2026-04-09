# Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.
# SPDX-License-Identifier: BSD-3-Clause-Clear

import os
import sys
import argparse
import subprocess

TRAILER_PREFIXES = (
    "signed-off-by:",
    "co-authored-by:",
    "reviewed-by:",
    "acked-by:",
    "tested-by:",
)


def parse_arguments():
    parser = argparse.ArgumentParser(
        description="Validate commit messages using local Git history (no API/token)."
    )
    parser.add_argument(
        "--base", required=True, help="Base SHA for the range (base..head)"
    )
    parser.add_argument(
        "--head", required=True, help="Head SHA for the range (or single ref)"
    )
    parser.add_argument("--body-limit", type=int, default=72)
    parser.add_argument("--sub-limit", type=int, default=50)
    parser.add_argument("--check-blank-line", type=str, default="true")
    return parser.parse_args()


def fetch_commits(base, head):
    """
    Fetch commits between base..head from local repository.
    Returns a list of dicts with 'sha' and 'message' keys.
    """
    if not head:
        print("::error::Tokenless mode requires --head (and usually --base).")
        sys.exit(2)

    rev_range = f"{base}..{head}" if base else head
    try:
        shas = (
            subprocess.check_output(
                ["git", "rev-list", "--no-merges", rev_range], text=True
            )
            .strip()
            .splitlines()
        )
        if not shas:
            return []
        output = subprocess.check_output(
            ["git", "show", "-s", "--format=%H%x00%B%x00"] + shas, text=True
        )
        commits = []
        parts = output.split("\x00")
        for i in range(0, len(parts) - 1, 2):
            sha = parts[i].strip()
            message = parts[i + 1] if i + 1 < len(parts) else ""
            if sha:
                commits.append({"sha": sha, "message": message})
        return commits

    except subprocess.CalledProcessError as e:
        print(f"::error::Failed to fetch commits with git: {e}")
        sys.exit(2)


def validate_subject(subject, sub_char_limit):
    """Validate the commit subject line."""
    errors = []
    if len(subject.strip()) == 0:
        errors.append("Commit message is missing subject!")
    if len(subject) > sub_char_limit:
        errors.append(f"Subject exceeds {sub_char_limit} characters!")
    return errors


def validate_body(lines, n, body_char_limit, check_blank_line):
    """Validate the commit body."""
    errors = []

    body_index = 1
    if check_blank_line.lower() == "true":
        # Check for blank line after subject
        if n > 1 and lines[1].strip() != "":
            errors.append("Subject and body must be separated by a blank line")
        body_index = 2
    body = [
        line.strip()
        for line in lines[body_index:n]
        if line.strip() and not line.lower().startswith(TRAILER_PREFIXES)
    ]
    if len(body) == 0:
        errors.append("Commit message is missing a body!")
    for line in body:
        if len(line) > body_char_limit:
            errors.append(f"Line exceeds {body_char_limit} characters: {line}")

    return errors, body


def validate_trailers(lines, body, check_blank_line):
    errors = []

    trailer_indices = [
        i for i, line in enumerate(lines) if line.lower().startswith(TRAILER_PREFIXES)
    ]

    first_trailer_index = 0
    if trailer_indices:
        first_trailer_index = trailer_indices[0]

    if check_blank_line.lower() == "true" and body:
        if first_trailer_index > 0 and lines[first_trailer_index - 1].strip() != "":
            errors.append("Body and trailers must be separated by a blank line")

    return errors


def validate_commit_message(commit, sub_char_limit, body_char_limit, check_blank_line):
    sha = commit["sha"]
    message = commit["message"]
    lines = message.splitlines()
    n = len(lines)
    subject = lines[0] if n >= 1 else ""

    errors = []
    subject_errors = validate_subject(subject, sub_char_limit)
    body_errors, body = validate_body(lines, n, body_char_limit, check_blank_line)
    trailer_errors = validate_trailers(lines, body, check_blank_line)

    errors.extend(subject_errors + body_errors + trailer_errors)

    return sha, errors


def process_commits(commits, sub_limit, body_limit, check_blank_line):
    failed_count = 0
    for commit in commits:
        sha, errors = validate_commit_message(
            commit, sub_limit, body_limit, check_blank_line
        )
        if errors:
            print(f"::group:: ❌ Errors in commit {sha}")
            failed_count += 1
            for err in errors:
                print(f"::error:: {err}")
            print("::endgroup::")
        else:
            print(f"✅ Commit {sha} passed all checks.")
    return failed_count


def main():
    args = parse_arguments()
    commits = fetch_commits(args.base, args.head)
    failed_count = process_commits(
        commits, args.sub_limit, args.body_limit, args.check_blank_line
    )

    summary_path = os.getenv("GITHUB_STEP_SUMMARY")
    if summary_path:
        with open(summary_path, "a") as f:
            f.write("### Commit Validation Summary\n")
            if failed_count:
                f.write(f"- ❌ {failed_count} commit(s) failed validation.\n")
            else:
                f.write("- ✅ All commits passed validation.\n")

    sys.exit(1 if failed_count else 0)


if __name__ == "__main__":
    main()
