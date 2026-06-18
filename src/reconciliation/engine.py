from dataclasses import replace
from decimal import Decimal

from src.oracle.queries import HABER_DESCRIPTIONS
from src.reconciliation.models import BukRecord, OracleRecord, ReconciliationRow


def reconcile(
    oracle_records: list[OracleRecord],
    buk_records: list[BukRecord],
    haber_descriptions: dict[str, str] | None = None,
) -> list[ReconciliationRow]:
    """Compares Oracle and Buk records person-by-person, grouped by cod_haber.

    BukRecord.cod_concepto must already be translated to Oracle cod_haber codes
    (done inside BukClient before calling this function).

    Returns rows sorted by (rut, cod_haber). Rows with differences are flagged
    via ReconciliationRow.tiene_diferencia.
    """
    descriptions = haber_descriptions if haber_descriptions is not None else HABER_DESCRIPTIONS

    # Index Oracle records by (rut, cod_haber)
    oracle_index: dict[tuple[str, str], OracleRecord] = {}
    for rec in oracle_records:
        key = (rec.rut, rec.cod_haber)
        if key in oracle_index:
            existing = oracle_index[key]
            oracle_index[key] = replace(existing, monto=existing.monto + rec.monto)
        else:
            oracle_index[key] = rec

    # Index Buk records by (rut, cod_concepto) → accumulated monto
    buk_index: dict[tuple[str, str], Decimal] = {}
    for rec in buk_records:
        key = (rec.rut, rec.cod_concepto)
        buk_index[key] = buk_index.get(key, Decimal("0")) + rec.monto

    # Union of all keys → one row per (person × haber)
    all_keys = sorted(set(oracle_index.keys()) | set(buk_index.keys()))

    rows: list[ReconciliationRow] = []
    for key in all_keys:
        rut, cod_haber = key
        oracle_rec = oracle_index.get(key)
        monto_oracle = oracle_rec.monto if oracle_rec else Decimal("0")
        monto_buk = buk_index.get(key, Decimal("0"))

        rows.append(
            ReconciliationRow(
                periodo=oracle_rec.periodo if oracle_rec else "",
                nom_sitio=oracle_rec.nom_sitio if oracle_rec else "",
                num_reporte=oracle_rec.num_reporte if oracle_rec else 0,
                estado_reporte=oracle_rec.estado_reporte if oracle_rec else "",
                rut=rut,
                nombre=(oracle_rec.nombre or "") if oracle_rec else "",
                cargo=(oracle_rec.cargo or "") if oracle_rec else "",
                cod_haber=cod_haber,
                descripcion_haber=descriptions.get(cod_haber, cod_haber),
                monto_oracle=monto_oracle,
                monto_buk=monto_buk,
                diferencia=monto_oracle - monto_buk,
            )
        )

    return rows
