import argparse
import concurrent.futures
import contextlib
import dataclasses
import datetime
import fnmatch
import gzip
import io
import os
import re
import struct
import time
import tomllib
from dataclasses import dataclass

import git

TEAM_LIST_FILENAME_PATTERN = re.compile(
    r"^(?P<year>\d+)(?P<event_code>[^\.]+)\.teams\.txt$"
)
TIMESTAMP_BASE = datetime.datetime(
    year=2025, month=1, day=1, tzinfo=datetime.timezone.utc
)


@dataclass
class EventTeamList:
    event_code: str
    teams: list[int]


@dataclass
class EventTeamsSnapshot:
    timestamp: datetime.datetime
    events: list[EventTeamList] = dataclasses.field(default_factory=list)


def parse_team_list_blob(blob: git.Blob) -> list[int]:
    out = []
    for line in blob.data_stream.read().decode().split("\n"):
        line = line.strip()
        if not line:
            continue
        out.append(int(line))
    return out


def read_teams_from_branch(
    repo: git.Repo,
    branch_name: str,
    match_files: list[str],
) -> list[EventTeamsSnapshot]:
    out = []
    for commit in repo.iter_commits(f"origin/{branch_name}"):
        # print(f"{branch_name} commit {commit.hexsha} at {commit.authored_date}")
        snapshot_time_utc = datetime.datetime.fromtimestamp(
            commit.authored_date, tz=datetime.timezone.utc
        )
        snapshot = EventTeamsSnapshot(
            timestamp=snapshot_time_utc,
            events=[],
        )
        for blob in commit.tree.traverse():
            if blob.type != "blob":
                continue
            if not any(fnmatch.fnmatch(blob.path, pattern) for pattern in match_files):
                continue
            match = TEAM_LIST_FILENAME_PATTERN.match(blob.path.split("/")[-1])
            if not match:
                print(f"WARN: unhandled file {blob.path!r} on {commit.hexsha}")
                continue
            snapshot.events.append(
                EventTeamList(
                    event_code=match.group("event_code"),
                    teams=parse_team_list_blob(blob),
                )
            )
        out.append(snapshot)
    return out


class DataFileWriter(io.BytesIO):
    def write_int16(self, value: int):
        self.write(struct.pack("<h", value))

    def write_int32(self, value: int):
        self.write(struct.pack("<i", value))

    def write_str(self, value: str):
        self.write(value.encode() + b"\x00")


def encode_data_file(data: list[EventTeamsSnapshot], year: int) -> bytes:
    out = DataFileWriter()
    out.write_int16(year)

    all_event_codes = set()
    all_team_lists = set()
    all_team_lists.add(())  # ensure we have the empty list
    for snapshot in data:
        for event in snapshot.events:
            all_event_codes.add(event.event_code)
            all_team_lists.add(tuple(sorted(event.teams)))

    all_event_codes = sorted(all_event_codes)
    all_team_lists = sorted(all_team_lists)
    assert all_team_lists[0] == ()

    event_code_to_index = {v: i for i, v in enumerate(all_event_codes)}
    team_list_to_index = {v: i for i, v in enumerate(all_team_lists)}

    # write event codes
    out.write_int16(len(all_event_codes))
    for event_code in all_event_codes:
        out.write_str(event_code)

    # write team lists
    out.write_int16(len(all_team_lists))
    for team_list in all_team_lists:
        out.write_int16(len(team_list))
        for team in team_list:
            out.write_int16(team)

    # write snapshots
    out.write_int16(len(data))
    for snapshot in data:
        out.write_int32(
            int(snapshot.timestamp.timestamp() - TIMESTAMP_BASE.timestamp())
        )
        out.write_int16(len(snapshot.events))
        for event in snapshot.events:
            out.write_int16(event_code_to_index[event.event_code])
            out.write_int16(team_list_to_index[tuple(sorted(event.teams))])

    with out:  # close
        return gzip.compress(out.getvalue())


@contextlib.contextmanager
def log_time(desc: str):
    t1 = time.perf_counter()
    yield
    t2 = time.perf_counter()
    print(f"{desc}: elapsed: {t2 - t1:.2f}sec")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("manifest")
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--dump-json")
    parser.add_argument("--output-dir")
    args = parser.parse_args()

    with open(args.manifest, "rb") as f:
        manifest = tomllib.load(f)

    repo = git.Repo(args.repo_root)

    data = {}

    # validate first
    for i, dataset_entry in enumerate(manifest["dataset"]):
        year = dataset_entry["year"]
        group_name = dataset_entry["group"]
        branch_name = dataset_entry["branch"]
        match_files = dataset_entry["match_files"]

        if not isinstance(year, int):
            raise ValueError(f"dataset {i}: invalid year: {year!r}")
        if not group_name:
            raise ValueError(f"dataset {i}: invalid group: {group_name!r}")
        if not branch_name:
            raise ValueError(f"dataset {i}: invalid branch: {branch_name!r}")
        if not isinstance(match_files, list) or not match_files:
            raise ValueError(f"dataset {i}: invalid match_files: {match_files!r}")

        data.setdefault(year, {})
        if group_name in data[year]:
            raise ValueError(f"dataset {i}: duplicate year/group")

        data[year][group_name] = None

    if args.output_dir:
        os.makedirs(args.output_dir, exist_ok=True)

    # print("Fetching...")
    # repo.remotes.origin.fetch([d["branch"] for d in manifest["dataset"]])

    def _load_dataset(dataset_entry):
        year = dataset_entry["year"]
        group_name = dataset_entry["group"]
        branch_name = dataset_entry["branch"]
        match_files = dataset_entry["match_files"]

        # gitpython is not thread-safe
        repo = git.Repo(args.repo_root)
        data[year][group_name] = read_teams_from_branch(repo, branch_name, match_files)
        print(f"loaded {len(data[year][group_name])} snapshots for {year}/{group_name}")

    with log_time("load data"):
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
            pool.map(_load_dataset, manifest["dataset"])

    if args.output_dir:
        with log_time("write data"):
            for year in data:
                for group_name in data[year]:
                    encoded = encode_data_file(data[year][group_name], year=year)
                    with open(
                        os.path.join(args.output_dir, f"{year}.{group_name}.eventdata"),
                        "wb",
                    ) as f:
                        f.write(encoded)

    return data


if __name__ == "__main__":
    data = main()
