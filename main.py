import argparse
import os

import git

import download
import git_util


def main():
    clients = {
        "tba": download.TBAClient,
        "dummy": download.DummyClient,
    }

    repo = git.Repo(os.path.abspath(__file__), search_parent_directories=True)
    parser = argparse.ArgumentParser()
    parser.add_argument("--client", choices=clients.keys(), required=True)
    parser.add_argument("--year", type=int, required=True)
    args = parser.parse_args()

    client = clients[args.client]()
    print(client.get_all_event_teams(year=args.year))


if __name__ == "__main__":
    main()
