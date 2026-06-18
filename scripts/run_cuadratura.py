#!/usr/bin/env python
"""
Proceso de cuadratura mensual Oracle vs Buk.

Genera un Excel con la comparación haber por haber, persona por persona,
marca en rojo las diferencias y lo envía por correo.

Uso:
    # Dentro del contenedor
    docker compose run --rm app python scripts/run_cuadratura.py \\
        --periodo 052026 --emails rrhh@empresa.cl,finanzas@empresa.cl

    # Solo generar Excel (sin enviar correo)
    docker compose run --rm app python scripts/run_cuadratura.py \\
        --periodo 052026 --no-email --output /app/reportes
"""

import argparse
import logging
import sys
from pathlib import Path

# Run from project root without needing to install the package
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.buk.client import BukClient
from src.database.connection import close_pool, get_connection, init_oracle_client
from src.notifications.email import send_cuadratura
from src.oracle.queries import (
    HABER_DESCRIPTIONS,
    aggregate_he_records,
    get_all_haberes,
    get_buk_to_oracle_map,
    get_haber_descriptions,
)
from src.reconciliation.engine import reconcile
from src.reports.excel import generate_excel

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s — %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("cuadratura")


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Cuadratura mensual Oracle vs Buk",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--periodo",
        required=True,
        metavar="MMYYYY",
        help="Período a procesar, ej: 052026",
    )
    parser.add_argument(
        "--emails",
        default="",
        metavar="EMAIL[,EMAIL...]",
        help="Destinatarios del reporte separados por coma",
    )
    parser.add_argument(
        "--output",
        default="./reportes",
        metavar="DIR",
        help="Directorio de salida del Excel (default: ./reportes)",
    )
    parser.add_argument(
        "--no-email",
        action="store_true",
        help="Genera el Excel pero no envía correo",
    )
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    periodo: str = args.periodo.strip()

    if len(periodo) != 6 or not periodo.isdigit():
        logger.error(
            "Período inválido '%s'. Formato esperado: MMYYYY (ej: 052026)", periodo
        )
        sys.exit(1)

    recipients: list[str] = [e.strip() for e in args.emails.split(",") if e.strip()]
    output_dir = Path(args.output)

    # ── 1. Extracción Oracle ──────────────────────────────────────────────────
    logger.info("Extrayendo datos Oracle para período %s …", periodo)
    init_oracle_client()
    try:
        with get_connection() as conn:
            oracle_records    = get_all_haberes(conn, periodo)
            buk_to_oracle_map = get_buk_to_oracle_map(conn)
            oracle_hab_desc   = get_haber_descriptions(conn)
    finally:
        close_pool()

    oracle_records = aggregate_he_records(oracle_records)

    # Value set descriptions for bonos; HABER_DESCRIPTIONS wins for HE canonical codes
    all_descriptions = {**oracle_hab_desc, **HABER_DESCRIPTIONS}

    logger.info(
        "Oracle: %d registros (HE agregadas) | Mapa Buk→Oracle: %d | Descripciones: %d",
        len(oracle_records), len(buk_to_oracle_map), len(all_descriptions),
    )

    # ── 2. Extracción Buk ─────────────────────────────────────────────────────
    logger.info("Extrayendo datos Buk para período %s …", periodo)
    buk_records = BukClient(oracle_map=buk_to_oracle_map).get_payroll_records(periodo)
    logger.info("Buk: %d registros", len(buk_records))

    # ── 3. Cuadratura ─────────────────────────────────────────────────────────
    logger.info("Ejecutando cuadratura …")
    rows    = reconcile(oracle_records, buk_records, haber_descriptions=all_descriptions)
    n_diffs = sum(1 for r in rows if r.tiene_diferencia)
    logger.info("Total filas: %d  |  Con diferencias: %d", len(rows), n_diffs)

    # ── 4. Excel ──────────────────────────────────────────────────────────────
    excel_path = generate_excel(
        rows, periodo, output_dir,
        buk_to_oracle=buk_to_oracle_map,
        haber_descriptions=all_descriptions,
    )
    logger.info("Excel generado: %s", excel_path)

    # ── 5. Correo ─────────────────────────────────────────────────────────────
    if args.no_email:
        logger.info("--no-email activo — correo omitido")
    elif recipients:
        logger.info("Enviando reporte a: %s", ", ".join(recipients))
        send_cuadratura(recipients, periodo, excel_path, n_diffs, len(rows))
    else:
        logger.info("Sin destinatarios de correo — agrega --emails para enviar")

    logger.info("Proceso finalizado.")


if __name__ == "__main__":
    main()
