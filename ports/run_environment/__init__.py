"""Reads the process's surroundings that a run records: the wall clock and the git commit.

Re-exported so callers can use the short form:

    from ports.run_environment import GitCommit, git_commit, now
"""

from ports.run_environment.run_environment import GitCommit, git_commit, now

__all__ = ["GitCommit", "git_commit", "now"]
