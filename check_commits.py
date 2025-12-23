# Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.
# SPDX-License-Identifier: BSD-3-Clause-Clear

import os
import sys
import requests
import argparse

api_base_url = "https://api.github.com"


def parse_arguments():
    parser = argparse.ArgumentParser(
        description="Validate commit messages in a GitHub PR."
    )
    parser.add_argument("--repo", required=True)
    parser.add_argument("--pr-number", required=True)
    parser.add_argument("--body-limit", type=int, default=72)
    parser.add_argument("--sub-limit", type=int, default=50)
    parser.add_argument("--check-blank-line", type=str, default="true")
    return parser.parse_args()


def fetch_commits(args):
    url = f"{api_base_url}/repos/{args.repo}/pulls/{args.pr_number}/commits"
    headers = {"Accept": "application/vnd.github.v3+json"}
    resp = requests.get(url, headers=headers, timeout=30)

    if resp.status_code in (401, 403, 404):
        token = os.getenv("GITHUB_TOKEN")
        if not token:
            print(
                "::error::Please set GITHUB_TOKEN as an environment variable to access private repositories!"
            )
            sys.exit(1)
        headers["Authorization"] = f"Bearer {token}"
        resp = requests.get(url, headers=headers, timeout=30)

    if resp.status_code != 200:
        print(
            f"::error::Failed to fetch PR commits: {resp.status_code} {resp.text[:300]}"
        )
        sys.exit(1)

    return resp.json()


def validate_commit_message(commit, sub_char_limit, body_char_limit, check_blank_line):
    sha = commit["sha"]
    message = commit["commit"]["message"]
    lines = message.splitlines()
    n = len(lines)

    subject = lines[0] if n >= 1 else ""
    body = [
        line.strip()
        for line in lines[1:]
        if line.strip() and not line.lower().startswith("signed-off-by")
    ]
    signed_off = lines[-1] if "signed-off-by" in lines[-1].lower() else ""
    missing_sub_body_line = False
    missing_body_sign_line = False

    if check_blank_line.lower() == "true":
        if n > 1 and lines[1].strip() != "":
            missing_sub_body_line = True
        else:
            body = [
                line.strip()
                for line in lines[2:]
                if line.strip() and not line.lower().startswith("signed-off-by")
            ]
        if signed_off and lines[-2].strip() != "":
            missing_body_sign_line = True

    errors = []
    if len(subject.strip()) == 0:
        errors.append("Commit message is missing subject!")
    if len(subject) > sub_char_limit:
        errors.append(f"Subject exceeds {sub_char_limit} characters!")
    if check_blank_line.lower() == "true":
        if missing_sub_body_line and subject and body:
            errors.append("Subject and body must be separated by a blank line")
        if missing_body_sign_line and body and signed_off:
            errors.append("Body and Signed-off-by must be separated by a blank line")
    if len(body) == 0:
        errors.append("Commit message is missing a body!")
    for line in body:
        if len(line) > body_char_limit:
            errors.append(f"Line exceeds {body_char_limit} characters: {line}")

    return sha, errors


def add_commit_comment(repo, sha, message):
    token = os.getenv("GITHUB_TOKEN")
    if not token:
        return
    url = f"{api_base_url}/repos/{repo}/commits/{sha}/comments"
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github.v3+json",
    }
    requests.post(url, headers=headers, json={"body": message})


def set_commit_status(repo, sha, state, description):
    token = os.getenv("GITHUB_TOKEN")
    if not token:
        return
    url = f"{api_base_url}/repos/{repo}/statuses/{sha}"
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github.v3+json",
    }
    data = {
        "state": state,
        "description": description,
        "context": "commit-message-check",
    }
    requests.post(url, headers=headers, json=data)


def process_commits(commits, repo, sub_limit, body_limit, check_blank_line):
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
            add_commit_comment(repo, sha, "\n".join(errors))
            set_commit_status(repo, sha, "failure", "Commit message validation failed")
            print("::endgroup::")
        else:
            print(f"✅ Commit {sha} passed all checks.")
            set_commit_status(repo, sha, "success", "Commit message validation passed")
    return failed_count


def main():
    args = parse_arguments()
    commits = fetch_commits(args)
    failed_count = process_commits(
        commits, args.repo, args.sub_limit, args.body_limit, args.check_blank_line
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
