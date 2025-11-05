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

    subject = lines[0] if n >= 1 else ""
    description = [
        line.strip()
        for line in lines[1:]
        if line.strip() != "" and not line.lower().startswith("signed-off-by")
    ]
    signed_off = lines[-1] if n >= 1 and "Signed-off-by" in lines[-1] else ""
    missing_sub_desc_line = False
    missing_desc_sign_line = False

    if check_blank_line.lower() == "true":
        if n > 1 and lines[1].strip() != "":
            missing_sub_desc_line = True
        else:
            description = [
                line.strip()
                for line in lines[2:]
                if line.strip() != "" and not line.lower().startswith("signed-off-by")
            ]

        if signed_off and lines[-2].strip() != "":
            missing_desc_sign_line = True

    errors = []

    # Validate subject
    if len(subject.strip()) == 0:
        errors.append("Commit message is missing subject!")
    if len(subject) > sub_char_limit:
        errors.append(f"Subject exceeds {sub_char_limit} characters!")

    # Blank line check
    if check_blank_line.lower() == "true":
        if missing_sub_desc_line and subject and description:
            errors.append(
                "Commit subject and description must be separated by a blank line"
            )

        if missing_desc_sign_line and description and signed_off:
            errors.append(
                "Commit description and Signed-off-by must be separated by a blank line"
            )

    # Validate description
    if len(description) == 0:
        errors.append("Commit message is missing description!")

    # Word wrap check
    for line in description:
        if len(line) > desc_char_limit:
            errors.append(
                f"The following line in the commit description exceeds {desc_char_limit} characters: {line}"
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
