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

PACKAGES = ("application", "domain", "libs", "ports", "strategies", "ui")
SCRIPTS = "scripts"  # the entry scripts at the repo root, as one component
SCRIPT_MODULES = frozenset(path.stem for path in REPO_ROOT.glob("*.py"))

# Component -> the components it may import (itself included). No component
# may import an entry script: shared code belongs in a package.
ALLOWED_IMPORTS = {
    SCRIPTS: {"application", "domain", "ports", "strategies", "ui"},
    "application": {"application", "domain", "ports", "strategies"},
    "strategies": {"strategies", "domain"},
    "ports": {"ports", "domain", "libs"},  # only the domain names in PORT_DOMAIN_NAMES
    "ui": {"ui", "domain"},
    "domain": {"domain"},
    "libs": {"libs"},  # and only its own library, see test_each_library_imports_only_itself
}

# The domain names a port may import, by module: the entities it parses into
# or writes out, and the enums and name tables that spell them. Never logic.
PORT_DOMAIN_NAMES = {
    "domain.bar_approach.bar": {"Bar"},
    "domain.backtesting.backtest": {"BacktestResult"},
    "domain.backtesting.splits": {"SplitMode"},
    "domain.market_data.broker_clock": {"timezone_name"},
    "domain.market_data.trading_session": {"SESSIONS", "TradingSession"},
}


def source_files(component: str) -> list[Path]:
    if component == SCRIPTS:
        return sorted(REPO_ROOT.glob("*.py"))
    return sorted(path for path in (REPO_ROOT / component).rglob("*.py")
                  if "__pycache__" not in path.parts)


def module_name(path: Path) -> str:
    return ".".join(path.relative_to(REPO_ROOT).with_suffix("").parts)


def imported_modules(path: Path) -> list[tuple[int, str]]:
    """(line, absolute module name) for every import in `path`."""
    return [(line, module) for line, module, _ in import_statements(path)]


def import_statements(path: Path) -> list[tuple[int, str, tuple[str, ...] | None]]:
    """(line, absolute module name, names imported) for every import in `path`.

    The names are those of a `from module import ...`; None for a plain
    `import module`, which imports the whole module.
    """
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    found = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            found.extend((node.lineno, alias.name, None) for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            if node.level:  # relative: resolve against the importing package
                package = module_name(path).split(".")
                if path.name != "__init__.py":
                    package = package[:-1]
                base = package[:len(package) - (node.level - 1)]
                module = ".".join(base + ([node.module] if node.module else []))
            else:
                module = node.module
            found.append((node.lineno, module, tuple(alias.name for alias in node.names)))
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


def test_ports_import_only_the_allowed_domain_names():
    violations = [
        describe(path, line, module if name is None else f"{module}.{name}")
        for path in source_files("ports")
        for line, module, names in import_statements(path)
        if component_of(module) == "domain"
        for name in (names or (None,))
        if name not in PORT_DOMAIN_NAMES.get(module, ())
    ]

    allowed = ", ".join(f"{module}.{name}" for module, names in sorted(PORT_DOMAIN_NAMES.items())
                        for name in sorted(names))
    assert not violations, (f"ports may import only these domain names: {allowed}\n  "
                            + "\n  ".join(violations))


def test_each_library_imports_only_itself():
    """A library must stay copyable to another project: no imports from the repo, not even another library."""
    violations = [
        describe(path, line, module)
        for path in source_files("libs")
        for line, module in imported_modules(path)
        if component_of(module) == "libs"
        and module.split(".")[:2] != module_name(path).split(".")[:2]
        and module != "libs"
    ]

    assert not violations, ("a library may import only its own modules:\n  "
                            + "\n  ".join(violations))
