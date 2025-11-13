# Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.
# SPDX-License-Identifier: BSD-3-Clause-Clear

import os
import sys
import requests
import argparse

def parse_arguments():
    parser = argparse.ArgumentParser(description="Validate commit messages in a GitHub PR.")
    parser.add_argument("--repo", required=True)
    parser.add_argument("--pr-number", required=True)
    parser.add_argument("--desc-limit", type=int, default=72)
    parser.add_argument("--sub-limit", type=int, default=50)
    parser.add_argument("--check-blank-line", type=str, default="true")
    return parser.parse_args()

def fetch_commits(args):
    token = os.getenv("GITHUB_TOKEN")
    if not token:
        print("::error::No GITHUB_TOKEN found!")
        sys.exit(1)

    url = f"https://api.github.com/repos/{args.repo}/pulls/{args.pr_number}/commits"
    headers = {"Authorization": f"Bearer {token}", "Accept": "application/vnd.github.v3+json"}
    response = requests.get(url, headers=headers)

    if response.status_code != 200:
        print(f"::error::Failed to fetch PR commits: {response.status_code} {response.text}")
        sys.exit(1)

    return response.json()

def validate_commit_message(commit, sub_char_limit, desc_char_limit, check_blank_line):
    sha = commit["sha"]
    message = commit["commit"]["message"]
    lines = message.splitlines()
    n = len(lines)

    subject = lines[0] if n >= 1 else ""
    description = [line.strip() for line in lines[1:] if line.strip() and not line.lower().startswith("signed-off-by")]
    signed_off = lines[-1] if "Signed-off-by" in lines[-1] else ""
    missing_sub_desc_line = False
    missing_desc_sign_line = False

    if check_blank_line.lower() == "true":
        if n > 1 and lines[1].strip() != "":
            missing_sub_desc_line = True
        else:
            description = [line.strip() for line in lines[2:] if line.strip() and not line.lower().startswith("signed-off-by")]
        if signed_off and lines[-2].strip() != "":
            missing_desc_sign_line = True

    errors = []
    if len(subject.strip()) == 0:
        errors.append("Commit message is missing subject!")
    if len(subject) > sub_char_limit:
        errors.append(f"Subject exceeds {sub_char_limit} characters!")
    if check_blank_line.lower() == "true":
        if missing_sub_desc_line and subject and description:
            errors.append("Subject and description must be separated by a blank line")
        if missing_desc_sign_line and description and signed_off:
            errors.append("Description and Signed-off-by must be separated by a blank line")
    if len(description) == 0:
        errors.append("Commit message is missing description!")
    for line in description:
        if len(line) > desc_char_limit:
            errors.append(f"Line exceeds {desc_char_limit} characters: {line}")

    return sha, errors

def add_commit_comment(repo, sha, message):
    token = os.getenv("GITHUB_TOKEN")
    if not token:
        return
    url = f"https://api.github.com/repos/{repo}/commits/{sha}/comments"
    headers = {"Authorization": f"Bearer {token}", "Accept": "application/vnd.github.v3+json"}
    requests.post(url, headers=headers, json={"body": message})

def set_commit_status(repo, sha, state, description):
    token = os.getenv("GITHUB_TOKEN")
    if not token:
        return
    url = f"https://api.github.com/repos/{repo}/statuses/{sha}"
    headers = {"Authorization": f"Bearer {token}", "Accept": "application/vnd.github.v3+json"}
    data = {"state": state, "description": description, "context": "commit-message-check"}
    requests.post(url, headers=headers, json=data)

def process_commits(commits, repo, sub_limit, desc_limit, check_blank_line):
    failed_count = 0
    for commit in commits:
        sha, errors = validate_commit_message(commit, sub_limit, desc_limit, check_blank_line)
        print(f"::group:: ❌ Errors in commit {sha}")
        if errors:
            failed_count += 1
            for err in errors:
                print(f"::error file=check_commits.py:: {err}")
            add_commit_comment(repo, sha, "\n".join(errors))
            set_commit_status(repo, sha, "failure", "Commit message validation failed")
        else:
            print(f"✅ Commit {sha} passed all checks.")
            set_commit_status(repo, sha, "success", "Commit message validation passed")
        print("::endgroup::")
    return failed_count

def main():
    args = parse_arguments()
    commits = fetch_commits(args)
    failed_count = process_commits(commits, args.repo, args.sub_limit, args.desc_limit, args.check_blank_line)

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
