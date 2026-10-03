"""Offline photo OCR; models ship inside the pinned RapidOCR wheel.

The App accepts photos through authenticated Ingress and discards image bytes
after processing. Only user-confirmed numeric readings are stored. No cloud API.
"""

import re
import threading

from .model import number

_LOCK = threading.Lock()
_ENGINE = None


def extract_candidates(results):
    """Conservative numeric tokens; never guess a missing decimal separator.

    The caller must crop to the reading area and confirm the suggestion.
    Numeric serial numbers are intrinsically ambiguous without that context.
    """
    candidates = {}
    for _box, text, confidence in results or []:
        text = text.strip().replace("\u00a0", " ")
        # Allow a reading followed by its unit, but reject dates, meter IDs
        # containing letters, and tariff codes such as 1.8.0.
        match = re.fullmatch(r"([0-9]{1,10}(?:[.,][0-9]{1,3})?)\s*(?:kWh|m³|m3)?", text, re.IGNORECASE)
        if match is None or confidence < 0.5:
            continue
        value = number(match.group(1).replace(",", "."))
        candidates[value] = max(float(confidence), candidates.get(value, 0))
    return [
        {"value": value, "confidence": confidence}
        for value, confidence in sorted(candidates.items(), key=lambda item: item[1], reverse=True)
    ][:8]


def scan_bytes(payload, crop):
    """Read JPEG/PNG bytes in a bounded, local inference worker."""
    from io import BytesIO

    import numpy as np
    from PIL import Image, ImageOps, UnidentifiedImageError

    global _ENGINE
    if len(payload) > 12 * 1024 * 1024:
        raise ValueError("image_too_large")
    try:
        with Image.open(BytesIO(payload)) as original:
            if original.format not in ("JPEG", "PNG"):
                raise ValueError("invalid_image")
            if original.width * original.height > 20_000_000:
                raise ValueError("image_too_large")
            image = ImageOps.exif_transpose(original).convert("RGB")
            left, top, right, bottom = crop
            if not 0 <= left < right <= 100 or not 0 <= top < bottom <= 100:
                raise ValueError("invalid_crop")
            image = image.crop(
                (
                    int(image.width * left / 100),
                    int(image.height * top / 100),
                    int(image.width * right / 100),
                    int(image.height * bottom / 100),
                )
            )
            if min(image.size) < 10:
                raise ValueError("invalid_crop")
            image.thumbnail((2000, 2000))
            pixels = np.asarray(image)[:, :, ::-1].copy()
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError) as err:
        raise ValueError("invalid_image") from err
    with _LOCK:
        if _ENGINE is None:
            import onnxruntime
            from rapidocr_onnxruntime import RapidOCR

            onnxruntime.disable_telemetry_events()
            _ENGINE = RapidOCR(intra_op_num_threads=1, inter_op_num_threads=1)
        results, _elapsed = _ENGINE(pixels)
    candidates = extract_candidates(results)
    if not candidates:
        raise ValueError("no_digits")
    return candidates
