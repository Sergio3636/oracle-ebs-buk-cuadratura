"""Lee XX_HABERES_PAYROLL vía FND_FLEX_VALUES_TL."""
import sys
sys.path.insert(0, "/app")
from src.database.connection import get_connection, init_oracle_client

init_oracle_client()
with get_connection() as conn:
    cur = conn.cursor()

    # Columnas de FND_FLEX_VALUES_TL
    print("=== COLUMNAS FND_FLEX_VALUES_TL ===\n")
    cur.execute("""
        SELECT column_name FROM all_tab_columns
        WHERE table_name = 'FND_FLEX_VALUES_TL'
        ORDER BY column_id
    """)
    for (c,) in cur.fetchall():
        print(f"  {c}")

    # Join FND_FLEX_VALUES con TL para obtener el nombre
    print("\n=== XX_HABERES_PAYROLL (ID=1010039) ===\n")
    cur.execute("""
        SELECT fv.flex_value, tl.description
        FROM apps.fnd_flex_values fv
        JOIN apps.fnd_flex_values_tl tl
          ON tl.flex_value_id = fv.flex_value_id
         AND tl.language = USERENV('LANG')
        WHERE fv.flex_value_set_id = 1010039
        ORDER BY fv.flex_value
    """)
    rows = cur.fetchall()
    print(f"{'COD_HABER':15} NOMBRE")
    print("-" * 60)
    for val, desc in rows:
        print(f"  {str(val):15} {desc}")
    print(f"\nTotal: {len(rows)} haberes en el catálogo")

    # Verificar los de 052026
    print("\n=== CÓDIGOS 052026 ===\n")
    codigos = ['BOGEMA','BOLMVA','BONADI','BONEME','BONOBR','BONTUR','BONCOM','BONOMA',
               'HEX051','HEX052','HEX053','HEX054','HEX055',
               'HEX056','HEX057','HEX058','HEX059','HEX100','HEX102','HEX103']
    for cod in codigos:
        cur.execute("""
            SELECT tl.description
            FROM apps.fnd_flex_values fv
            JOIN apps.fnd_flex_values_tl tl ON tl.flex_value_id = fv.flex_value_id
              AND tl.language = USERENV('LANG')
            WHERE fv.flex_value_set_id = 1010039 AND fv.flex_value = :v
        """, v=cod)
        row = cur.fetchone()
        estado = f"→ {row[0]}" if row else "❌ no encontrado"
        print(f"  {cod:15} {estado}")
