_ocr = None


def get_ocr():
    global _ocr
    if _ocr is None:
        from rapidocr_onnxruntime import RapidOCR
        _ocr = RapidOCR()
    return _ocr


def ocr_image(image_bytes: bytes) -> str:
    """Run local OCR (rapidocr-onnxruntime) on raw image bytes. Returns extracted text."""
    import numpy as np
    from PIL import Image
    from io import BytesIO

    img = Image.open(BytesIO(image_bytes))
    arr = np.array(img.convert("RGB"))
    result, _ = get_ocr()(arr)
    if not result:
        return ""
    lines = []
    for box, text, conf in result:
        if text and text.strip():
            lines.append(text.strip())
    return "\n".join(lines)
