# tests/test_converter_spreadsheet.py
import pytest
from docconv.converters.spreadsheet import SpreadsheetConverter
from docconv.config import load_config


@pytest.fixture
def converter():
    return SpreadsheetConverter()


@pytest.fixture
def config():
    return load_config()


def test_can_handle_xlsx(tmp_path, converter):
    assert converter.can_handle(tmp_path / "f.xlsx") is True


def test_can_handle_csv(tmp_path, converter):
    assert converter.can_handle(tmp_path / "f.csv") is True


def test_cannot_handle_pdf(tmp_path, converter):
    assert converter.can_handle(tmp_path / "f.pdf") is False


def test_simple_xlsx_produces_markdown_table(simple_xlsx, converter, config):
    result = converter.convert(simple_xlsx, config)
    assert "| Name" in result
    assert "Alice" in result
    assert "Bob" in result


def test_merged_cells_xlsx_fills_values(merged_cells_xlsx, converter, config):
    result = converter.convert(merged_cells_xlsx, config)
    assert result.count("Q1") >= 2
    assert result.count("South") >= 2


def test_multi_sheet_xlsx_has_section_headers(multi_sheet_xlsx, converter, config):
    result = converter.convert(multi_sheet_xlsx, config)
    assert "## Sheet1" in result
    assert "## Sheet2" in result


def test_csv_comma_delimiter(csv_comma, converter, config):
    result = converter.convert(csv_comma, config)
    assert "Alice" in result
    assert "Hanoi" in result


def test_csv_semicolon_delimiter(csv_semicolon, converter, config):
    result = converter.convert(csv_semicolon, config)
    assert "Alice" in result
    assert "Hanoi" in result


def test_csv_utf16_encoding(csv_utf16, converter, config):
    result = converter.convert(csv_utf16, config)
    assert "Alpha" in result


def test_max_cell_len_truncates(simple_xlsx, converter):
    config = load_config()
    config.spreadsheet.max_cell_len = 3
    result = converter.convert(simple_xlsx, config)
    # "Alice" (5 chars) with max_cell_len=3 → "Al…" (2 chars + ellipsis)
    assert "Al…" in result
    assert "Bob" in result


def test_sheets_filter_limits_output(multi_sheet_xlsx, converter):
    config = load_config()
    config.spreadsheet.sheets = ["Sheet1"]
    result = converter.convert(multi_sheet_xlsx, config)
    assert "## Sheet1" in result
    assert "## Sheet2" not in result
