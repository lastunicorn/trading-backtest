# RunEnvironment

A [port](README.md) of the [application blueprint](../README.md).

*Python: `ports/run_environment/`.* The two things a run records about its surroundings.

## Actions

| Action | Returns | Description |
|---|---|---|
| `now()` | `LocalDateTime` | The local wall-clock time, no zone. |
| `git_commit(repo: Path = the application's own repository)` | `GitCommit` | HEAD's short hash and whether the working tree has uncommitted changes (`git rev-parse --short HEAD`, `git status --porcelain` non-empty). Each field is `null` when git can't tell (not installed, not a repository, a 10-second timeout). |

## Errors

None: `git_commit` reports what git can't tell as `null` fields instead.

## DTOs

### GitCommit

| Property | Type | Notes |
|---|---|---|
| `commit` | `String?` | short hash of HEAD |
| `dirty` | `Boolean?` | uncommitted changes in the working tree |
