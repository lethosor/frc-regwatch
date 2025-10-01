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
    now = datetime.datetime.now(datetime.UTC)

    clients = {
        "tba": download.TBAClient,
        "frc": download.FRCClient,
        "dummy": download.DummyClient,
    }

    repo = git.Repo(os.path.abspath(__file__), search_parent_directories=True)
    parser = argparse.ArgumentParser()
    parser.add_argument("--client", choices=clients.keys(), required=True)
    parser.add_argument("--year", type=int, required=True)
    parser.add_argument("--target-repo-root", default=".")
    parser.add_argument("--target-repo-branch", help="default: data-{client}")
    parser.add_argument("--target-repo-subdir", help="default: data/{year}")
    parser.add_argument("--target-repo-remote", default="origin")
    parser.add_argument("--no-pull", action="store_true")
    args = parser.parse_args()

    if args.target_repo_branch is None:
        args.target_repo_branch = f"data-{args.client}"
    if args.target_repo_subdir is None:
        args.target_repo_subdir = f"data/{args.year}"

    repo = git.Repo(args.target_repo_root)

    remote = repo.remotes[args.target_repo_remote]
    branch_name = args.target_repo_branch
    if not args.no_pull:
        print(f"Pulling branch {args.target_repo_remote}/{branch_name}")
        remote.fetch()
        if branch_name in remote.refs:
            remote.pull(f"{branch_name}:{branch_name}")
        else:
            print(f"Branch {branch_name!r} does not exist on remote - will be created")

    client = clients[args.client]()
    event_teams = client.get_all_event_teams(year=args.year)
    file_contents = event_teams_to_files(event_teams)
    git_util.ensure_branch(repo=repo, branch=branch_name)
    git_util.commit_subdir_contents(
        repo=repo,
        branch=branch_name,
        subdir=args.target_repo_subdir,
        files=file_contents,
        message=f"{args.year} event teams at " + now.strftime("%Y-%m-%d-%H%MZ"),
        author=("frc-regwatch", "frc-regwatch"),
        author_date=now,
    )


if __name__ == "__main__":
    main()
