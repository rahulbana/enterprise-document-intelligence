# Name: Rahul Singh Bana
# Email: bana.saa@gmail.com
# LinkedIn: https://www.linkedin.com/in/rahulsinghbana
#
# Standalone image uploads (screenshots, scanned pages saved as an image,
# HEIC photos, ...) — OCR'd directly with pytesseract, no PDF wrapper
# involved. register_heif_opener() below makes PIL.Image.open handle .heic
# transparently, so it goes through the same code path as any other image.
# The .convert("RGB") is load-bearing, not cosmetic: pytesseract whitelists
# a fixed set of Image.format values and rejects anything else (including
# "HEIF") before it ever gets to the tesseract binary; convert() drops the
# source format tag so every input goes through pytesseract's own re-encode
# path instead of being rejected outright.

from typing import BinaryIO

import pillow_heif
import pytesseract
from PIL import Image

from app.ingestion.parsers.base import ParsedElement, Parser

pillow_heif.register_heif_opener()


class ImageParser(Parser):
    def extract_elements(self, file: BinaryIO) -> list[ParsedElement]:
        image = Image.open(file).convert("RGB")
        text = pytesseract.image_to_string(image).strip()
        return [ParsedElement(content=text)] if text else []
