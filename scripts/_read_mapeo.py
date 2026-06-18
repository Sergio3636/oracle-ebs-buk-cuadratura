"""Lee la tabla XXMAPEO_HABER — debería tener el mapeo Oracle cod_haber → Buk."""
import sys
sys.path.insert(0, "/app")
from src.database.connection import get_connection, init_oracle_client

SQL_COLS = """
SELECT column_name, data_type, data_length
FROM all_tab_columns
WHERE table_name = 'XXMAPEO_HABER'
ORDER BY column_id
"""

SQL_ALL = "SELECT * FROM apps.xxmapeo_haber ORDER BY 1"

init_oracle_client()
with get_connection() as conn:
    cur = conn.cursor()

    print("=== COLUMNAS DE XXMAPEO_HABER ===\n")
    cur.execute(SQL_COLS)
    cols = cur.fetchall()
    col_names = [c[0] for c in cols]
    for col, dtype, length in cols:
        print(f"  {str(col):35} {str(dtype):15} {length}")

    print(f"\n=== DATOS DE XXMAPEO_HABER ({len(col_names)} columnas) ===\n")
    cur.execute(SQL_ALL)
    rows = cur.fetchall()
    print("  " + " | ".join(f"{c:25}" for c in col_names))
    print("  " + "-" * (28 * len(col_names)))
    for row in rows:
        print("  " + " | ".join(f"{str(v or ''):25}" for v in row))

print(f"\nTotal filas: {len(rows)}")
