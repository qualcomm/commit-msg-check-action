# Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.
# SPDX-License-Identifier: BSD-3-Clause-Clear

import os
import sys
import requests
import argparse


def parse_arguments():
    parser = argparse.ArgumentParser(
        description="Validate commit messages in a GitHub PR."
    )
    parser.add_argument("--repo", required=True)
    parser.add_argument("--pr-number", required=True)
    parser.add_argument("--desc-limit", type=int, default=72)
    parser.add_argument("--sub-limit", type=int, default=50)
    parser.add_argument("--check-blank-line", type=str, default="true")
    args = parser.parse_args()
    return args


def fetch_commits(args):
    token = os.getenv("GITHUB_TOKEN")
    if token:
        url = f"https://api.github.com/repos/{args.repo}/pulls/{args.pr_number}/commits"
        headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github.v3+json",
        }
        response = requests.get(url, headers=headers)
        if response.status_code != 200:
            print(
                f"❌ Failed to fetch PR commits: {response.status_code} {response.text}"
            )
            sys.exit(1)
        return response.json()
    else:
        print(f"❌ No token found to fetch the commits! : {token}")
        sys.exit(1)


def validate_commit_message(commit, sub_char_limit, desc_char_limit, check_blank_line):
    sha = commit["sha"]
    message = commit["commit"]["message"]
    lines = message.splitlines()
    n = len(lines)

    signed_off = lines[-1] if n >= 1 else ""
    subject = lines[0] if n >= 1 else ""
    description = lines[2:-1] if n >= 3 else []

    errors = []

    # validate if commit message exists
    if len(subject) == 0:
        errors.append("Commit message is missing subject!")
    # validate if description exists
    if len(description) == 0:
        errors.append("Commit message is missing description!")
    # validate the length of the subject
    if len(subject) > sub_char_limit:
        errors.append(f"Subject exceeds {sub_char_limit} characters!")
    # validate word wrap limit of description
    for line in description:
        if len(line) > desc_char_limit:
            errors.append(
                f"The following line in the commit description exceeds the maximum allowed length of {desc_char_limit} characters: {line}"
            )
    # check for blank line between subject and description
    if description and check_blank_line.lower() == "true":
        if n > 1 and lines[1].strip() != "":
            errors.append(
                "Commit subject and description must be separated by a blank line"
            )
    # check for blank line between description and signed-off-by signature
    if description and (
        description[-1] != "" or not signed_off.lower().startswith("signed-off-by")
    ):
        errors.append(
            "Commit description and Signed-off-by must be separated by a blank line"
        )

    return sha, errors


def process_commits(commits, sub_limit, desc_limit, check_blank_line):
    failed_count = 0

    for commit in commits:
        sha, errors = validate_commit_message(
            commit, sub_limit, desc_limit, check_blank_line
        )
        if errors:
            failed_count += 1
            print(f"\n❌ Commit {sha} failed checks:")
            print("   - " + "\n   - ".join(errors))
        else:
            print(f"✅ Commit {sha} passed all checks.")

    return failed_count


def main():
    args = parse_arguments()
    commits = fetch_commits(args)
    failed_count = process_commits(
        commits, args.sub_limit, args.desc_limit, args.check_blank_line
    )
    if failed_count:
        print(f"\n❌ {failed_count} commit(s) failed validation.")
        sys.exit(1)
    else:
        print("\n✅ All commits passed validation.")
        sys.exit(0)


if __name__ == "__main__":
    main()
