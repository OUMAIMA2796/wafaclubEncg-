from __future__ import annotations

import json
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path

from wafaclub.i18n import (
    SUPPORTED_LANGUAGES,
    format_date,
    format_datetime,
    format_mad,
    format_points,
    is_rtl,
    language_label,
    normalize_language,
    t,
)
from wafaclub.qrcodes import extract_qr_token, qr_payload, qr_png_bytes

I18N_DIR = Path(__file__).resolve().parent.parent / "wafaclub" / "i18n"


def _load(name: str) -> dict:
    return json.loads((I18N_DIR / f"{name}.json").read_text(encoding="utf-8"))


def test_french_and_arabic_translation_keys_are_complete():
    fr = _load("fr")
    ar = _load("ar")
    missing = sorted(set(fr) - set(ar))
    assert not missing, f"Clés arabes manquantes : {missing[:10]}"
    assert t("nav.client.card", "fr") == "Ma carte & QR"
    assert t("nav.client.card", "ar") != "nav.client.card"


def test_only_french_and_arabic_are_supported():
    assert SUPPORTED_LANGUAGES == ("fr", "ar")
    assert normalize_language("darija") == "fr"
    assert language_label("darija") == "Français"
    assert t("nav.client.points", "darija") == t("nav.client.points", "fr")


def test_rtl_and_formatters():
    assert is_rtl("ar") is True
    assert is_rtl("fr") is False
    assert is_rtl("darija") is False
    assert "1" in format_mad(Decimal("1250.50"), "fr")
    assert format_mad(Decimal("1250.50"), "fr").endswith("MAD")
    assert format_points(1500, "fr").endswith("500")
    assert format_date(date(2026, 11, 10), "fr") == "10/11/2026"
    assert format_datetime(datetime(2026, 11, 10, 14, 30), "ar") == "10/11/2026 · 14:30"


def test_translation_placeholders():
    message = t("client.dashboard.greeting", "fr", name="Yasmine")
    assert "Yasmine" in message
    message_ar = t("client.dashboard.greeting", "ar", name="ياسمين")
    assert "ياسمين" in message_ar


def test_qr_payload_roundtrip_and_png():
    token = "QR_TOKEN_TEST_123456789"
    payload = qr_payload(token)
    assert payload.startswith("WAFACLUB:QR:")
    assert extract_qr_token(payload) == token
    png = qr_png_bytes(payload)
    assert png[:8] == b"\x89PNG\r\n\x1a\n"
    assert len(png) > 500
