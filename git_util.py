import datetime
import io
import os
import tempfile
from dataclasses import dataclass

import git
import gitdb

EMPTY_TREE_SHA = "4b825dc642cb6eb9a060e54bf8d69288fbee4904"


@dataclass
class GitFileContents:
    data: str
    mode: str = "100644"  # default: regular file


def ensure_branch(
    *,
    repo: git.Repo,
    branch: str,
):
    if branch not in repo.heads:
        new_commit_sha = repo.git.commit_tree(EMPTY_TREE_SHA, "-m", "initialize")
        repo.git.update_ref(f"refs/heads/{branch}", new_commit_sha)


def commit_subdir_contents(
    *,
    repo,  # git.Repo
    branch: str,
    subdir: str,
    files: dict[str, GitFileContents],  # key is path relative to `subdir`
    message: str,
    author: tuple[str, str],  # name, email
    committer: tuple[str, str] = None,  # default: author
    author_date: datetime.datetime = None,  # default: now
    committer_date: datetime.datetime = None,  # default: author_date
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

            data_bytes = file_contents.data.encode("utf-8")
            stream = gitdb.IStream(b"blob", len(data_bytes), io.BytesIO(data_bytes))
            blob_sha = repo.odb.store(stream).hexsha.decode()
            repo.git.update_index(
                "--add",
                "--cacheinfo",
                str(file_contents.mode),
                blob_sha,
                full_path,
                env=env,
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
            commit_env["GIT_AUTHOR_DATE"] = str(int(author_date.timestamp()))
        if committer_date:
            commit_env["GIT_COMMITTER_DATE"] = str(int(committer_date.timestamp()))

        new_commit_sha = repo.git.commit_tree(
            tree_sha, "-p", base.hexsha, "-m", message, env=commit_env
        )
        repo.git.update_ref(f"refs/heads/{branch}", new_commit_sha)
        return new_commit_sha
