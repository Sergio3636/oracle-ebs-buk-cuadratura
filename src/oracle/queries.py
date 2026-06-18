import dataclasses
from decimal import Decimal
from typing import Any

from src.reconciliation.models import OracleRecord
from src.utils import normalize_rut

# ── HE classification ────────────────────────────────────────────────────────
# Oracle tracks HE by day-type sub-code; Buk consolidates each rate into one.
# Canonical code = the single code used for comparison against Buk.
HE_50_PERCENT: frozenset[str] = frozenset({
    "HEX051", "HEX052", "HEX053", "HEX054", "HEX055",
    "HEX056", "HEX057", "HEX058", "HEX059", "HEX060", "HEX062",
})
HE_100_PERCENT: frozenset[str] = frozenset({"HEX100", "HEX101", "HEX064"})
HE_80_PERCENT:  frozenset[str] = frozenset({"HEX102"})
HE_70_PERCENT:  frozenset[str] = frozenset({"HEX103"})

# Maps every sub-code to its canonical code (the one used in reconciliation)
HE_CANONICAL: dict[str, str] = {
    **{code: "HEX051" for code in HE_50_PERCENT},
    **{code: "HEX100" for code in HE_100_PERCENT},
    **{code: "HEX102" for code in HE_80_PERCENT},
    **{code: "HEX103" for code in HE_70_PERCENT},
}

HABER_DESCRIPTIONS: dict[str, str] = {
    # Descriptions indexed by canonical code (the sub-codes are no longer used after aggregation)
    "HEX051": "Hora Extra 50%",
    "HEX100": "Hora Extra 100%",
    "HEX102": "Hora Extra 80%",
    "HEX103": "Hora Extra 70%",
    # Keep sub-code descriptions as fallback (e.g. when not yet aggregated)
    **{code: "Hora Extra 50%"  for code in HE_50_PERCENT},
    **{code: "Hora Extra 100%" for code in HE_100_PERCENT},
    **{code: "Hora Extra 80%"  for code in HE_80_PERCENT},
    **{code: "Hora Extra 70%"  for code in HE_70_PERCENT},
}

# ── Base SQL ──────────────────────────────────────────────────────────────────
# :periodo  →  MMYYYY string, e.g. '052026'
_BASE_SQL = """
SELECT
    periodo,
    nom_sitio,
    num_reporte,
    estado_reporte,
    aprobador,
    rut,
    nombre,
    (SELECT xx.cargo FROM xxhr_personal_jdc xx WHERE xx.rut = x.rut) cargo,
    cod_haber,
    SUM(valor) monto
FROM (
    SELECT
        s.nom_sitio,
        TO_CHAR(c.periodo, 'mm-yyyy')                                       periodo,
        c.carga_remuneraciones_id                                            num_reporte,
        DECODE(c.estado,
               '01', 'Ingresado',
               '02', 'Envio a Jefatura',
               '03', 'Rechazado',
               '04', 'Aprobado',
               '05', 'Cargado en RRHH')                                     estado_reporte,
        (SELECT DISTINCT full_name
           FROM apps.per_all_people_f
          WHERE person_id = c.owner)                                         aprobador,
        d.rut,
        (SELECT p.nombre FROM xxhr_personal_jdc p WHERE p.rut = d.rut)     nombre,
        d.cod_haber,
        d.valor
    FROM apps.xxgl_carga_remu_detalle d
    JOIN apps.xxgl_carga_remu          c
      ON c.carga_remuneraciones_id = d.carga_remuneraciones_id
    JOIN apps.xxgl_sitio               s
      ON c.sitio_id = s.sitio_id
    WHERE {cod_haber_filter}
      AND TO_CHAR(c.periodo, 'MMyyyy') = :periodo
) x
GROUP BY
    periodo, nom_sitio, num_reporte, estado_reporte, aprobador,
    rut, nombre, cod_haber
ORDER BY rut, cod_haber
"""

BONOS_SQL:       str = _BASE_SQL.format(cod_haber_filter="d.cod_haber LIKE 'B%'")
HE_SQL:          str = _BASE_SQL.format(cod_haber_filter="d.cod_haber LIKE 'H%'")
ALL_HABERES_SQL: str = _BASE_SQL.format(
    cod_haber_filter="(d.cod_haber LIKE 'B%' OR d.cod_haber LIKE 'H%')"
)


def _row_to_record(row: tuple[Any, ...]) -> OracleRecord:
    return OracleRecord(
        periodo=str(row[0]) if row[0] is not None else "",
        nom_sitio=str(row[1]) if row[1] is not None else "",
        num_reporte=int(row[2]) if row[2] is not None else 0,
        estado_reporte=str(row[3]) if row[3] is not None else "",
        aprobador=str(row[4]) if row[4] is not None else None,
        rut=normalize_rut(str(row[5])) if row[5] is not None else "",
        nombre=str(row[6]) if row[6] is not None else None,
        cargo=str(row[7]) if row[7] is not None else None,
        cod_haber=str(row[8]) if row[8] is not None else "",
        monto=Decimal(str(row[9])) if row[9] is not None else Decimal("0"),
    )


def get_bonos(connection: Any, periodo: str) -> list[OracleRecord]:
    cursor = connection.cursor()
    cursor.execute(BONOS_SQL, periodo=periodo)
    return [_row_to_record(row) for row in cursor.fetchall()]


def get_horas_extras(connection: Any, periodo: str) -> list[OracleRecord]:
    cursor = connection.cursor()
    cursor.execute(HE_SQL, periodo=periodo)
    return [_row_to_record(row) for row in cursor.fetchall()]


def get_all_haberes(connection: Any, periodo: str) -> list[OracleRecord]:
    """Fetches bonos (B%) and horas extras (H%) for the given period."""
    cursor = connection.cursor()
    cursor.execute(ALL_HABERES_SQL, periodo=periodo)
    return [_row_to_record(row) for row in cursor.fetchall()]


def aggregate_he_records(records: list[OracleRecord]) -> list[OracleRecord]:
    """Consolidates Oracle HE sub-codes into one canonical code per rate per person.

    Oracle tracks overtime with multiple sub-codes (HEX051=día hábil, HEX052=nocturno,
    etc.) while Buk stores a single aggregated line per rate (HEX051 for 50%, etc.).
    This function sums all sub-codes with the same rate for the same RUT into one record.
    """
    bonos = [r for r in records if not r.cod_haber.startswith("H")]
    he    = [r for r in records if r.cod_haber.startswith("H")]

    # Accumulate by (rut, canonical_code); preserve first-seen record for metadata
    accumulated: dict[tuple[str, str], OracleRecord] = {}
    for rec in he:
        canonical = HE_CANONICAL.get(rec.cod_haber, rec.cod_haber)
        key = (rec.rut, canonical)
        if key in accumulated:
            existing = accumulated[key]
            accumulated[key] = dataclasses.replace(
                existing,
                cod_haber=canonical,
                monto=existing.monto + rec.monto,
            )
        else:
            accumulated[key] = dataclasses.replace(rec, cod_haber=canonical)

    return bonos + list(accumulated.values())


def get_haber_descriptions(connection: Any) -> dict[str, str]:
    """Returns cod_haber → description from the official Oracle value set XX_HABERES_PAYROLL.

    Queries FND_FLEX_VALUES (set ID 1010039) joined with FND_FLEX_VALUES_TL for the
    session language. Callers should merge the result with HABER_DESCRIPTIONS so that
    HE canonical codes (HEX051, HEX100, etc.) keep their "Hora Extra X%" labels
    instead of the sub-code descriptions stored in the value set.

    Merge pattern in callers:
        descriptions = {**get_haber_descriptions(conn), **HABER_DESCRIPTIONS}
    """
    SQL = """
    SELECT fv.flex_value, tl.description
    FROM apps.fnd_flex_values fv
    JOIN apps.fnd_flex_values_tl tl
      ON tl.flex_value_id = fv.flex_value_id
     AND tl.language      = USERENV('LANG')
    WHERE fv.flex_value_set_id = 1010039
    ORDER BY fv.flex_value
    """
    cursor = connection.cursor()
    cursor.execute(SQL)
    return {str(val): str(desc) for val, desc in cursor.fetchall() if desc}


def get_buk_to_oracle_map(connection: Any) -> dict[str, str]:
    """Builds Buk item_code → Oracle cod_haber map from APPS.XXMAPEO_HABER.

    Only includes TIPO='H' (haber/income) entries where cod_haber starts with B or H
    (matching the Oracle SQL filter for bonos and horas extras).
    Buk item codes follow the pattern 'l' + str(COD_WINPER), e.g. l195, l51.
    """
    SQL = """
    SELECT cohade, cod_winper
    FROM apps.xxmapeo_haber
    WHERE tipo = 'H'
      AND (cohade LIKE 'B%' OR cohade LIKE 'H%')
    """
    cursor = connection.cursor()
    cursor.execute(SQL)
    result: dict[str, str] = {}
    for cohade, cod_winper in cursor.fetchall():
        if cod_winper is not None:
            buk_code = f"l{int(cod_winper)}"
            result[buk_code] = str(cohade)
    return result
