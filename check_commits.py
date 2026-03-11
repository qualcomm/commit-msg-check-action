# Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.
# SPDX-License-Identifier: BSD-3-Clause-Clear

import os
import sys
import argparse
import subprocess


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


def fetch_commit_sha(base, head):
    """
    Build a list of commits between base..head (or at head if base is omitted)
    by reading the local repository. The returned objects mirror the minimal
    shape used elsewhere: {'sha': <sha>, 'commit': {'message': <str>}}.
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
    except subprocess.CalledProcessError as e:
        print(f"::error::Failed to enumerate commits with git: {e}")
        sys.exit(2)

    return shas


def get_commit_msgs(shas):
    commits = []
    for sha in shas:
        try:
            msg = subprocess.check_output(
                ["git", "show", "-s", "--format=%B", sha], text=True
            )
        except subprocess.CalledProcessError as e:
            print(f"::warning::Failed to read commit message for {sha}: {e}")
            msg = ""
        commits.append({"sha": sha, "message": msg})
    return commits


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
        if line.strip() and not line.lower().startswith("signed-off-by")
    ]
    if len(body) == 0:
        errors.append("Commit message is missing a body!")
    for line in body:
        if len(line) > body_char_limit:
            errors.append(f"Line exceeds {body_char_limit} characters: {line}")

    return errors, body


def validate_signoff(lines, n, body, check_blank_line):
    """Validate the Signed-off-by line."""
    errors = []

    signed_off = lines[-1] if n > 0 and "signed-off-by" in lines[-1].lower() else ""

    if check_blank_line.lower() == "true" and body and signed_off:
        if n >= 2 and lines[-2].strip() != "":
            errors.append("Body and Signed-off-by must be separated by a blank line")

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
    signed_off_errors = validate_signoff(lines, n, body, check_blank_line)

    errors.extend(subject_errors + body_errors + signed_off_errors)

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
    shas = fetch_commit_sha(args.base, args.head)
    commits = get_commit_msgs(shas)

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
