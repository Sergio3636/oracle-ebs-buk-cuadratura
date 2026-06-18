from src.database.connection import close_pool, get_connection, init_oracle_client


def main() -> None:
    init_oracle_client()

    try:
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT 'Conexión OK' FROM dual")
            row = cursor.fetchone()
            print(f"Oracle respondió: {row[0]}")
    finally:
        close_pool()


if __name__ == "__main__":
    main()
