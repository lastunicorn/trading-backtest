# Backtest Application

The current project is a collection of scripts focused on back-testing historical trading data.

Each entry script (script that can be run by itself) is placed in the root of the repo. Other helpers are placed inside directories. In other words, run only scripts that are in the root of the repo.

## Architecture

The code is split into seven components: the entry scripts, `application/`, `ports/`, `libs/`, `domain/`, `strategies/` and `ui/`. There are rules about which component may import which. See [doc/architecture.md](doc/architecture.md) for what goes where and why.

The backtest framework has its own documentation in [doc/backtest-framework/](doc/backtest-framework/README.md).

## How to run

Start the virtual environment:

```sh
source .venv/bin/activate
```

Run python scripts:

```sh
python script.py
```

Run tests:

```sh
python -m pytest tests/ -v
```

## How to recreate the python virtual environment

Rebuild it after cloning the repo, or after moving or renaming its folder. A virtual environment stores its own absolute path, so a moved `.venv/` stops working.

One-time, if `python3 -m venv` complains that `ensurepip` is not available:

```sh
sudo apt install python3-venv
```

Remove the current virtual environment:

```sh
rm -rf .venv
```

Recreate the virtual environment:

```sh
python3 -m venv .venv
```

Install the dependencies (`requirements-dev.txt` is `requirements.txt` plus `pytest`):

```sh
.venv/bin/pip install -r requirements-dev.txt
```

Then activate it, as described in [How to run](#how-to-run).
