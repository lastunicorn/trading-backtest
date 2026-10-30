"""Tests for `ports.run_environment.git_commit`."""

import shutil
import subprocess
from pathlib import Path

import pytest

from ports.run_environment import GitCommit, git_commit

requires_git = pytest.mark.skipif(shutil.which("git") is None, reason="git is not installed")


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(["git", *args], cwd=repo, capture_output=True, text=True, check=True).stdout.strip()


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    _git(tmp_path, "init", "--quiet")
    (tmp_path / "file.txt").write_text("one\n")
    _git(tmp_path, "add", "file.txt")
    _git(tmp_path, "-c", "user.name=Test", "-c", "user.email=test@example.com", "commit", "--quiet", "-m", "first")
    return tmp_path


@requires_git
def test_reports_head_short_hash_of_a_clean_tree(repo: Path) -> None:
    assert git_commit(repo) == GitCommit(commit=_git(repo, "rev-parse", "--short", "HEAD"), dirty=False)


@requires_git
def test_reports_a_modified_tree_as_dirty(repo: Path) -> None:
    (repo / "file.txt").write_text("two\n")

    assert git_commit(repo).dirty is True


@requires_git
def test_reports_an_untracked_file_as_dirty(repo: Path) -> None:
    (repo / "new.txt").write_text("new\n")

    assert git_commit(repo).dirty is True


def test_is_all_none_outside_a_repository(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GIT_CEILING_DIRECTORIES", str(tmp_path.parent))

    assert git_commit(tmp_path) == GitCommit(commit=None, dirty=None)


def test_is_all_none_when_git_cannot_run(tmp_path: Path) -> None:
    assert git_commit(tmp_path / "missing") == GitCommit(commit=None, dirty=None)
