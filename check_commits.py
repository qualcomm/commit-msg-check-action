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
    args = parser.parse_args()
    return args


def fetch_commits(args):
    token = os.getenv("GITHUB_TOKEN")
    if token:
        url = f"https://api.github.com/repos/{args.repo}/pulls/{args.pr_number}/commits"
        headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github.v3+json"
        }
        response = requests.get(url, headers=headers)
        if response.status_code != 200:
            print(f"❌ Failed to fetch PR commits: {response.status_code} {response.text}")
            sys.exit(1)
        return response.json()
    else:
        print(f"❌ No token found to fetch the commits! : {token}")
        sys.exit(1)


def validate_commit_message(commit, sub_char_limit, desc_char_limit):
    sha = commit['sha']
    message = commit['commit']['message']
    lines = message.splitlines()
    subject = lines[0] if len(lines) >= 1 else ""
    description = lines[1:] if len(lines) >= 2 else []

    errors = []

    if len(subject) == 0:
        errors.append("Commit message is missing subject!")
    if len(description) == 0:
        errors.append("Commit message is missing description!")
    if len(subject) > sub_char_limit:
        errors.append(f"Subject exceeds {sub_char_limit} characters.")
    for line in description:
        if len(line) > desc_char_limit:
            errors.append(f"Line in description: {line} , exceeds maximum limit of {desc_char_limit} characters")

    return sha, errors


def process_commits(commits, sub_limit, desc_limit):
    failed_count = 0

    for commit in commits:
        sha, errors = validate_commit_message(commit, sub_limit, desc_limit)
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
    failed_count = process_commits(commits, args.sub_limit, args.desc_limit)

    if failed_count:
        print(f"\n❌ {failed_count} commit(s) failed validation.")
        sys.exit(1)
    else:
        print("\n✅ All commits passed validation.")
        sys.exit(0)


if __name__ == "__main__":
    main()
