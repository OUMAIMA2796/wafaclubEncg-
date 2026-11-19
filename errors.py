"""Exceptions métier WafaClub avec codes traduisibles côté interface."""

from __future__ import annotations


class WafaClubError(Exception):
    """Erreur métier de base. Le code est utilisé par l'interface i18n."""

    code = "generic"
    default_message = "Une erreur est survenue."

    def __init__(self, message: str | None = None, *, code: str | None = None) -> None:
        self.message = message or self.default_message
        if code:
            self.code = code
        super().__init__(self.message)


class ValidationError(WafaClubError):
    code = "validation"
    default_message = "Les informations fournies sont invalides."


class AuthError(WafaClubError):
    code = "auth_failed"
    default_message = "Identifiants invalides."


class AccessDenied(WafaClubError):
    code = "access_denied"
    default_message = "Vous n'êtes pas autorisé à effectuer cette action."


class NotFoundError(WafaClubError):
    code = "not_found"
    default_message = "Élément introuvable."


class ConflictError(WafaClubError):
    code = "conflict"
    default_message = "Cette opération est en conflit avec les données existantes."


class ImmutableLedgerError(WafaClubError):
    code = "immutable_ledger"
    default_message = "Le journal des points est immuable."
