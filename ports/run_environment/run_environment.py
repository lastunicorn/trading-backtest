"""The wall clock and the repo's git state, the two things a run reads from outside the process.

Stdlib only. Callers take these functions as parameters (defaulting to the ones
here) so tests can pass fakes instead of reading the real clock or repo.
"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]


@dataclass(frozen=True)
class GitCommit:
    """HEAD's short hash and whether the working tree has changes; None for what git could not tell."""

    commit: str | None
    dirty: bool | None


def now() -> datetime:
    """The current local wall-clock time, naive."""
    return datetime.now()


def git_commit(repo: Path = _REPO_ROOT) -> GitCommit:
    """The git state of `repo` (default: this repository); all None when git is unavailable."""
    def git(*args: str) -> str | None:
        try:
            completed = subprocess.run(
                ["git", *args], cwd=repo, capture_output=True, text=True, timeout=10, check=True,
            )
        except (OSError, subprocess.SubprocessError):
            return None
        return completed.stdout.strip()

    status = git("status", "--porcelain")
    return GitCommit(commit=git("rev-parse", "--short", "HEAD"), dirty=None if status is None else bool(status))
