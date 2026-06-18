"""HTML rendering: the tiny Markdown subset, escaping, and the CLI --html path."""

from __future__ import annotations

from risk_ledger.cli import main
from risk_ledger.render import html_document, markdown_to_html, raw_svg_block


def test_headings_rules_bold_italic_code():
    html = markdown_to_html("# Title\n\n## Section\n\n---\n\nA **bold** and *italic* and `code` line.")
    assert "<h1>Title</h1>" in html
    assert "<h2>Section</h2>" in html
    assert "<hr/>" in html
    assert "<strong>bold</strong>" in html
    assert "<em>italic</em>" in html
    assert "<code>code</code>" in html


def test_table_renders_with_header_and_rows():
    md = "| A | B |\n|---|---|\n| 1 | **2** |\n| 3 | 4 |"
    html = markdown_to_html(md)
    assert "<table>" in html and "</table>" in html
    assert "<th>A</th>" in html and "<th>B</th>" in html
    assert "<td>1</td>" in html
    assert "<td><strong>2</strong></td>" in html  # inline markdown inside cells
    assert "|" not in html  # pipes fully consumed


def test_bullet_list():
    html = markdown_to_html("- one\n- two\n")
    assert html.count("<li>") == 2
    assert "<ul>" in html and "</ul>" in html


def test_html_is_escaped_no_injection():
    # Free-text fields must not be able to inject markup when rendered as HTML.
    html = markdown_to_html("Title with <script>alert(1)</script> & an ampersand")
    assert "<script>" not in html
    assert "&lt;script&gt;" in html
    assert "&amp;" in html


def test_document_wraps_and_colours_badges():
    doc = html_document(markdown_to_html("### RISK-X — OVER appetite"))
    assert doc.startswith("<!DOCTYPE html>")
    assert "<style>" in doc
    assert '<span class="over">OVER appetite</span>' in doc


def test_raw_svg_block_passes_through_unescaped():
    # The one controlled path that bypasses escaping: trusted, self-generated SVG.
    svg = '<svg class="rl-chart"><rect x="0" y="0" width="4" height="4"/></svg>'
    html = markdown_to_html(raw_svg_block(svg))
    assert svg in html  # verbatim, angle brackets intact
    assert "&lt;svg" not in html


def test_raw_svg_passthrough_does_not_weaken_table_escaping():
    # A raw SVG block and a table with markup in a cell, in the same document: the
    # SVG passes through, but the record text is still escaped in the table.
    svg = '<svg class="rl-chart"><rect width="4" height="4"/></svg>'
    md = raw_svg_block(svg) + "\n\n| Title |\n|---|\n| <script>alert(1)</script> |"
    html = markdown_to_html(md)
    assert "<svg" in html and "<rect" in html  # chart passed through
    assert "&lt;script&gt;" in html  # table cell still escaped
    assert "<script>" not in html  # no raw injection from a data field


def test_cli_html_writes_file(tmp_path, capsys):
    out = tmp_path / "report.html"
    assert main(["report", "--html", "--no-open", "--out", str(out)]) == 0
    text = out.read_text()
    assert text.startswith("<!DOCTYPE html>")
    assert "<table>" in text and "Company Corp Exceptions Risk Report" in text
    assert "Wrote" in capsys.readouterr().out
