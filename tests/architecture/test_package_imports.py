"""The import rules between the repo's components (see CLAUDE.md, "Code layout").

Every `import` / `from ... import` in the source is parsed with `ast` (so
examples in docstrings don't count) and checked against `ALLOWED_IMPORTS`.
Third-party and stdlib imports are ignored; only the repo's own components are
checked.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]

PACKAGES = ("application", "domain", "ports", "strategies", "ui")
SCRIPTS = "scripts"  # the entry scripts at the repo root, as one component
SCRIPT_MODULES = frozenset(path.stem for path in REPO_ROOT.glob("*.py"))

# Component -> the components it may import (itself included). No component
# may import an entry script: shared code belongs in a package.
ALLOWED_IMPORTS = {
    SCRIPTS: {"application", "domain", "ports", "strategies", "ui"},
    "application": {"application", "domain", "ports", "strategies"},
    "strategies": {"strategies", "domain"},
    "ports": {"ports", "domain"},  # domain entities only, see PORT_DOMAIN_ENTITIES
    "ui": {"ui", "domain"},
    "domain": {"domain"},
}

# The domain modules a port may import: entities it parses into, never logic.
PORT_DOMAIN_ENTITIES = frozenset({"domain.bar_approach.bar"})


def source_files(component: str) -> list[Path]:
    if component == SCRIPTS:
        return sorted(REPO_ROOT.glob("*.py"))
    return sorted(path for path in (REPO_ROOT / component).rglob("*.py")
                  if "__pycache__" not in path.parts)


def module_name(path: Path) -> str:
    return ".".join(path.relative_to(REPO_ROOT).with_suffix("").parts)


def imported_modules(path: Path) -> list[tuple[int, str]]:
    """(line, absolute module name) for every import in `path`."""
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    found = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            found.extend((node.lineno, alias.name) for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            if node.level:  # relative: resolve against the importing package
                package = module_name(path).split(".")
                if path.name != "__init__.py":
                    package = package[:-1]
                base = package[:len(package) - (node.level - 1)]
                module = ".".join(base + ([node.module] if node.module else []))
            else:
                module = node.module
            found.append((node.lineno, module))
    return found


def component_of(module: str) -> str | None:
    """The repo component `module` belongs to, or None for an external one."""
    top = module.split(".")[0]
    if top in PACKAGES:
        return top
    if top in SCRIPT_MODULES:
        return SCRIPTS
    return None


def describe(path: Path, line: int, module: str) -> str:
    return f"{path.relative_to(REPO_ROOT)}:{line} imports {module}"


@pytest.mark.parametrize("component", sorted(ALLOWED_IMPORTS))
def test_component_imports_only_allowed_components(component):
    files = source_files(component)
    assert files, f"no source files found for {component!r}"

    violations = [
        describe(path, line, module)
        for path in files
        for line, module in imported_modules(path)
        if (target := component_of(module)) is not None
        and target not in ALLOWED_IMPORTS[component]
    ]

    allowed = ", ".join(sorted(ALLOWED_IMPORTS[component]))
    assert not violations, (f"{component} may import only {allowed}:\n  "
                            + "\n  ".join(violations))


def test_ports_import_only_domain_entities():
    violations = [
        describe(path, line, module)
        for path in source_files("ports")
        for line, module in imported_modules(path)
        if component_of(module) == "domain" and module not in PORT_DOMAIN_ENTITIES
    ]

    entities = ", ".join(sorted(PORT_DOMAIN_ENTITIES))
    assert not violations, (f"ports may import only these domain entities: {entities}\n  "
                            + "\n  ".join(violations))
