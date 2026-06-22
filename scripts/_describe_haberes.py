"""Diagnóstico: nombres de conceptos Oracle vs Buk para determinar el mapeo."""
import sys, json
sys.path.insert(0, "/app")

from src.config.settings import settings
from src.database.connection import get_connection, init_oracle_client
from src.utils import normalize_rut

PERIODO = "052026"  # Mayo 2026 — todos en estado 'Cargado en RRHH'

# ── 1. Oracle: conceptos distintos con descripción ────────────────────────────
SQL_CONCEPTOS = """
SELECT DISTINCT
    d.cod_haber,
    d.nom_haber
FROM apps.xxgl_carga_remu_detalle d
JOIN apps.xxgl_carga_remu c
  ON c.carga_remuneraciones_id = d.carga_remuneraciones_id
WHERE (d.cod_haber LIKE 'B%' OR d.cod_haber LIKE 'H%')
  AND TO_CHAR(c.periodo, 'MMyyyy') = :periodo
ORDER BY 1
"""

SQL_CONCEPTOS_FALLBACK = """
SELECT DISTINCT d.cod_haber, '' nom_haber
FROM apps.xxgl_carga_remu_detalle d
JOIN apps.xxgl_carga_remu c
  ON c.carga_remuneraciones_id = d.carga_remuneraciones_id
WHERE (d.cod_haber LIKE 'B%' OR d.cod_haber LIKE 'H%')
  AND TO_CHAR(c.periodo, 'MMyyyy') = :periodo
ORDER BY 1
"""

# ── 2. Oracle: algunos RUTs con sus cod_haber (muestra 10 personas) ───────────
SQL_POR_PERSONA = """
SELECT rut, nom_haber, cod_haber, SUM(valor) monto
FROM (
    SELECT normalize_rut(d.rut) rut, d.nom_haber, d.cod_haber, d.valor
    FROM apps.xxgl_carga_remu_detalle d
    JOIN apps.xxgl_carga_remu c
      ON c.carga_remuneraciones_id = d.carga_remuneraciones_id
    WHERE (d.cod_haber LIKE 'B%' OR d.cod_haber LIKE 'H%')
      AND TO_CHAR(c.periodo, 'MMyyyy') = :periodo
)
GROUP BY rut, nom_haber, cod_haber
ORDER BY rut, cod_haber
"""

SQL_POR_PERSONA_SIMPLE = """
SELECT d.rut, d.cod_haber, SUM(d.valor) monto
FROM apps.xxgl_carga_remu_detalle d
JOIN apps.xxgl_carga_remu c
  ON c.carga_remuneraciones_id = d.carga_remuneraciones_id
WHERE (d.cod_haber LIKE 'B%' OR d.cod_haber LIKE 'H%')
  AND TO_CHAR(c.periodo, 'MMyyyy') = :periodo
GROUP BY d.rut, d.cod_haber
ORDER BY d.rut, d.cod_haber
"""

init_oracle_client()
with get_connection() as conn:
    cur = conn.cursor()

    # Intentar con nom_haber primero
    print(f"=== CONCEPTOS ORACLE PERÍODO {PERIODO} ===\n")
    try:
        cur.execute(SQL_CONCEPTOS, periodo=PERIODO)
        rows = cur.fetchall()
        print(f"{'COD_HABER':12} NOM_HABER")
        print("-" * 50)
        for cod, nom in rows:
            print(f"  {str(cod):12} {nom}")
    except Exception as e:
        print(f"(nom_haber no disponible: {e})")
        cur.execute(SQL_CONCEPTOS_FALLBACK, periodo=PERIODO)
        rows = cur.fetchall()
        print(f"{'COD_HABER':12}")
        print("-" * 20)
        for (cod,) in [r[:1] for r in rows]:
            print(f"  {str(cod)}")

    # Muestra por persona
    print(f"\n=== MUESTRA DE PERSONAS CON SUS CÓDIGOS (PERÍODO {PERIODO}) ===\n")
    try:
        cur.execute(SQL_POR_PERSONA, periodo=PERIODO)
        rows = cur.fetchall()
        current_rut = None
        count = 0
        for rut, nom, cod, monto in rows:
            rut_norm = normalize_rut(str(rut))
            if rut_norm != current_rut:
                if count >= 10:
                    break
                count += 1
                current_rut = rut_norm
                print(f"\nRUT {rut_norm}")
            print(f"  {str(cod):12} {str(nom):35} {float(monto):12,.0f}")
    except Exception as e:
        print(f"(nom_haber no disponible: {e})")
        cur.execute(SQL_POR_PERSONA_SIMPLE, periodo=PERIODO)
        rows = cur.fetchall()
        current_rut = None
        count = 0
        for rut, cod, monto in rows:
            rut_norm = normalize_rut(str(rut))
            if rut_norm != current_rut:
                if count >= 10:
                    break
                count += 1
                current_rut = rut_norm
                print(f"\nRUT {rut_norm}")
            print(f"  {str(cod):12} {float(monto):12,.0f}")

print("\n=== BUK: item_codes período actual (3 págs, para comparar) ===\n")
import urllib.request
_TOKEN = settings.buk_api_token
_BASE  = settings.buk_api_url.rstrip("/")
buk_concepts: dict[str, str] = {}
for page in range(1, 4):
    url = f"{_BASE}/api/v1/chile/payroll_detail/month?month=6&year=2026&page={page}"
    req = urllib.request.Request(url, headers={"auth_token": _TOKEN, "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        data = json.loads(resp.read())
    for rec in data["data"]:
        for line in rec.get("lines_settlement", []):
            if line.get("type") == "haber" and line.get("item_code"):
                ic = line["item_code"]
                if ic not in buk_concepts:
                    buk_concepts[ic] = line.get("name", "")

print(f"{'ITEM_CODE':30} NOMBRE")
print("-" * 60)
for ic, name in sorted(buk_concepts.items()):
    print(f"  {ic:30} {name}")
