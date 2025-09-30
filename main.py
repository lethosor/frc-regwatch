import argparse
import datetime
import os

import git

import download
import git_util


def event_teams_to_files(
    event_teams: dict[str, list[int]],
) -> dict[str, str]:
    out = {}
    for event_key, teams in event_teams.items():
        out[f"{event_key}.teams.txt"] = git_util.GitFileContents(
            data="".join(f"{t}\n" for t in teams)
        )
    return out


def main():
    now = datetime.datetime.now()

    clients = {
        "tba": download.TBAClient,
        "dummy": download.DummyClient,
    }

    repo = git.Repo(os.path.abspath(__file__), search_parent_directories=True)
    parser = argparse.ArgumentParser()
    parser.add_argument("--client", choices=clients.keys(), required=True)
    parser.add_argument("--year", type=int, required=True)
    parser.add_argument("--target-repo-root", default=".")
    parser.add_argument("--target-repo-branch", help="default: data-{client}")
    parser.add_argument("--target-repo-subdir", help="default: data/{year}")
    args = parser.parse_args()

    if args.target_repo_branch is None:
        args.target_repo_branch = f"data-{args.client}"
    if args.target_repo_subdir is None:
        args.target_repo_subdir = f"data/{args.year}"

    repo = git.Repo(args.target_repo_root)

    client = clients[args.client]()
    event_teams = client.get_all_event_teams(year=args.year)
    file_contents = event_teams_to_files(event_teams)
    git_util.ensure_branch(repo=repo, branch=args.target_repo_branch)
    git_util.commit_subdir_contents(
        repo=repo,
        branch=args.target_repo_branch,
        subdir=args.target_repo_subdir,
        files=file_contents,
        message=f"{args.year} event teams at " + now.strftime("%Y-%m-%d-%H%M"),
        author=("frc-regwatch", "frc-regwatch"),
        author_date=now,
    )


if __name__ == "__main__":
    main()
