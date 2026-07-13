import os
import time
import secrets
import pytest
import requests
import psycopg2
import psycopg2.extras

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "http://localhost:8001").rstrip("/")
DATABASE_URL = os.environ.get("DATABASE_URL", "postgresql://primeencontros:devlocal@localhost:5432/primeencontros")


@pytest.fixture(scope="session")
def base_url():
    return BASE_URL


class _PgCollection:
    """Shim compatível com o subset da API do pymongo (insert_one/find_one/
    delete_one/delete_many/update_one com $set) usado pelos testes — evita
    reescrever cada chamada individualmente em test_oasis_rio.py/test_iter4.py.
    Só entende filtros de igualdade simples e {"$regex": "..."} (via operador
    `~` do Postgres), que é tudo que os testes usam."""

    def __init__(self, conn, table: str):
        self._conn = conn
        self._table = table

    def _where(self, filt: dict):
        if not filt:
            return "TRUE", []
        clauses, params = [], []
        for k, v in filt.items():
            if isinstance(v, dict) and "$regex" in v:
                clauses.append(f"{k} ~ %s")
                params.append(v["$regex"])
            else:
                clauses.append(f"{k} = %s")
                params.append(v)
        return " AND ".join(clauses), params

    def insert_one(self, doc: dict):
        cols = list(doc.keys())
        with self._conn.cursor() as cur:
            cur.execute(
                f"INSERT INTO {self._table} ({', '.join(cols)}) VALUES ({', '.join(['%s'] * len(cols))})",
                [doc[c] for c in cols],
            )

    def find_one(self, filt: dict, projection: dict = None):
        where, params = self._where(filt)
        with self._conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(f"SELECT * FROM {self._table} WHERE {where} LIMIT 1", params)
            row = cur.fetchone()
            return dict(row) if row else None

    def delete_one(self, filt: dict):
        where, params = self._where(filt)
        with self._conn.cursor() as cur:
            cur.execute(f"DELETE FROM {self._table} WHERE {where}", params)

    def delete_many(self, filt: dict):
        self.delete_one(filt)

    def update_one(self, filt: dict, update: dict):
        where, params = self._where(filt)
        sets = update.get("$set", {})
        set_clause = ", ".join(f"{k} = %s" for k in sets)
        with self._conn.cursor() as cur:
            cur.execute(
                f"UPDATE {self._table} SET {set_clause} WHERE {where}",
                list(sets.values()) + params,
            )


class _PgDB:
    def __init__(self, conn):
        self._conn = conn

    def __getattr__(self, table: str) -> _PgCollection:
        return _PgCollection(self._conn, table)


@pytest.fixture(scope="session")
def pg_conn():
    conn = psycopg2.connect(DATABASE_URL)
    conn.autocommit = True
    yield conn
    conn.close()


@pytest.fixture(scope="session")
def mongo_db(pg_conn):
    """Nome mantido por compatibilidade com os testes existentes — o backend
    é Postgres desde 2026-07-12 (ver .ai/context/ARCHITECTURE.md), isso aqui
    é só o shim acima."""
    return _PgDB(pg_conn)


@pytest.fixture(scope="session")
def mongo(pg_conn):
    """Idem — test_iter4.py usa esse nome pro mesmo shim."""
    return _PgDB(pg_conn)


@pytest.fixture(scope="session")
def api_client():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    return s


@pytest.fixture(scope="session")
def test_user(pg_conn):
    """Insere um usuário + sessão de teste direto no Postgres."""
    user_id = f"user_qa_{secrets.token_hex(5)}"
    token = f"test_token_{int(time.time()*1000)}_{secrets.token_hex(4)}"
    email = f"qa+{int(time.time()*1000)}@oasisrio.test"
    with pg_conn.cursor() as cur:
        cur.execute(
            "INSERT INTO users (user_id, email, name, picture) VALUES (%s,%s,%s,%s)",
            (user_id, email, "QA Tester", "https://i.pravatar.cc/150"),
        )
        cur.execute(
            "INSERT INTO user_sessions (session_token, user_id, expires_at) "
            "VALUES (%s,%s, now() + interval '1 day')",
            (token, user_id),
        )
    yield {"user_id": user_id, "email": email, "token": token}
    # Teardown — ordem respeita as FKs (payment_transactions/reviews antes de bookings)
    with pg_conn.cursor() as cur:
        cur.execute("DELETE FROM payment_transactions WHERE user_id = %s", (user_id,))
        cur.execute("DELETE FROM reviews WHERE user_id = %s", (user_id,))
        cur.execute("DELETE FROM bookings WHERE user_id = %s", (user_id,))
        cur.execute("DELETE FROM user_sessions WHERE user_id = %s", (user_id,))
        cur.execute("DELETE FROM users WHERE user_id = %s", (user_id,))


@pytest.fixture(scope="session")
def auth_client(api_client, test_user):
    api_client.headers.update({"Authorization": f"Bearer {test_user['token']}"})
    return api_client
