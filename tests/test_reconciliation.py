from decimal import Decimal

from src.buk.client import _parse_he_hours
from src.oracle.queries import aggregate_he_records
from src.reconciliation.engine import reconcile
from src.reconciliation.models import BukRecord, OracleRecord


# ── Helpers ───────────────────────────────────────────────────────────────────

def _oracle(rut: str, cod_haber: str, monto: float, sitio: str = "Sitio A") -> OracleRecord:
    return OracleRecord(
        periodo="05-2026",
        nom_sitio=sitio,
        num_reporte=100,
        estado_reporte="Aprobado",
        aprobador="Aprobador Test",
        rut=rut,
        nombre="Trabajador Test",
        cargo="Operario",
        cod_haber=cod_haber,
        monto=Decimal(str(monto)),
    )


def _buk(rut: str, cod: str, monto: float) -> BukRecord:
    return BukRecord(
        rut=rut,
        nombre="Trabajador Test",
        cod_concepto=cod,   # already translated to Oracle code
        nombre_concepto="Test concepto",
        monto=Decimal(str(monto)),
        periodo="052026",
    )


# ── Tests ─────────────────────────────────────────────────────────────────────

def test_empty_inputs_returns_empty_list() -> None:
    assert reconcile([], []) == []


def test_no_difference_when_amounts_match() -> None:
    rows = reconcile(
        [_oracle("12345678-9", "B001", 100_000)],
        [_buk("12345678-9",   "B001", 100_000)],
    )
    assert len(rows) == 1
    assert not rows[0].tiene_diferencia
    assert rows[0].diferencia == Decimal("0")


def test_difference_flagged_when_amounts_differ() -> None:
    rows = reconcile(
        [_oracle("12345678-9", "B001", 100_000)],
        [_buk("12345678-9",   "B001",  90_000)],
    )
    assert rows[0].tiene_diferencia
    assert rows[0].diferencia == Decimal("10000")
    assert rows[0].monto_oracle == Decimal("100000")
    assert rows[0].monto_buk    == Decimal("90000")


def test_record_only_in_oracle_is_flagged() -> None:
    rows = reconcile([_oracle("12345678-9", "B001", 50_000)], [])
    assert len(rows) == 1
    assert rows[0].tiene_diferencia
    assert rows[0].monto_buk == Decimal("0")


def test_record_only_in_buk_is_flagged() -> None:
    rows = reconcile([], [_buk("12345678-9", "B001", 50_000)])
    assert len(rows) == 1
    assert rows[0].tiene_diferencia
    assert rows[0].monto_oracle == Decimal("0")


def test_multiple_people_and_haberes() -> None:
    oracle = [
        _oracle("11111111-1", "B001",   100_000),
        _oracle("11111111-1", "HEX051",  20_000),
        _oracle("22222222-2", "B002",    80_000),
    ]
    buk = [
        _buk("11111111-1", "B001",   100_000),
        _buk("11111111-1", "HEX051",  20_000),
        _buk("22222222-2", "B002",    75_000),  # ← difference
    ]
    rows    = reconcile(oracle, buk)
    ok_rows = [r for r in rows if not r.tiene_diferencia]
    bad_rows = [r for r in rows if r.tiene_diferencia]

    assert len(rows) == 3
    assert len(ok_rows) == 2
    assert len(bad_rows) == 1
    assert bad_rows[0].rut       == "22222222-2"
    assert bad_rows[0].diferencia == Decimal("5000")


def test_rows_sorted_by_rut_then_cod_haber() -> None:
    oracle = [
        _oracle("22222222-2", "B002", 1),
        _oracle("11111111-1", "B001", 1),
        _oracle("11111111-1", "HEX051", 1),
    ]
    rows = reconcile(oracle, [])
    keys = [(r.rut, r.cod_haber) for r in rows]
    assert keys == sorted(keys)


def test_he_description_populated() -> None:
    rows = reconcile([_oracle("11111111-1", "HEX051", 10_000)], [])
    assert rows[0].descripcion_haber == "Hora Extra 50%"


def test_unknown_cod_haber_uses_code_as_description() -> None:
    rows = reconcile([_oracle("11111111-1", "B999", 10_000)], [])
    assert rows[0].descripcion_haber == "B999"


def test_aggregate_he_sums_subcodes_into_canonical() -> None:
    """HEX051-HEX059 son sub-códigos al 50% → deben sumar en un único HEX051."""
    oracle = [
        _oracle("11111111-1", "HEX051", 13),
        _oracle("11111111-1", "HEX052",  5),
        _oracle("11111111-1", "HEX059",  2),
        _oracle("11111111-1", "HEX100",  8),  # 100% — otro grupo
        _oracle("11111111-1", "BONOBR", 100_000),  # bono — no se toca
    ]
    result = aggregate_he_records(oracle)
    # debe quedar: BONOBR + HEX051(=20) + HEX100(=8)
    assert len(result) == 3
    by_code = {r.cod_haber: r for r in result}
    assert by_code["HEX051"].monto == Decimal("20")
    assert by_code["HEX100"].monto == Decimal("8")
    assert by_code["BONOBR"].monto == Decimal("100000")


def test_parse_he_hours_parentheses() -> None:
    assert _parse_he_hours("(28)")    == Decimal("28")
    assert _parse_he_hours("(28.5)")  == Decimal("28.5")
    assert _parse_he_hours("(3)")     == Decimal("3")
    assert _parse_he_hours(None)      is None
    assert _parse_he_hours("")        is None
    assert _parse_he_hours("sin dato") is None


def test_aggregate_he_different_people_not_merged() -> None:
    """Personas distintas no se mezclan al agregar."""
    oracle = [
        _oracle("11111111-1", "HEX051", 10),
        _oracle("22222222-2", "HEX051",  5),
        _oracle("11111111-1", "HEX052",  3),
    ]
    result = aggregate_he_records(oracle)
    by_rut = {r.rut: r for r in result}
    assert by_rut["11111111-1"].monto == Decimal("13")
    assert by_rut["22222222-2"].monto == Decimal("5")
