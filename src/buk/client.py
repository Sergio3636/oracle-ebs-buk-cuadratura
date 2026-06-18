import logging
import re
from decimal import Decimal

import requests

from src.config.settings import settings
from src.reconciliation.models import BukRecord
from src.utils import normalize_rut

logger = logging.getLogger(__name__)

# ── HE item_codes en Buk → Oracle cod_haber canónico ─────────────────────────
# Buk consolida todas las horas extras por porcentaje en un único item_code.
# El monto (amount) es CLP; las horas se extraen del campo description: "(28)".
_BUK_HE_MAP: dict[str, str] = {
    # Formato especial horas_extras_*
    "horas_extras_50percent":  "HEX051",
    "horas_extras_100percent": "HEX100",
    "horas_extras_80percent":  "HEX102",
    "horas_extras_70percent":  "HEX103",
    # Formato l{N} — Buk usa esto para 80% y 70% (no están en XXMAPEO_HABER)
    "l102": "HEX102",
    "l103": "HEX103",
}

_HE_HOURS_RE = re.compile(r"\((\d+(?:[.,]\d+)?)\)")


def _parse_he_hours(description: str | None) -> Decimal | None:
    """Extrae las horas de un campo description Buk como '(28)' o '(28.5)'."""
    if not description:
        return None
    m = _HE_HOURS_RE.search(description)
    if m:
        return Decimal(m.group(1).replace(",", "."))
    # fallback: si description es solo el número
    try:
        return Decimal(description.strip())
    except Exception:
        return None


class BukClient:
    _ENDPOINT = "payroll_detail/month"

    def __init__(self, oracle_map: dict[str, str] | None = None) -> None:
        """
        Args:
            oracle_map: Buk item_code (bonos) → Oracle cod_haber.
                        Built from APPS.XXMAPEO_HABER via get_buk_to_oracle_map().
                        Only used for bono codes (l-prefixed item_codes).
                        HE item_codes (horas_extras_*) are handled separately.
        """
        self._oracle_map: dict[str, str] = oracle_map or {}

        self._session = requests.Session()
        self._session.headers.update({
            "auth_token": settings.buk_api_token,
            "Accept": "application/json",
        })
        base = settings.buk_api_url
        if not base.endswith("/"):
            base += "/"
        self._base_url = base

    # ── Public ────────────────────────────────────────────────────────────────

    def get_payroll_records(self, periodo: str) -> list[BukRecord]:
        """Returns bono and HE lines from Buk for the given period.

        Bonos: monto = CLP amount from the 'amount' field.
        HE:    monto = hours from the 'description' field (e.g. '(28)' → 28).
        """
        if not settings.buk_api_token:
            logger.warning("BUK_API_TOKEN not configured — returning empty Buk dataset")
            return []

        # periodo "052026" → date="01-05-2026"
        mm   = periodo[:2]
        yyyy = periodo[2:]
        date_param = f"01-{mm}-{yyyy}"

        records: list[BukRecord] = []
        page = 1
        total_pages = 1

        while page <= total_pages:
            data = self._get(
                self._ENDPOINT,
                params={"date": date_param, "page": page},
            )
            pagination  = data.get("pagination", {})
            total_pages = pagination.get("total_pages", 1)

            for liquidacion in data.get("data", []):
                records.extend(self._extract_haberes(liquidacion, periodo))

            logger.debug("Buk page %d/%d — %d records so far", page, total_pages, len(records))
            page += 1

        logger.info("Buk haber lines fetched for %s (date=%s): %d", periodo, date_param, len(records))
        return records

    # ── Private ───────────────────────────────────────────────────────────────

    def _get(self, path: str, params: dict | None = None) -> dict:
        url = f"{self._base_url}{path}"
        response = self._session.get(url, params=params, timeout=30)
        response.raise_for_status()
        return response.json()

    def _extract_haberes(self, liquidacion: dict, periodo: str) -> list[BukRecord]:
        rut = normalize_rut(liquidacion.get("rut", ""))
        result: list[BukRecord] = []

        for line in liquidacion.get("lines_settlement", []):
            if line.get("type") != "haber":
                continue

            item_code: str = line.get("item_code") or ""
            if not item_code:
                continue

            # Resolve oracle code: special horas_extras_* map first, then l{N} map
            if item_code in _BUK_HE_MAP:
                oracle_code = _BUK_HE_MAP[item_code]
            else:
                oracle_code = self._oracle_map.get(item_code, "")

            if not oracle_code:
                continue

            # H% codes → horas from description field (e.g. "(11)" = 11 HH)
            # B% codes → CLP amount field
            if oracle_code.startswith("H"):
                hours = _parse_he_hours(line.get("description"))
                if hours is None:
                    logger.debug(
                        "HE sin horas en description para %s / %s: %r",
                        rut, item_code, line.get("description"),
                    )
                    continue
                monto = hours
            else:
                monto = Decimal(str(line.get("amount", 0)))

            result.append(BukRecord(
                rut=rut,
                nombre="",
                cod_concepto=oracle_code,
                nombre_concepto=line.get("name", ""),
                monto=monto,
                periodo=periodo,
            ))

        return result
