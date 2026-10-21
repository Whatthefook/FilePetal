"""Faithful HTML rendering (v1.8) and the v1.9 print quality pass.

The builders are pure Python and run anywhere; only the final
``html_to_pdf`` step needs QtWebEngine on the GUI thread, so the suite
covers the markup here and the PDF round-trip skips under the offscreen
platform used by the tests (a live check runs it for real).
"""

import os

import pytest

from tangerine import render


def test_markdown_renders_headings_tables_and_code():
    source = (
        "# Title\n\n"
        "Some **bold** text.\n\n"
        "| A | B |\n|---|---|\n| 1 | 2 |\n\n"
        "```python\nprint('hi')\n```\n"
    )
    page = render.markdown_to_html(source)
    assert "<title>Title</title>" in page
    assert "<h1>Title</h1>" in page
    assert "<table>" in page
    assert "codehilite" in page
    assert "<style>" in page


def test_markdown_title_comes_from_argument_or_first_heading():
    assert "<title>Custom</title>" in render.markdown_to_html("no heading", "Custom")
    assert "<title>Hello</title>" in render.markdown_to_html("# Hello\n\ntext")


def test_table_to_html_shapes_rows():
    page = render.table_to_html([["h1", "h2"], ["a", "b"]])
    assert page == (
        "<table><thead><tr><th>h1</th><th>h2</th></tr></thead>"
        "<tbody><tr><td>a</td><td>b</td></tr></tbody></table>"
    )
    assert render.table_to_html([]) == "<p></p>"


def test_csv_escapes_markup(tmp_path):
    csv_path = tmp_path / "sample.csv"
    csv_path.write_text("name,note\nx,<script>alert(1)</script>\n", "utf-8")
    page = render.csv_to_html(csv_path)
    assert "&lt;script&gt;" in page
    assert "<script>" not in page
    assert "<title>sample</title>" in page


def test_docx_renders_paragraphs(tmp_path):
    docx = pytest.importorskip("docx")
    path = tmp_path / "sample.docx"
    document = docx.Document()
    document.add_paragraph("Hola mundo")
    document.save(path)

    page = render.docx_to_html(path)
    assert "Hola mundo" in page
    assert "<p>" in page
    assert "<title>sample</title>" in page


def test_xlsx_renders_cell_values(tmp_path):
    openpyxl = pytest.importorskip("openpyxl")
    path = tmp_path / "sample.xlsx"
    workbook = openpyxl.Workbook()
    sheet = workbook.active
    sheet["A1"] = "hola"
    sheet["B1"] = 42
    workbook.save(path)

    page = render.xlsx_to_html(path)
    assert "hola" in page
    assert "42" in page
    assert "<title>sample</title>" in page


# ---------------------------------------------------------------------------
# v1.9 print polish: paper, margins, prose and page breaks
# ---------------------------------------------------------------------------

def test_margin_presets_and_page_sizes():
    assert render.MARGIN_PRESETS_MM["normal"] == (16.0, 18.0, 16.0, 18.0)
    assert render.MARGIN_PRESETS_MM["compact"] == (10.0, 12.0, 10.0, 12.0)
    assert render.MARGIN_PRESETS_MM["wide"] == (25.0, 20.0, 25.0, 20.0)
    assert render.DEFAULT_PAGE_SIZE == "a4"
    assert render.PAGE_SIZES_MM["a4"] == (210.0, 297.0)
    assert render.PAGE_SIZES_MM["letter"] == (215.9, 279.4)

    width, height = render.page_size_points("a4")
    assert round(width) == 595
    assert round(height) == 842

    left, top, right, bottom = render.margins_to_points(
        render.MARGIN_PRESETS_MM["normal"])
    assert round(left) == 45
    assert round(top) == 51
    assert left == right
    assert top == bottom


def test_print_css_bakes_paper_and_margins():
    css = render.print_css()
    assert "size: 210mm 297mm" in css
    assert "margin: 18mm 16mm 18mm 16mm" in css
    assert "page-break-inside: avoid" in css
    assert "orphans: 2" in css

    options = {"page_size": "letter", "margins_mm": (10.0, 12.0, 10.0, 12.0)}
    letter = render.print_css(options)
    assert "size: 215.9mm 279.4mm" in letter
    assert "margin: 12mm 10mm 12mm 10mm" in letter


def test_print_options_fall_back_to_defaults(monkeypatch):
    from tangerine import settings

    monkeypatch.setattr(
        settings, "get",
        lambda key, default=None: {"pdfPageSize": "nope", "pdfMarginPreset": "nope"}.get(
            key, default),
    )
    options = render.print_options()
    assert options["page_size"] == render.DEFAULT_PAGE_SIZE
    assert options["margins_mm"] == render.MARGIN_PRESETS_MM["normal"]
    assert options["page_numbers"] is True


def test_print_options_read_custom_settings(monkeypatch):
    from tangerine import settings

    values = {
        "pdfPageSize": "letter",
        "pdfMarginPreset": "wide",
        "pdfPageNumbers": False,
    }
    monkeypatch.setattr(settings, "get", lambda key, default=None: values.get(key, default))
    options = render.print_options()
    assert options["page_size"] == "letter"
    assert options["margins_mm"] == render.MARGIN_PRESETS_MM["wide"]
    assert options["page_numbers"] is False


def test_plain_text_keeps_columns_and_escapes_markup():
    page = render.plain_text_to_html("hola <b>mundo</b>\n        indented", "Notas")
    assert "<title>Notas</title>" in page
    assert "class='plain'" in page
    assert "&lt;b&gt;" in page
    assert "<b>mundo</b>" not in page
    assert "        indented" in page


def test_paragraphs_to_html_splits_on_blank_lines():
    page = render.paragraphs_to_html("uno\ndos\n\ntres", "Doc")
    assert "<p>uno<br>dos</p><p>tres</p>" in page
    assert "<title>Doc</title>" in page


def test_slides_to_html_makes_one_section_per_slide():
    slides = [("Portada", ["uno", "dos"]), ("Cierre", [])]
    page = render.slides_to_html(slides, "Charla")
    assert page.count("class='slide'") == 2
    assert "Slide 1" in page
    assert "Slide 2" in page
    assert "<h1>Portada</h1>" in page
    assert "<li>uno</li>" in page
    assert "<title>Charla</title>" in page


def _three_page_pdf(path):
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas as pdf_canvas

    pdf = pdf_canvas.Canvas(str(path), pagesize=A4)
    for number in (1, 2, 3):
        pdf.drawString(60, 700, f"pagina {number}")
        pdf.showPage()
    pdf.save()
    return path


def test_postprocess_pdf_stamps_metadata_and_numbers(tmp_path):
    pytest.importorskip("pypdf")
    pytest.importorskip("reportlab")
    from pypdf import PdfReader

    source = _three_page_pdf(tmp_path / "plain.pdf")
    assert render.postprocess_pdf(source, title="Reporte", page_numbers=True)

    reader = PdfReader(str(source))
    assert len(reader.pages) == 3
    assert reader.metadata.get("/Title") == "Reporte"
    assert reader.metadata.get("/Author") in ("FilePetal", "Tangerine")
    for index, page in enumerate(reader.pages, start=1):
        text = page.extract_text().replace(" ", "")
        assert f"{index}/3" in text
    assert reader.pages[0].extract_text().replace(" ", "").count("/3") == 1


def test_postprocess_pdf_without_numbers_keeps_pages_clean(tmp_path):
    pytest.importorskip("pypdf")
    pytest.importorskip("reportlab")
    from pypdf import PdfReader

    source = _three_page_pdf(tmp_path / "plain.pdf")
    assert render.postprocess_pdf(source, title="Limpio", page_numbers=False)

    reader = PdfReader(str(source))
    assert reader.metadata.get("/Title") == "Limpio"
    assert "/3" not in reader.pages[0].extract_text().replace(" ", "")


def test_html_to_pdf_without_renderer_is_false(tmp_path, monkeypatch):
    monkeypatch.setattr(render, "_renderer", None)
    assert render.html_to_pdf("<p>x</p>", tmp_path / "x.pdf") is False


def test_pdf_roundtrip_needs_a_real_platform(tmp_path):
    if os.environ.get("QT_QPA_PLATFORM", "") == "offscreen":
        pytest.skip("QtWebEngine needs a real platform")
    if not render.available():
        pytest.skip("QtWebEngine not installed")

    from PySide6.QtWidgets import QApplication

    app = QApplication.instance() or QApplication([])
    assert app is not None
    assert render.ensure_ready()

    out = tmp_path / "roundtrip.pdf"
    assert render.html_to_pdf(
        "<h1>Hola</h1><p>Render fiel</p>", out, title="Roundtrip")
    assert out.stat().st_size > 0

    pdfium = pytest.importorskip("pypdfium2")
    from PIL import Image

    document = pdfium.PdfDocument(str(out))
    page = document[0]
    width, height = page.get_size()
    assert 593 < width < 597
    assert 840 < height < 844

    bitmap = page.render(scale=1).to_pil().convert("L")
    ink = Image.eval(bitmap, lambda pixel: 255 - pixel).getbbox()
    assert ink is not None
    assert ink[0] >= 28, f"text starts at {ink[0]}pt, margins were ignored"
    assert ink[1] >= 28

    from pypdf import PdfReader

    assert PdfReader(str(out)).metadata.get("/Title") == "Roundtrip"
