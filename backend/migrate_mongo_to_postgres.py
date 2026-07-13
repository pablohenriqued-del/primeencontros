"""ETL one-shot: migra os dados do MongoDB (produção antiga) pro Postgres novo.

Rodar UMA VEZ, depois que as migrations SQL (migrations/0001_initial_schema.sql)
já tiverem sido aplicadas no Postgres de destino. Não é idempotente pra
massagistas/bookings/etc — rodar duas vezes duplica dados (roda tudo dentro
de uma transação só; se algo falhar no meio, nada fica salvo).

Tolerante a documentos reais divergentes do schema atual do server.py — ver
achado do inventário em .ai/context/ARCHITECTURE.md: o script
cleanup_for_production.py insere uma massagista de teste ("Lara") com campos
antigos (phone_ddd/phone_number, age, gender, atendimento_domicilio) e sem
bairro_slug/hourly_rate/experience_years/verification. Este script usa
sempre .get(...) com default, nunca acesso direto por chave.

`user_sessions` NÃO é migrada de propósito — são tokens de login efêmeros
(expiram em 7 dias); depois do corte, todo mundo simplesmente loga de novo.

Dependências (não estão no requirements.txt principal — só usadas aqui):
    pip install pymongo asyncpg python-dotenv

Uso:
    cd backend
    MONGO_URL=... DB_NAME=... DATABASE_URL=... python3 migrate_mongo_to_postgres.py
"""
import asyncio
import os
import re
import unicodedata
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import asyncpg
from dotenv import load_dotenv
from pymongo import MongoClient

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / ".env")

MONGO_URL = os.environ["MONGO_URL"]
DB_NAME = os.environ["DB_NAME"]
DATABASE_URL = os.environ["DATABASE_URL"]

# Mesma lista de bairros do server.py — usada só pra derivar bairro_slug
# quando o documento não tiver esse campo (drift conhecido).
BAIRRO_SLUGS = {
    "ipanema", "leblon", "copacabana", "botafogo", "flamengo", "laranjeiras",
    "jardim-botanico", "lagoa", "urca", "tijuca", "barra-da-tijuca", "recreio",
}


def _slugify(name: str) -> str:
    normalized = unicodedata.normalize("NFKD", name or "").encode("ascii", "ignore").decode()
    slug = re.sub(r"[^a-z0-9]+", "-", normalized.lower()).strip("-")
    return slug


def _derive_bairro_slug(doc: Dict[str, Any]) -> str:
    slug = doc.get("bairro_slug")
    if slug:
        return slug
    candidate = _slugify(doc.get("bairro", ""))
    return candidate if candidate in BAIRRO_SLUGS else (candidate or "ipanema")


def _parse_dt(value: Any) -> Optional[datetime]:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    if isinstance(value, str):
        dt = datetime.fromisoformat(value)
        return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    return None


def _parse_date_str(value: Any):
    if value is None:
        return None
    if isinstance(value, str):
        return datetime.strptime(value, "%Y-%m-%d").date()
    return value


def _parse_time_str(value: Any):
    if value is None:
        return None
    if isinstance(value, str):
        return datetime.strptime(value[:5], "%H:%M").time()
    return value


async def migrate():
    mongo = MongoClient(MONGO_URL)
    src = mongo[DB_NAME]
    pool = await asyncpg.create_pool(DATABASE_URL, min_size=1, max_size=2)

    now = datetime.now(timezone.utc)
    stats: Dict[str, int] = {}

    async with pool.acquire() as conn:
        async with conn.transaction():
            # --- users ---
            users = list(src.users.find({}))
            for u in users:
                await conn.execute(
                    """
                    INSERT INTO users (user_id, email, name, picture, is_admin, created_at)
                    VALUES ($1,$2,$3,$4,$5,$6)
                    ON CONFLICT (user_id) DO NOTHING
                    """,
                    u["user_id"], u["email"], u.get("name", ""), u.get("picture", ""),
                    bool(u.get("is_admin", False)), _parse_dt(u.get("created_at")) or now,
                )
            stats["users"] = len(users)

            # --- massagistas (tolerante a drift — ver docstring) ---
            massagistas = list(src.massagistas.find({}))
            massagista_columns = [
                "id", "owner_user_id", "name", "bairro", "bairro_slug", "lat", "lng", "rating", "reviews", "bio",
                "specialties", "hourly_rate", "price_60", "price_90", "price_120", "main_image", "gallery",
                "video_url", "video_thumb", "experience_years", "languages", "ddd", "phone", "verified",
                "verification_status", "verification_id_check", "verification_photo_check",
                "verification_address_check", "verification_verified_at", "verification_verified_by",
                "verification_notes", "created_at",
            ]
            massagista_placeholders = ",".join(f"${i}" for i in range(1, len(massagista_columns) + 1))
            massagista_sql = (
                f"INSERT INTO massagistas ({', '.join(massagista_columns)}) "
                f"VALUES ({massagista_placeholders}) ON CONFLICT (id) DO NOTHING"
            )
            for m in massagistas:
                verification = m.get("verification") or {}
                price_60 = float(m.get("price_60") or 0)
                params = [
                    m["id"], m.get("owner_user_id"), m.get("name", ""), m.get("bairro", ""),
                    _derive_bairro_slug(m), float(m.get("lat") or 0), float(m.get("lng") or 0),
                    float(m.get("rating") or 0), int(m.get("reviews") or 0), m.get("bio", ""),
                    list(m.get("specialties") or []), float(m.get("hourly_rate") or price_60),
                    price_60, float(m.get("price_90") or round(price_60 * 1.4, 2)),
                    float(m.get("price_120") or round(price_60 * 1.8, 2)),
                    m.get("main_image", ""), list(m.get("gallery") or []),
                    m.get("video_url", ""), m.get("video_thumb", ""),
                    int(m.get("experience_years") or 0), list(m.get("languages") or []),
                    m.get("ddd") or m.get("phone_ddd", ""), m.get("phone") or m.get("phone_number", ""),
                    bool(m.get("verified", False)),
                    verification.get("status", "pending"),
                    bool(verification.get("id_check", False)),
                    bool(verification.get("photo_check", False)),
                    bool(verification.get("address_check", False)),
                    _parse_dt(verification.get("verified_at")),
                    verification.get("verified_by"),
                    verification.get("notes"),
                    _parse_dt(m.get("created_at")) or now,
                ]
                assert len(params) == len(massagista_columns), (
                    f"{len(params)} params vs {len(massagista_columns)} columns"
                )
                await conn.execute(massagista_sql, *params)
            stats["massagistas"] = len(massagistas)

            # --- bookings ---
            bookings = list(src.bookings.find({}))
            for b in bookings:
                await conn.execute(
                    """
                    INSERT INTO bookings (
                        id, user_id, user_email, massagista_id, massagista_name, massagista_image, bairro,
                        date, time, duration, location_type, address, notes, amount, currency, status,
                        payment_session_id, payment_method, manual_confirmed_by, manual_confirmed_at, created_at
                    ) VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14,$15,$16,$17,$18,$19,$20,$21)
                    ON CONFLICT (id) DO NOTHING
                    """,
                    b["id"], b["user_id"], b.get("user_email", ""), b["massagista_id"],
                    b.get("massagista_name", ""), b.get("massagista_image", ""), b.get("bairro", ""),
                    _parse_date_str(b.get("date")), _parse_time_str(b.get("time")),
                    int(b.get("duration") or 60), b.get("location_type", "studio"), b.get("address"),
                    b.get("notes"), float(b.get("amount") or 0), b.get("currency", "brl"),
                    b.get("status", "pending_payment"), None,  # payment_session_id via segunda passada, ver abaixo
                    b.get("payment_method"), b.get("manual_confirmed_by"),
                    _parse_dt(b.get("manual_confirmed_at")), _parse_dt(b.get("created_at")) or now,
                )
            stats["bookings"] = len(bookings)

            # --- payment_transactions (depois de bookings, antes de religar payment_session_id) ---
            transactions = list(src.payment_transactions.find({}))
            for t in transactions:
                await conn.execute(
                    """
                    INSERT INTO payment_transactions (
                        session_id, booking_id, user_id, user_email, amount, currency, status,
                        payment_status, created_at, updated_at
                    ) VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10)
                    ON CONFLICT (session_id) DO NOTHING
                    """,
                    t["session_id"], t["booking_id"], t["user_id"], t.get("user_email", ""),
                    float(t.get("amount") or 0), t.get("currency", "brl"), t.get("status", "initiated"),
                    t.get("payment_status", "pending"), _parse_dt(t.get("created_at")) or now,
                    _parse_dt(t.get("updated_at")) or now,
                )
            stats["payment_transactions"] = len(transactions)

            # Religar bookings.payment_session_id agora que payment_transactions existe
            for b in bookings:
                if b.get("payment_session_id"):
                    await conn.execute(
                        "UPDATE bookings SET payment_session_id = $1 WHERE id = $2",
                        b["payment_session_id"], b["id"],
                    )

            # --- reviews ---
            reviews = list(src.reviews.find({}))
            for r in reviews:
                await conn.execute(
                    """
                    INSERT INTO reviews (id, booking_id, massagista_id, user_id, user_name, user_picture,
                                          rating, comment, created_at)
                    VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9)
                    ON CONFLICT (id) DO NOTHING
                    """,
                    r["id"], r["booking_id"], r["massagista_id"], r["user_id"], r.get("user_name", ""),
                    r.get("user_picture", ""), int(r.get("rating") or 5), r.get("comment"),
                    _parse_dt(r.get("created_at")) or now,
                )
            stats["reviews"] = len(reviews)

            # --- whatsapp_clicks ---
            clicks = list(src.whatsapp_clicks.find({}))
            for c in clicks:
                await conn.execute(
                    """
                    INSERT INTO whatsapp_clicks (id, massagista_id, massagista_name, user_id, user_email,
                                                  user_name, source, user_agent, created_at)
                    VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9)
                    ON CONFLICT (id) DO NOTHING
                    """,
                    c["id"], c["massagista_id"], c.get("massagista_name", ""), c.get("user_id"),
                    c.get("user_email"), c.get("user_name"), c.get("source", "detail"),
                    c.get("user_agent", ""), _parse_dt(c.get("created_at")) or now,
                )
            stats["whatsapp_clicks"] = len(clicks)

            # --- profile_views ---
            views = list(src.profile_views.find({}))
            for v in views:
                await conn.execute(
                    """
                    INSERT INTO profile_views (id, massagista_id, user_id, user_agent, created_at)
                    VALUES ($1,$2,$3,$4,$5)
                    ON CONFLICT (id) DO NOTHING
                    """,
                    v["id"], v["massagista_id"], v.get("user_id"), v.get("user_agent", ""),
                    _parse_dt(v.get("created_at")) or now,
                )
            stats["profile_views"] = len(views)

            # --- files ---
            files = list(src.files.find({}))
            for f in files:
                await conn.execute(
                    """
                    INSERT INTO files (id, massagista_id, kind, storage_path, content_type, size,
                                        original_filename, uploaded_by, is_deleted, deleted_by, deleted_at,
                                        created_at)
                    VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12)
                    ON CONFLICT (id) DO NOTHING
                    """,
                    f["id"], f["massagista_id"], f.get("kind", "image"), f["storage_path"],
                    f.get("content_type", "application/octet-stream"), int(f.get("size") or 0),
                    f.get("original_filename"), f.get("uploaded_by", ""), bool(f.get("is_deleted", False)),
                    f.get("deleted_by"), _parse_dt(f.get("deleted_at")), _parse_dt(f.get("created_at")) or now,
                )
            stats["files"] = len(files)

    await pool.close()
    mongo.close()

    print("Migração concluída:")
    for k, v in stats.items():
        print(f"  {k}: {v}")
    print("\nuser_sessions NÃO foi migrada (tokens efêmeros) — usuários vão precisar logar de novo.")


if __name__ == "__main__":
    asyncio.run(migrate())
