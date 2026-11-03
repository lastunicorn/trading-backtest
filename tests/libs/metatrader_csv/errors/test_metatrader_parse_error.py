"""Tests for `libs.metatrader_csv.errors.MetatraderParseError`."""

from libs.metatrader_csv import MetatraderParseError


def test_keeps_its_parts_and_names_the_file_and_line() -> None:
    error = MetatraderParseError("/data/export.csv", 7, "bad number", "2020.01.02,00:00,x\n")

    assert (error.path, error.line_no, error.reason, error.line) == ("/data/export.csv", 7, "bad number",
                                                                     "2020.01.02,00:00,x\n")
    assert str(error) == "export.csv:7: bad number  |  2020.01.02,00:00,x"


def test_without_a_line() -> None:
    assert str(MetatraderParseError("export.csv", 1, "no prices")) == "export.csv:1: no prices"


def test_is_a_value_error() -> None:
    assert isinstance(MetatraderParseError("x", 1, "r"), ValueError)
