import pytest

from src.database.connection import get_connection, init_oracle_client


@pytest.fixture(scope="session", autouse=True)
def oracle_client():
    init_oracle_client()


def test_oracle_connection_alive():
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT 1 FROM dual")
        result = cursor.fetchone()
    assert result[0] == 1


def test_oracle_query_returns_data():
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT SYSDATE FROM dual")
        row = cursor.fetchone()
    assert row is not None
