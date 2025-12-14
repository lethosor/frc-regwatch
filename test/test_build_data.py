import functools
import json
import os
import subprocess
import tempfile

import build_data
import git
import pytest

TEST_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.join(TEST_DIR, "..")


@functools.cache
def load_data(branch_name):
    repo = git.Repo(REPO_ROOT)
    data = build_data.read_teams_from_branch(repo, branch_name, ["*.teams.txt"])
    assert data
    return data


@pytest.mark.parametrize("year, group_name", ((2025, "frc"), (2026, "tba")))
def test_roundtrip_python(year, group_name):
    data = load_data(f"data-{year}-{group_name}")
    encoded = build_data.encode_data_file(data, year=year)
    decoded = build_data.decode_data_file(encoded)
    assert data == decoded


@pytest.mark.parametrize("year, group_name", ((2025, "frc"), (2026, "tba")))
def test_roundtrip_python_js(year, group_name):
    data = load_data(f"data-{year}-{group_name}")
    data_json = json.loads(build_data.encode_data_json(data))
    with tempfile.NamedTemporaryFile(
        mode="w+b", delete=True, delete_on_close=False
    ) as tmp:
        tmp.write(build_data.encode_data_file(data, year=year))
        tmp.close()  # release handle so node can open it on Windows

        p = subprocess.run(
            ["node", os.path.join(TEST_DIR, "decode-data-file.js"), tmp.name],
            check=True,
            capture_output=True,
            encoding="utf-8",
        )
        result = json.loads(p.stdout)

        assert result == data_json
