"""Utilitário de linha de comando pra ver e gerenciar usuários (`users`).

Não existe endpoint HTTP pra isso de propósito — promover/remover admin e
apagar usuário são operações raras e sensíveis, feitas direto no banco (ver
CONTRACTS.md #6). Este script só facilita rodar isso sem escrever SQL na mão.

Uso (dentro do container ou com DATABASE_URL apontando pro Postgres certo):
    cd backend
    python3 manage_users.py list
    python3 manage_users.py make-admin <email>
    python3 manage_users.py delete <email>

Na VPS (Portainer/Docker), rodar dentro do container do backend:
    docker exec -it primeencontros_backend-app-prod python3 manage_users.py list
"""
import asyncio
import sys
from pathlib import Path

import asyncpg
from dotenv import load_dotenv
import os

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / ".env")
DATABASE_URL = os.environ["DATABASE_URL"]


async def list_users() -> None:
    conn = await asyncpg.connect(DATABASE_URL)
    try:
        rows = await conn.fetch(
            "SELECT user_id, email, name, is_admin, created_at FROM users ORDER BY created_at"
        )
        if not rows:
            print("Nenhum usuário cadastrado ainda.")
            return
        print(f"{'ADMIN':<6} {'EMAIL':<40} {'NOME':<25} CRIADO EM")
        for r in rows:
            flag = "sim" if r["is_admin"] else "não"
            print(f"{flag:<6} {r['email']:<40} {r['name']:<25} {r['created_at']}")
    finally:
        await conn.close()


async def make_admin(email: str) -> None:
    conn = await asyncpg.connect(DATABASE_URL)
    try:
        result = await conn.execute(
            "UPDATE users SET is_admin = true WHERE email = $1", email
        )
        if result == "UPDATE 0":
            print(f"Nenhum usuário com e-mail {email!r} encontrado — a pessoa "
                  f"ainda precisa logar pelo menos uma vez, ou adicione o "
                  f"e-mail em ADMIN_EMAILS no backend/.env.")
        else:
            print(f"{email} agora é admin.")
    finally:
        await conn.close()


async def delete_user(email: str) -> None:
    conn = await asyncpg.connect(DATABASE_URL)
    try:
        try:
            result = await conn.execute("DELETE FROM users WHERE email = $1", email)
        except asyncpg.ForeignKeyViolationError:
            print(f"Não foi possível apagar {email}: este usuário tem reservas, "
                  f"avaliações ou pagamentos registrados (mantidos de propósito "
                  f"como histórico — ver CONTRACTS.md #11).")
            return
        if result == "DELETE 0":
            print(f"Nenhum usuário com e-mail {email!r} encontrado.")
        else:
            print(f"Usuário {email} apagado (sessões associadas também "
                  f"caíram junto; massagista dona da conta, se houver, fica "
                  f"sem dono mas não é apagada).")
    finally:
        await conn.close()


def main() -> None:
    if len(sys.argv) < 2 or sys.argv[1] not in {"list", "make-admin", "delete"}:
        print(__doc__)
        sys.exit(1)

    cmd = sys.argv[1]
    if cmd == "list":
        asyncio.run(list_users())
    elif cmd == "make-admin":
        if len(sys.argv) != 3:
            print("Uso: python3 manage_users.py make-admin <email>")
            sys.exit(1)
        asyncio.run(make_admin(sys.argv[2]))
    elif cmd == "delete":
        if len(sys.argv) != 3:
            print("Uso: python3 manage_users.py delete <email>")
            sys.exit(1)
        asyncio.run(delete_user(sys.argv[2]))


if __name__ == "__main__":
    main()
