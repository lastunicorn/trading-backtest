"""Tests for `ui.cli_args.timezone_arg`."""

import argparse
from zoneinfo import ZoneInfo

import pytest

from domain.broker_clock import BROKER_SERVER_TZ
from ui.cli_args import timezone_arg


@pytest.mark.parametrize("name", ["broker", "BROKER", " Broker "])
def test_broker_is_the_broker_server_clock(name: str) -> None:
    assert timezone_arg(name) is BROKER_SERVER_TZ


def test_iana_names_are_zoneinfo() -> None:
    assert timezone_arg("Europe/London") == ZoneInfo("Europe/London")


@pytest.mark.parametrize("name", ["Mars/Olympus_Mons", "", "/etc/localtime", "../etc/passwd"])
def test_unknown_or_malformed_name_is_an_argument_type_error(name: str) -> None:
    with pytest.raises(argparse.ArgumentTypeError, match=f"unknown timezone {name!r}"):
        timezone_arg(name)


def test_argparse_reports_an_unknown_name_as_a_usage_error(capsys) -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--timezone", type=timezone_arg)

    with pytest.raises(SystemExit) as exit_info:
        parser.parse_args(["--timezone", "Mars/Olympus_Mons"])

    assert exit_info.value.code == 2
    assert "argument --timezone: unknown timezone 'Mars/Olympus_Mons'" in capsys.readouterr().err
