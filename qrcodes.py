"""Génération et lecture des QR codes WafaClub."""

from __future__ import annotations

import io
import re

import qrcode

QR_PREFIX = "WAFACLUB:QR:"
_QR_DEEP_LINK = "wafaclub://loyalty/"


def qr_payload(token: str) -> str:
    return f"{QR_PREFIX}{token}"


def extract_qr_token(value: str) -> str:
    raw = (value or "").strip()
    if raw.startswith(QR_PREFIX):
        raw = raw[len(QR_PREFIX) :].strip()
    elif raw.startswith(_QR_DEEP_LINK):
        raw = raw[len(_QR_DEEP_LINK) :].strip()
    if not re.fullmatch(r"[A-Za-z0-9_\-]{8,100}", raw):
        raise ValueError("Contenu de QR code invalide.")
    return raw


def qr_png_bytes(payload: str, box_size: int = 9, border: int = 2) -> bytes:
    qr = qrcode.QRCode(
        version=None, error_correction=qrcode.constants.ERROR_CORRECT_M, box_size=box_size, border=border
    )
    qr.add_data(payload)
    qr.make(fit=True)
    image = qr.make_image(fill_color="#0B3C6E", back_color="white")
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def decode_qr_image(image_bytes: bytes) -> str | None:
    """Décode une photo de QR code. OpenCV est optionnel et importé à la demande."""
    try:
        import cv2
        import numpy as np
    except ImportError:
        return None
    try:
        array = np.frombuffer(image_bytes, dtype=np.uint8)
        image = cv2.imdecode(array, cv2.IMREAD_COLOR)
        if image is None:
            return None
        detector = cv2.QRCodeDetector()
        value, _points, _straight = detector.detectAndDecode(image)
        if value:
            return value
        # Deuxième tentative après agrandissement, utile sur les captures d'écran.
        upscaled = cv2.resize(image, None, fx=1.8, fy=1.8, interpolation=cv2.INTER_CUBIC)
        value, _points, _straight = detector.detectAndDecode(upscaled)
        return value or None
    except Exception:  # image corrompue : on échoue proprement côté UI
        return None
