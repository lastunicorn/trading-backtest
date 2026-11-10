# FileSystem

A [port](README.md) of the [application blueprint](../README.md).

*Python: `ports/file_system_access/`.* Finds the source files of a bar format in a folder.

## Actions

| Action | Returns | Description |
|---|---|---|
| `find_files(path: Path, pattern: String = "*.csv", skip_parts: List<String> = [], recursive: Boolean = false)` | `List<Path>` | A file: `[path]`, unfiltered (pointing at a file means that file). A folder: the files matching the glob `pattern` (in subfolders too with `recursive`), minus those whose name contains any of `skip_parts` (case-insensitive), sorted by path. A path that doesn't exist gives an empty list, not an error: callers decide what "no files" means. |

## Errors

None.
