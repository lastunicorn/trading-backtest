# Backtest Application

The current project is a collection of scripts focused on back-testing historical trading data.

Each entry script (script that can be run by itself) is placed in the root of the repo. Other helpers are placed inside directories. In other words, run only scripts that are in the root of the repo.

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
