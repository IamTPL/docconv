from docconv.utils.postprocess import clean_markdown


def test_normalizes_line_endings():
    result = clean_markdown("line1\r\nline2\r\nline3")
    assert "\r" not in result


def test_removes_trailing_whitespace_per_line():
    result = clean_markdown("line1   \nline2  \n")
    for line in result.split("\n"):
        assert line == line.rstrip()


def test_collapses_excess_blank_lines():
    result = clean_markdown("a\n\n\n\n\nb")
    assert "\n\n\n" not in result


def test_ensures_single_trailing_newline():
    result = clean_markdown("some content\n\n\n")
    assert result.endswith("\n")
    assert not result.endswith("\n\n")


def test_strips_leading_whitespace():
    result = clean_markdown("\n\n\nHello")
    assert not result.startswith("\n")


def test_empty_string_returns_newline():
    result = clean_markdown("")
    assert result == "\n"


def test_preserves_markdown_table_structure():
    table = "| A | B |\n|---|---|\n| 1 | 2 |\n"
    result = clean_markdown(table)
    assert "| A | B |" in result
    assert "|---|---|" in result
