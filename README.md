# Backtest Application

The current project is a collection of scripts focused on back-testing historical trading data.

Each entry script (script that can be run by itself) is placed in the root of the repo. Other helpers are placed inside directories. In other words, run only scripts that are in the root of the repo.

## Architecture

The code is split into six components: the entry scripts, `application/`, `ports/`, `domain/`, `strategies/` and `ui/`. There are rules about which component may import which. See [help/architecture.md](help/architecture.md) for what goes where and why.

The backtest framework has its own documentation in [help/backtest-framework/](help/backtest-framework/README.md).

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

Remove the current virtual environment

```sh
rm -rf .venv
```

Recreate the virtual environment

```sh
python3 -m venv .venv
```

???

```sh
.venv/bin/pip install -r requirements.txt pytest
```

Then activate it

- See the "How to run"
