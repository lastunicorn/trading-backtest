from pathlib import Path
from typing import Sequence


def find_files(
    path,
    pattern: str = "*.csv",
    skip_parts: Sequence[str] = (),
    recursive: bool = False,
) -> list[Path]:
    """The source files at `path`, sorted by name, generated files excluded.

    `path` is either a folder -- every file matching `pattern` inside it, minus
    the ones whose name contains a `skip_parts` fragment -- or a single file,
    returned as a one-item list with no pattern or skip filtering: pointing
    straight at a file is taken to mean that file. `recursive` extends the
    folder search into subdirectories; it is False by default, matching the
    top-level-only behaviour every existing caller relies on.
    """
    path = Path(path)
    if path.is_file():
        return [path]

    lowered = [part.lower() for part in skip_parts]
    glob = path.rglob if recursive else path.glob

    return [
        found
        for found in sorted(glob(pattern))
        if not any(part in found.name.lower() for part in lowered)
    ]
