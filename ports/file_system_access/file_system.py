from pathlib import Path
from typing import Sequence

DEFAULT_SKIP_NAME_PARTS = []

def find_files(
    folder,
    pattern: str = "*.csv",
    skip_parts: Sequence[str] = DEFAULT_SKIP_NAME_PARTS,
) -> list[Path]:
    """The raw exports in `folder`, sorted by name, generated files excluded."""
    lowered = [part.lower() for part in skip_parts]

    return [
        path
        for path in sorted(Path(folder).glob(pattern))
        if not any(part in path.name.lower() for part in lowered)
    ]

