"""Primitives de sécurité : mots de passe, téléphones marocains, codes aléatoires."""

from __future__ import annotations

import base64
import hashlib
import hmac
import re
import secrets
import string
from decimal import Decimal, InvalidOperation

from .errors import ValidationError

_SCRYPT_N = 2**14
_SCRYPT_R = 8
_SCRYPT_P = 1
_SCRYPT_DKLEN = 64
_PHONE_RE = re.compile(r"^\+212[5-7]\d{8}$")
_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
# Alphabet sans caractères ambigus (pas de O/0, I/1).
_CODE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"


def _b64e(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def _b64d(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


def hash_password(password: str) -> str:
    """Hache un mot de passe avec scrypt + sel aléatoire (aucun mot de passe en clair)."""
    if not isinstance(password, str) or not password:
        raise ValidationError("Le mot de passe est obligatoire.", code="invalid_password")
    salt = secrets.token_bytes(16)
    digest = hashlib.scrypt(
        password.encode("utf-8"),
        salt=salt,
        n=_SCRYPT_N,
        r=_SCRYPT_R,
        p=_SCRYPT_P,
        dklen=_SCRYPT_DKLEN,
    )
    return f"scrypt${_SCRYPT_N}${_SCRYPT_R}${_SCRYPT_P}${_b64e(salt)}${_b64e(digest)}"


def verify_password(password: str, encoded: str | None) -> bool:
    """Vérifie un mot de passe en temps constant. Ne lève jamais sur un hash corrompu."""
    if not password or not encoded:
        return False
    try:
        scheme, n, r, p, salt_b64, digest_b64 = encoded.split("$")
        if scheme != "scrypt":
            return False
        digest = hashlib.scrypt(
            password.encode("utf-8"),
            salt=_b64d(salt_b64),
            n=int(n),
            r=int(r),
            p=int(p),
            dklen=len(_b64d(digest_b64)),
        )
        return hmac.compare_digest(digest, _b64d(digest_b64))
    except (ValueError, TypeError, MemoryError):
        return False


# Hash factice pour égaliser approximativement le temps de réponse d'un compte absent.
DUMMY_PASSWORD_HASH = hash_password("WafaClub-dummy-password-2026")


def validate_password_strength(password: str) -> None:
    if len(password) < 8:
        raise ValidationError(
            "Le mot de passe doit contenir au moins 8 caractères.",
            code="password_too_short",
        )
    if not any(char.isalpha() for char in password) or not any(char.isdigit() for char in password):
        raise ValidationError(
            "Le mot de passe doit contenir au moins une lettre et un chiffre.",
            code="password_too_weak",
        )


def normalize_moroccan_phone(raw: str | None) -> str:
    """Normalise 06/07/05…, +212…, 00212… vers +212XXXXXXXXX."""
    if not raw:
        raise ValidationError("Le numéro de téléphone est obligatoire.", code="invalid_phone")
    value = re.sub(r"[\s.\-()/]", "", str(raw))
    if value.startswith("+212"):
        rest = value[4:]
    elif value.startswith("00212"):
        rest = value[5:]
    elif value.startswith("212") and len(value) == 12:
        rest = value[3:]
    elif value.startswith("0"):
        rest = value[1:]
    else:
        rest = value
    normalized = f"+212{rest}"
    if not _PHONE_RE.match(normalized):
        raise ValidationError(
            "Numéro marocain invalide. Exemple : 06 61 23 45 67.",
            code="invalid_phone",
        )
    return normalized


def validate_email(email: str | None) -> str | None:
    if not email:
        return None
    value = email.strip().lower()
    if not _EMAIL_RE.match(value):
        raise ValidationError("Adresse e-mail invalide.", code="invalid_email")
    return value


def generate_code(prefix: str, groups: int = 3, group_length: int = 4) -> str:
    """Code aléatoire non séquentiel, lisible, ex. WFC-8M2K-6RP4-Q9TX."""
    chunks = ["".join(secrets.choice(_CODE_ALPHABET) for _ in range(group_length)) for _ in range(groups)]
    return f"{prefix}-" + "-".join(chunks)


def generate_qr_token() -> str:
    return secrets.token_urlsafe(28)


def generate_reference(prefix: str = "PUR") -> str:
    return f"{prefix}-{secrets.token_hex(8).upper()}"


def slugify(value: str) -> str:
    translation = str.maketrans("àâäéèêëîïôöùûüç", "aaaeeeeiioouuuc")
    cleaned = value.lower().translate(translation)
    return "".join(ch if ch in string.ascii_lowercase + string.digits else "-" for ch in cleaned).strip("-")


def to_decimal(value: str | float | int | Decimal, *, field: str = "montant") -> Decimal:
    try:
        result = Decimal(str(value)).quantize(Decimal("0.01"))
    except (InvalidOperation, ValueError, TypeError) as exc:
        raise ValidationError(f"Le {field} est invalide.", code="invalid_amount") from exc
    return result
