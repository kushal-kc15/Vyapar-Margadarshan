"""Optional Tesseract receipt-scanning logic.

This module is intentionally not connected to the receipt upload/API/task flow.
It documents a local OCR alternative that can be enabled in a future change
after the Tesseract binary and ``pytesseract`` dependency are installed.
"""

from pathlib import Path

from PIL import Image, ImageFilter, ImageOps, UnidentifiedImageError


class TesseractScannerError(RuntimeError):
    """Raised when the optional local scanner cannot process an image."""


def preprocess_receipt(image):
    """Improve receipt contrast before sending pixels to Tesseract."""
    grayscale = ImageOps.grayscale(image)
    width, height = grayscale.size
    if width < 1600:
        scale = 1600 / max(width, 1)
        grayscale = grayscale.resize(
            (1600, max(1, round(height * scale))),
            Image.Resampling.LANCZOS,
        )

    contrasted = ImageOps.autocontrast(grayscale)
    denoised = contrasted.filter(ImageFilter.MedianFilter(size=3))
    return denoised.point(lambda pixel: 255 if pixel > 165 else 0)


def scan_receipt_with_tesseract(image_path, *, language='eng'):
    """Return plain OCR text from a receipt image using local Tesseract.

    This function is dormant: no production code imports or calls it.
    """
    try:
        import pytesseract
    except ImportError as exc:
        raise TesseractScannerError(
            'Install pytesseract and the Tesseract OCR binary before enabling this scanner.'
        ) from exc

    path = Path(image_path)
    if not path.is_file():
        raise TesseractScannerError(f'Receipt image does not exist: {path}')

    try:
        with Image.open(path) as image:
            prepared = preprocess_receipt(image)
            text = pytesseract.image_to_string(
                prepared,
                lang=language,
                config='--oem 3 --psm 6',
            )
    except (OSError, UnidentifiedImageError, pytesseract.TesseractError) as exc:
        raise TesseractScannerError('Tesseract could not scan the receipt image.') from exc

    return '\n'.join(line.strip() for line in text.splitlines() if line.strip())
