from contextlib import contextmanager
from typing import Generator

import oracledb

from src.config.settings import settings

_pool: oracledb.ConnectionPool | None = None


def init_oracle_client() -> None:
    """Inicializa el modo thick de Oracle (debe llamarse una sola vez al arrancar)."""
    oracledb.init_oracle_client(lib_dir=settings.oracle_client_lib_dir)


def _get_pool() -> oracledb.ConnectionPool:
    global _pool
    if _pool is None:
        _pool = oracledb.create_pool(
            user=settings.db_user,
            password=settings.db_password,
            dsn=settings.db_dsn,
            min=2,
            max=10,
            increment=1,
        )
    return _pool


@contextmanager
def get_connection() -> Generator[oracledb.Connection, None, None]:
    """Context manager que entrega una conexión del pool y la devuelve al terminar."""
    pool = _get_pool()
    conn = pool.acquire()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        pool.release(conn)


def close_pool() -> None:
    """Cierra el pool de conexiones al apagar la aplicación."""
    global _pool
    if _pool is not None:
        _pool.close()
        _pool = None
