"""Pure photo parsing and actual local inference on a generated display."""

from io import BytesIO

import pytest
from budget_under_test.ocr_core import extract_candidates, scan_bytes


def test_decimal_and_units():
    rows = extract_candidates([[[], "001234,567 m³", 0.97], [[], "54321.8 kWh", 0.9]])
    assert rows[0]["value"] == 1234.567
    assert rows[1]["value"] == 54321.8


def test_reject_identifiers_dates_and_low_confidence():
    assert (
        extract_candidates([[[], "1.8.0", 0.99], [[], "ABC123456", 0.99], [[], "11.02.2025", 0.99], [[], "12345", 0.4]])
        == []
    )


def test_candidates_deduplicated():
    rows = extract_candidates([[[], "12345", 0.8], [[], "12345", 0.98], [[], "54321", 0.9]])
    assert len(rows) == 2 and rows[0]["confidence"] == 0.98


def display_bytes():
    from PIL import Image, ImageDraw, ImageFont

    image = Image.new("RGB", (900, 200), "white")
    try:
        font = ImageFont.truetype("DejaVuSans.ttf", 90)
    except OSError:
        font = ImageFont.load_default(size=90)
    ImageDraw.Draw(image).text((30, 30), "123456", fill="black", font=font)
    data = BytesIO()
    image.save(data, format="PNG")
    return data.getvalue()


def test_real_engine_synthetic_display():
    pytest.importorskip("rapidocr_onnxruntime")
    assert any(row["value"] == 123456 for row in scan_bytes(display_bytes(), (0, 0, 100, 100)))


def test_invalid_image():
    pytest.importorskip("rapidocr_onnxruntime")
    with pytest.raises(ValueError, match="invalid_image"):
        scan_bytes(b"not an image", (0, 0, 100, 100))


def test_invalid_crop():
    pytest.importorskip("rapidocr_onnxruntime")
    with pytest.raises(ValueError, match="invalid_crop"):
        scan_bytes(display_bytes(), (60, 0, 40, 100))
