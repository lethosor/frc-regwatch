import argparse
import os

import git


def main():
    repo = git.Repo(os.path.abspath(__file__), search_parent_directories=True)
    parser = argparse.ArgumentParser()
    args = parser.parse_args()


if __name__ == "__main__":
    main()
