import datetime
import io
import os
import tempfile
from dataclasses import dataclass

from git import Repo
from gitdb import IStream


@dataclass
class GitFileContents:
    data: bytes
    mode: str = "100644"  # default: regular file


def commit_replace_subdir(
    *,
    repo,
    branch,
    subdir,
    files,
    message,
    author=("Your Name", "you@example.com"),
    committer=None,
    author_date=None,
    committer_date=None,
):
    def to_git_path(p):
        return p.replace("\\", "/").lstrip("/")

    base = repo.commit(branch)

    if committer is None:
        committer = author
    if committer_date is None and author_date is not None:
        committer_date = author_date

    subdir_prefix = to_git_path(subdir)
    if subdir_prefix and not subdir_prefix.endswith("/"):
        subdir_prefix += "/"

    with tempfile.NamedTemporaryFile(
        prefix="altindex-", delete=True, delete_on_close=False
    ) as tmp:
        tmp_path = tmp.name
        tmp.close()  # release handle so git can open it on Windows

        env = os.environ.copy()
        env["GIT_INDEX_FILE"] = tmp_path

        repo.git.read_tree(base.tree.hexsha, env=env)

        if subdir_prefix:
            repo.git.rm(
                "-r", "--cached", "--ignore-unmatch", "--", subdir_prefix, env=env
            )

        for path, file_contents in files.items():
            full_path = subdir_prefix + to_git_path(path)

            stream = IStream(
                b"blob", len(file_contents.data), io.BytesIO(file_contents.data)
            )
            blob_sha = repo.odb.store(stream).hexsha
            repo.git.update_index(
                "--add", "--cacheinfo", file_contents.mode, blob_sha, full_path, env=env
            )

        tree_sha = repo.git.write_tree(env=env)

        a_name, a_email = author
        c_name, c_email = committer
        commit_env = {
            **env,
            "GIT_AUTHOR_NAME": a_name,
            "GIT_AUTHOR_EMAIL": a_email,
            "GIT_COMMITTER_NAME": c_name,
            "GIT_COMMITTER_EMAIL": c_email,
        }
        if author_date:
            commit_env["GIT_AUTHOR_DATE"] = author_date
        if committer_date:
            commit_env["GIT_COMMITTER_DATE"] = committer_date

        new_commit_sha = repo.git.commit_tree(
            tree_sha, "-p", base.hexsha, "-m", message, env=commit_env
        )
        repo.git.update_ref(f"refs/heads/{branch}", new_commit_sha)
        return new_commit_sha


if __name__ == "__main__":
    commit_replace_subdir(
        repo=Repo("."),
        branch="data-branch-1",
        subdir="data",
        files={
            "a": GitFileContents("contents a"),
            "b": GitFileContents("b", "contents b"),
        },
        message="test commit 1",
        author_date=datetime.datetime.now(),
    )
