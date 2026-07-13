"""Runner mínimo de migrations SQL versionadas (sem Alembic — evita mais uma
dependência pra um schema simples, sem ORM). Aplica cada .sql desta pasta em
ordem alfabética, uma vez só, registrando o nome do arquivo em
schema_migrations.

Uso:
    cd backend && python3 -m migrations.run_migrations
Lê DATABASE_URL do ambiente (ou de backend/.env via python-dotenv).
"""
import asyncio
import os
from pathlib import Path

import asyncpg
from dotenv import load_dotenv

MIGRATIONS_DIR = Path(__file__).parent
ROOT_DIR = MIGRATIONS_DIR.parent
load_dotenv(ROOT_DIR / ".env")

DATABASE_URL = os.environ["DATABASE_URL"]


async def run():
    conn = await asyncpg.connect(DATABASE_URL)
    try:
        await conn.execute(
            "CREATE TABLE IF NOT EXISTS schema_migrations "
            "(filename TEXT PRIMARY KEY, applied_at TIMESTAMPTZ NOT NULL DEFAULT now())"
        )
        applied = {r["filename"] for r in await conn.fetch("SELECT filename FROM schema_migrations")}

        pending = sorted(
            p for p in MIGRATIONS_DIR.glob("*.sql") if p.name not in applied
        )
        if not pending:
            print("Nada a aplicar — schema já está atualizado.")
            return

        for path in pending:
            sql = path.read_text()
            print(f"Aplicando {path.name}...")
            async with conn.transaction():
                await conn.execute(sql)
                await conn.execute(
                    "INSERT INTO schema_migrations (filename) VALUES ($1)", path.name
                )
            print(f"  OK")
    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(run())
