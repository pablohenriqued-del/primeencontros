"""
Oásis Rio – Backend API
Massage therapist marketplace for Rio de Janeiro.
"""
import os
import io
import uuid
import math
import logging
from datetime import datetime, timezone, timedelta, date, time as dtime
from decimal import Decimal
from pathlib import Path
from typing import List, Optional, Dict, Any

import httpx
import stripe
import asyncpg
from fastapi import FastAPI, APIRouter, HTTPException, Request, Response, Cookie, Header, Query, UploadFile, File, Body
from fastapi.responses import JSONResponse, StreamingResponse, HTMLResponse
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from promo_card import generate_promo_card

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / ".env")

# ---------------------------------------------------------------------------
# Postgres (migrado do MongoDB em 2026-07-12 — ver .ai/context/ARCHITECTURE.md)
# ---------------------------------------------------------------------------
DATABASE_URL = os.environ["DATABASE_URL"]
pool: Optional[asyncpg.Pool] = None


def _row(record: Optional[asyncpg.Record]) -> Optional[Dict[str, Any]]:
    """Converte um Record do asyncpg num dict JSON-seguro (mesmo shape que os
    documentos Mongo de antes: Decimal->float, date/time/datetime->string)."""
    if record is None:
        return None
    d = dict(record)
    for k, v in d.items():
        if isinstance(v, Decimal):
            d[k] = float(v)
        elif isinstance(v, datetime):
            d[k] = v.isoformat()
        elif isinstance(v, dtime):
            d[k] = v.strftime("%H:%M")
        elif isinstance(v, date):
            d[k] = v.isoformat()
    return d


def _rows(records) -> List[Dict[str, Any]]:
    return [_row(r) for r in records]


def _parse_date(s: str) -> date:
    return datetime.strptime(s, "%Y-%m-%d").date()


def _parse_time(s: str) -> dtime:
    return datetime.strptime(s, "%H:%M").time()


def _massagista_out(d: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """Reconstrói o objeto aninhado 'verification' a partir das colunas
    achatadas — contrato de API idêntico ao dos documentos Mongo de antes."""
    if d is None:
        return None
    d["verification"] = {
        "status": d.pop("verification_status"),
        "id_check": d.pop("verification_id_check"),
        "photo_check": d.pop("verification_photo_check"),
        "address_check": d.pop("verification_address_check"),
        "verified_at": d.pop("verification_verified_at"),
        "verified_by": d.pop("verification_verified_by"),
        "notes": d.pop("verification_notes"),
    }
    d.pop("is_deleted", None)
    d.pop("deleted_by", None)
    d.pop("deleted_at", None)
    return d


STRIPE_API_KEY = os.environ.get("STRIPE_API_KEY", "")
STRIPE_WEBHOOK_SECRET = os.environ.get("STRIPE_WEBHOOK_SECRET", "")
stripe.api_key = STRIPE_API_KEY
EMERGENT_AUTH_SESSION_URL = "https://demobackend.emergentagent.com/auth/v1/env/oauth/session-data"
ADMIN_EMAILS = {e.strip().lower() for e in os.environ.get("ADMIN_EMAILS", "").split(",") if e.strip()}

# ---------------------------------------------------------------------------
# Object storage (disco local — volume Docker, ver CONTRACTS.md #8)
# ---------------------------------------------------------------------------
APP_NAME = "prime-encontros"
STORAGE_DIR = Path(os.environ.get("STORAGE_DIR", "/data/uploads"))
ALLOWED_IMAGE = {"image/jpeg", "image/jpg", "image/png", "image/webp"}
ALLOWED_VIDEO = {"video/mp4", "video/quicktime", "video/webm"}
# Documento de identidade aceita PDF além de imagem — cobre CNH Digital (o app
# oficial exporta PDF) e digitalizações frente+verso num arquivo só (ver
# migrations/0004). Selfie continua só imagem.
ALLOWED_DOCUMENT = ALLOWED_IMAGE | {"application/pdf"}
EXT_FOR = {
    "image/jpeg": "jpg", "image/jpg": "jpg", "image/png": "png", "image/webp": "webp",
    "video/mp4": "mp4", "video/quicktime": "mov", "video/webm": "webm",
    "application/pdf": "pdf",
}


def _storage_full_path(path: str) -> Path:
    """Resolve path dentro de STORAGE_DIR, rejeitando qualquer tentativa de
    escapar o diretório (defesa em profundidade — na prática `path` sempre
    vem de storage_path gerado com uuid4, nunca de input direto do usuário)."""
    base = STORAGE_DIR.resolve()
    full = (base / path).resolve()
    if full != base and base not in full.parents:
        raise HTTPException(400, "Caminho inválido")
    return full


def put_object(path: str, data: bytes, content_type: str) -> Dict[str, Any]:
    full = _storage_full_path(path)
    full.parent.mkdir(parents=True, exist_ok=True)
    full.write_bytes(data)
    return {"path": path, "size": len(data)}


def get_object(path: str) -> tuple:
    full = _storage_full_path(path)
    if not full.is_file():
        raise HTTPException(404, "Arquivo não encontrado")
    return full.read_bytes(), "application/octet-stream"

# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------
app = FastAPI(title="Prime Encontros API")
api = APIRouter(prefix="/api")

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger("oasis")


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------
class Bairro(BaseModel):
    slug: str
    name: str
    lat: float
    lng: float


class Massagista(BaseModel):
    id: str
    name: str
    bairro: str
    bairro_slug: str
    lat: float
    lng: float
    rating: float
    reviews: int
    bio: str
    specialties: List[str]
    hourly_rate: float  # BRL
    price_60: float
    price_90: float
    price_120: float
    main_image: str
    gallery: List[str]
    video_url: str
    video_thumb: str
    experience_years: int
    languages: List[str]


class BookingCreate(BaseModel):
    massagista_id: str
    date: str  # ISO date "YYYY-MM-DD"
    time: str  # "HH:MM"
    duration: int  # 60 | 90 | 120
    location_type: str  # "studio" | "home"
    address: Optional[str] = None
    notes: Optional[str] = None


class Booking(BaseModel):
    id: str
    user_id: str
    user_email: str
    massagista_id: str
    massagista_name: str
    massagista_image: str
    bairro: str
    date: str
    time: str
    duration: int
    location_type: str
    address: Optional[str] = None
    notes: Optional[str] = None
    amount: float
    currency: str = "brl"
    status: str = "pending_payment"  # pending_payment | confirmed | cancelled
    payment_session_id: Optional[str] = None
    created_at: str


class CheckoutCreateReq(BaseModel):
    booking_id: str
    origin_url: str


class VerificationAction(BaseModel):
    id_check: bool = True
    photo_check: bool = True
    address_check: bool = True
    notes: Optional[str] = None


class ReviewCreate(BaseModel):
    rating: int = Field(ge=1, le=5)
    comment: Optional[str] = Field(default=None, max_length=600)


class ProfileCreate(BaseModel):
    name: str = Field(min_length=2, max_length=80)
    bairro_slug: str
    bio: str = Field(min_length=10, max_length=600)
    specialties: List[str] = Field(min_length=1, max_length=8)
    price_60: float = Field(gt=0)
    price_90: Optional[float] = None
    price_120: Optional[float] = None
    experience_years: int = Field(ge=0, le=60)
    languages: List[str] = Field(min_length=1)
    ddd: Optional[str] = None
    phone: Optional[str] = None


class ProfileUpdate(BaseModel):
    name: Optional[str] = None
    bio: Optional[str] = None
    specialties: Optional[List[str]] = None
    price_60: Optional[float] = None
    price_90: Optional[float] = None
    price_120: Optional[float] = None
    bairro_slug: Optional[str] = None
    experience_years: Optional[int] = None
    languages: Optional[List[str]] = None
    ddd: Optional[str] = None
    phone: Optional[str] = None


class WhatsAppClick(BaseModel):
    massagista_id: str
    source: Optional[str] = "detail"  # detail | modal | map


class ManualBookingCreate(BaseModel):
    massagista_id: str
    user_email: str
    date: str  # YYYY-MM-DD
    time: str  # HH:MM
    duration: int  # 60 | 90 | 120
    payment_method: str = "manual"  # whatsapp | pix | cash | manual
    notes: Optional[str] = None


# ---------------------------------------------------------------------------
# Seed data
# ---------------------------------------------------------------------------
BAIRROS: List[Bairro] = [
    Bairro(slug="ipanema", name="Ipanema", lat=-22.9839, lng=-43.2045),
    Bairro(slug="leblon", name="Leblon", lat=-22.9847, lng=-43.2233),
    Bairro(slug="copacabana", name="Copacabana", lat=-22.9711, lng=-43.1822),
    Bairro(slug="botafogo", name="Botafogo", lat=-22.9483, lng=-43.1815),
    Bairro(slug="flamengo", name="Flamengo", lat=-22.9329, lng=-43.1788),
    Bairro(slug="laranjeiras", name="Laranjeiras", lat=-22.9343, lng=-43.1880),
    Bairro(slug="jardim-botanico", name="Jardim Botânico", lat=-22.9685, lng=-43.2244),
    Bairro(slug="lagoa", name="Lagoa", lat=-22.9719, lng=-43.2058),
    Bairro(slug="urca", name="Urca", lat=-22.9483, lng=-43.1654),
    Bairro(slug="tijuca", name="Tijuca", lat=-22.9249, lng=-43.2378),
    Bairro(slug="barra-da-tijuca", name="Barra da Tijuca", lat=-23.0058, lng=-43.3197),
    Bairro(slug="recreio", name="Recreio", lat=-23.0244, lng=-43.4641),
]
BAIRRO_MAP = {b.slug: b for b in BAIRROS}

SAMPLE_VIDEO = "https://commondatastorage.googleapis.com/gtv-videos-bucket/sample/BigBuckBunny.mp4"
SPA1 = "https://images.unsplash.com/photo-1741522509438-a120c0bb5e88?crop=entropy&cs=srgb&fm=jpg&ixid=M3w3NDQ2NDN8MHwxfHNlYXJjaHwxfHxzcGElMjBtYXNzYWdlJTIwY2FsbXxlbnwwfHx8fDE3ODEzMTE5NzV8MA&ixlib=rb-4.1.0&q=85"
SPA2 = "https://images.unsplash.com/photo-1639162906614-0603b0ae95fd?crop=entropy&cs=srgb&fm=jpg&ixid=M3w3NDQ2NDN8MHwxfHNlYXJjaHwzfHxzcGElMjBtYXNzYWdlJTIwY2FsbXxlbnwwfHx8fDE3ODEzMTE5NzV8MA&ixlib=rb-4.1.0&q=85"
SPA3 = "https://images.unsplash.com/photo-1544161515-4ab6ce6db874?crop=entropy&cs=srgb&fm=jpg&w=900&q=80"
SPA4 = "https://images.unsplash.com/photo-1600334129128-685c5582fd35?crop=entropy&cs=srgb&fm=jpg&w=900&q=80"

# Female portraits — sourced from randomuser.me (100% reliable, all women).
# Admin can upload higher-quality replacements via the Media Editor.
PORTRAITS = [
    "https://randomuser.me/api/portraits/women/65.jpg",
    "https://randomuser.me/api/portraits/women/44.jpg",
    "https://randomuser.me/api/portraits/women/68.jpg",
    "https://randomuser.me/api/portraits/women/26.jpg",
    "https://randomuser.me/api/portraits/women/79.jpg",
    "https://randomuser.me/api/portraits/women/12.jpg",
    "https://randomuser.me/api/portraits/women/49.jpg",
    "https://randomuser.me/api/portraits/women/33.jpg",
    "https://randomuser.me/api/portraits/women/8.jpg",
    "https://randomuser.me/api/portraits/women/56.jpg",
    "https://randomuser.me/api/portraits/women/21.jpg",
    "https://randomuser.me/api/portraits/women/90.jpg",
]

SEED_PROFILES = [
    ("Camila Souza", "ipanema", 4.9, 213, "Especialista em massagem relaxante e pedras quentes. Atendimento humanizado em estúdio com vista para o mar.",
        ["Relaxante", "Pedras Quentes", "Shiatsu"], 220.0, 8, ["Português", "Inglês"]),
    ("Mariana Costa", "leblon", 4.8, 187, "Terapeuta com formação em terapias orientais. Foco em alívio de tensões e dores musculares crônicas.",
        ["Shiatsu", "Tui Ná", "Reflexologia"], 280.0, 12, ["Português", "Inglês", "Espanhol"]),
    ("Larissa Mendes", "copacabana", 4.7, 156, "Massoterapeuta esportiva com experiência em atletas amadores e profissionais. Recuperação muscular pós-treino.",
        ["Esportiva", "Drenagem", "Liberação Miofascial"], 250.0, 10, ["Português", "Inglês"]),
    ("Beatriz Almeida", "botafogo", 4.9, 298, "Apaixonada por aromaterapia. Sessões que combinam óleos essenciais e técnica suave para relaxamento profundo.",
        ["Aromaterapia", "Relaxante", "Sueca"], 200.0, 6, ["Português", "Francês"]),
    ("Júlia Ribeiro", "flamengo", 4.6, 92, "Quiropraxia e massagem ortopédica. Indicado para quem trabalha horas no computador e sente dores cervicais.",
        ["Quiropraxia", "Ortopédica", "Postura"], 240.0, 9, ["Português"]),
    ("Isabela Martins", "jardim-botanico", 4.9, 341, "Drenagem linfática modeladora e pós-cirúrgico. Ambiente tranquilo no Jardim Botânico.",
        ["Drenagem Linfática", "Modeladora", "Pós-cirúrgico"], 260.0, 11, ["Português", "Inglês"]),
    ("Clara Vieira", "tijuca", 4.5, 78, "Massagem terapêutica com 7 anos de experiência. Atendo na clínica ou no seu endereço com mesa portátil.",
        ["Terapêutica", "Relaxante", "Anti-stress"], 180.0, 7, ["Português"]),
    ("Fernanda Lima", "barra-da-tijuca", 4.8, 220, "Bambuterapia e ventosaterapia. Técnicas integradas para bem-estar profundo e alívio de tensões antigas.",
        ["Bambuterapia", "Ventosaterapia", "Relaxante"], 270.0, 9, ["Português", "Inglês"]),
    ("Letícia Barros", "laranjeiras", 4.7, 134, "Massagem desportiva e liberação de gatilhos. Atendimento direto, focado em resultado.",
        ["Esportiva", "Pontos de Gatilho", "Profunda"], 230.0, 8, ["Português", "Espanhol"]),
    ("Patrícia Nogueira", "lagoa", 4.9, 256, "Reiki e massagem energética. Para quem busca um equilíbrio que vai além do físico.",
        ["Reiki", "Energética", "Relaxante"], 210.0, 13, ["Português", "Inglês"]),
    ("Tatiane Castro", "urca", 4.8, 167, "Estúdio acolhedor na Urca. Massagem sueca e desportiva de alto padrão, ambiente reservado.",
        ["Sueca", "Esportiva", "Profunda"], 290.0, 10, ["Português", "Inglês"]),
    ("Renata Oliveira", "recreio", 4.6, 88, "Massagem relaxante e gestante. Cuidado especial e seguro para futuras mamães.",
        ["Gestante", "Relaxante", "Sueca"], 220.0, 6, ["Português"]),
]


async def seed_massagistas():
    count = await pool.fetchval("SELECT count(*) FROM massagistas")
    if count > 0:
        return
    now = datetime.now(timezone.utc)
    rows = []
    for i, (name, bairro_slug, rating, reviews, bio, specs, base_price, exp, langs) in enumerate(SEED_PROFILES):
        b = BAIRRO_MAP[bairro_slug]
        # small jitter so two massagistas in same bairro have slightly different coords
        jitter_lat = (i % 5) * 0.0008
        jitter_lng = (i % 4) * 0.0008
        portrait = PORTRAITS[i % len(PORTRAITS)]
        gallery = [portrait, SPA1, SPA2, SPA3 if i % 2 == 0 else SPA4]
        verified = i < 8  # first 8 are pre-verified for demo
        rows.append((
            f"m_{uuid.uuid4().hex[:10]}", name, b.name, b.slug, b.lat + jitter_lat, b.lng + jitter_lng,
            rating, reviews, bio, specs, base_price, base_price, round(base_price * 1.4, 2), round(base_price * 1.8, 2),
            portrait, gallery, SAMPLE_VIDEO, SPA1, exp, langs, "21", f"99{(80000000 + i * 137):08d}",
            verified,
            "verified" if verified else "pending", verified, verified, verified,
            now if verified else None, "system_seed" if verified else None,
            now,
        ))
    await pool.executemany(
        """
        INSERT INTO massagistas (
            id, name, bairro, bairro_slug, lat, lng, rating, reviews, bio, specialties,
            hourly_rate, price_60, price_90, price_120, main_image, gallery, video_url, video_thumb,
            experience_years, languages, ddd, phone, verified,
            verification_status, verification_id_check, verification_photo_check, verification_address_check,
            verification_verified_at, verification_verified_by, created_at
        ) VALUES (
            $1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14,$15,$16,$17,$18,$19,$20,$21,$22,$23,$24,$25,$26,$27,$28,$29,$30
        )
        """,
        rows,
    )
    logger.info(f"Seeded {len(rows)} massagistas")


# ---------------------------------------------------------------------------
# Utils
# ---------------------------------------------------------------------------
def haversine_km(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    R = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlng = math.radians(lng2 - lng1)
    a = math.sin(dlat / 2) ** 2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlng / 2) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c


async def get_current_user(
    session_token: Optional[str] = Cookie(default=None),
    authorization: Optional[str] = Header(default=None),
) -> Optional[Dict[str, Any]]:
    token = session_token
    if not token and authorization and authorization.lower().startswith("bearer "):
        token = authorization.split(" ", 1)[1].strip()
    if not token:
        return None
    sess = _row(await pool.fetchrow("SELECT * FROM user_sessions WHERE session_token = $1", token))
    if not sess:
        return None
    expires_at = datetime.fromisoformat(sess["expires_at"])
    if expires_at < datetime.now(timezone.utc):
        return None
    user = _row(await pool.fetchrow("SELECT * FROM users WHERE user_id = $1", sess["user_id"]))
    return user


async def require_user(
    session_token: Optional[str] = Cookie(default=None),
    authorization: Optional[str] = Header(default=None),
) -> Dict[str, Any]:
    user = await get_current_user(session_token=session_token, authorization=authorization)
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return user


# ---------------------------------------------------------------------------
# Public endpoints
# ---------------------------------------------------------------------------
@api.get("/")
async def root():
    return {"app": "Prime Encontros", "status": "ok"}


@api.get("/bairros", response_model=List[Bairro])
async def list_bairros():
    return BAIRROS


@api.get("/massagistas", response_model=List[Dict[str, Any]])
async def list_massagistas(
    bairro: Optional[str] = Query(None),
    lat: Optional[float] = Query(None),
    lng: Optional[float] = Query(None),
    q: Optional[str] = Query(None),
    verified_only: bool = Query(False),
):
    conditions = ["is_deleted = false"]
    params: List[Any] = []
    if bairro:
        params.append(bairro)
        conditions.append(f"bairro_slug = ${len(params)}")
    if verified_only:
        conditions.append("verified = true")
    if q:
        params.append(f"%{q}%")
        idx = len(params)
        conditions.append(
            f"(name ILIKE ${idx} OR bairro ILIKE ${idx} "
            f"OR EXISTS (SELECT 1 FROM unnest(specialties) s WHERE s ILIKE ${idx}))"
        )
    where = " AND ".join(conditions)
    rows = await pool.fetch(f"SELECT * FROM massagistas WHERE {where} LIMIT 200", *params)
    docs = [_massagista_out(_row(r)) for r in rows]
    if lat is not None and lng is not None:
        for d in docs:
            d["distance_km"] = round(haversine_km(lat, lng, d["lat"], d["lng"]), 2)
        docs.sort(key=lambda x: x["distance_km"])
    else:
        # Sort: verified first, then rating desc
        docs.sort(key=lambda x: (not x.get("verified", False), -x.get("rating", 0)))
    return docs


@api.get("/massagistas/{mid}")
async def get_massagista(mid: str):
    doc = _massagista_out(_row(await pool.fetchrow(
        "SELECT * FROM massagistas WHERE id = $1 AND is_deleted = false", mid
    )))
    if not doc:
        raise HTTPException(404, "Massagista não encontrada")
    return doc


# ---------------------------------------------------------------------------
# Admin (verification)
# ---------------------------------------------------------------------------
async def require_admin(request: Request) -> Dict[str, Any]:
    user = await get_current_user(
        session_token=request.cookies.get("session_token"),
        authorization=request.headers.get("authorization"),
    )
    if not user:
        raise HTTPException(401, "Not authenticated")
    if not user.get("is_admin"):
        raise HTTPException(403, "Admin only")
    return user


# ---------------------------------------------------------------------------
# Admin (usuários / RBAC básico — só o booleano is_admin, ver CONTRACTS.md #6)
# ---------------------------------------------------------------------------
@api.get("/admin/users")
async def admin_list_users(request: Request):
    await require_admin(request)
    rows = await pool.fetch(
        "SELECT user_id, email, name, is_admin, created_at FROM users ORDER BY created_at"
    )
    return _rows(rows)


@api.post("/admin/users/{user_id}/role")
async def admin_set_user_role(user_id: str, request: Request, is_admin: bool = Body(..., embed=True)):
    admin = await require_admin(request)
    if user_id == admin["user_id"] and not is_admin:
        raise HTTPException(400, "Você não pode remover seu próprio acesso de admin")
    result = await pool.execute("UPDATE users SET is_admin = $1 WHERE user_id = $2", is_admin, user_id)
    if result == "UPDATE 0":
        raise HTTPException(404, "Usuário não encontrado")
    return {"ok": True}


@api.delete("/admin/users/{user_id}")
async def admin_delete_user(user_id: str, request: Request):
    admin = await require_admin(request)
    if user_id == admin["user_id"]:
        raise HTTPException(400, "Você não pode apagar sua própria conta")
    try:
        result = await pool.execute("DELETE FROM users WHERE user_id = $1", user_id)
    except asyncpg.ForeignKeyViolationError:
        raise HTTPException(409, "Não é possível apagar: este usuário tem reservas, avaliações ou pagamentos registrados")
    if result == "DELETE 0":
        raise HTTPException(404, "Usuário não encontrado")
    return {"ok": True}


@api.get("/admin/verification/queue")
async def verification_queue(request: Request):
    await require_admin(request)
    rows = await pool.fetch(
        "SELECT * FROM massagistas WHERE is_deleted = false AND verified = false LIMIT 500"
    )
    return [_massagista_out(_row(r)) for r in rows]


@api.get("/admin/verification/all")
async def verification_all(request: Request):
    await require_admin(request)
    rows = await pool.fetch(
        "SELECT * FROM massagistas WHERE is_deleted = false ORDER BY verified ASC, name ASC LIMIT 500"
    )
    return [_massagista_out(_row(r)) for r in rows]


async def _set_verification(mid: str, status: str, verified: bool, id_check: bool, photo_check: bool,
                             address_check: bool, verified_at: Optional[datetime], verified_by: Optional[str],
                             notes: Optional[str]) -> Dict[str, Any]:
    result = await pool.execute(
        """
        UPDATE massagistas SET
            verified = $1, verification_status = $2, verification_id_check = $3,
            verification_photo_check = $4, verification_address_check = $5,
            verification_verified_at = $6, verification_verified_by = $7, verification_notes = $8
        WHERE id = $9 AND is_deleted = false
        """,
        verified, status, id_check, photo_check, address_check, verified_at, verified_by, notes, mid,
    )
    if result == "UPDATE 0":
        raise HTTPException(404, "Massagista não encontrada")
    return {
        "status": status,
        "id_check": id_check,
        "photo_check": photo_check,
        "address_check": address_check,
        "verified_at": verified_at.isoformat() if verified_at else None,
        "verified_by": verified_by,
        "notes": notes,
    }


@api.post("/admin/verification/{mid}/approve")
async def approve_verification(mid: str, payload: VerificationAction, request: Request):
    admin = await require_admin(request)
    rows = await pool.fetch(
        "SELECT kind, content_type FROM verification_documents WHERE massagista_id = $1", mid
    )
    by_kind = {r["kind"]: r["content_type"] for r in rows}
    # Duas formas válidas de mandar o documento: (1) frente + verso, as duas
    # como imagem; (2) um PDF só na frente (cobre CNH Digital e digitalização
    # de frente+verso num arquivo — ver migrations/0004). Selfie é sempre
    # obrigatória nos dois casos.
    missing = set()
    if "selfie" not in by_kind:
        missing.add("selfie")
    if "id_document_front" not in by_kind:
        missing.add("id_document_front")
    elif by_kind["id_document_front"] != "application/pdf" and "id_document_back" not in by_kind:
        missing.add("id_document_back")
    if missing:
        raise HTTPException(400, f"Faltam documentos obrigatórios: {', '.join(sorted(missing))}")
    verification = await _set_verification(
        mid, "verified", True, payload.id_check, payload.photo_check, payload.address_check,
        datetime.now(timezone.utc), admin["email"], payload.notes,
    )
    return {"ok": True, "verification": verification}


@api.post("/admin/verification/{mid}/reject")
async def reject_verification(mid: str, payload: VerificationAction, request: Request):
    admin = await require_admin(request)
    if not (payload.notes or "").strip():
        raise HTTPException(400, "Informe o motivo da rejeição — a profissional vai ver essa mensagem")
    verification = await _set_verification(
        mid, "rejected", False, payload.id_check, payload.photo_check, payload.address_check,
        datetime.now(timezone.utc), admin["email"], payload.notes,
    )
    return {"ok": True, "verification": verification}


@api.post("/admin/verification/{mid}/revoke")
async def revoke_verification(mid: str, request: Request):
    admin = await require_admin(request)
    await _set_verification(
        mid, "pending", False, False, False, False,
        None, admin["email"], "Revogada para nova verificação",
    )
    return {"ok": True}


# ---------------------------------------------------------------------------
# Files (object storage)
# ---------------------------------------------------------------------------
def _public_file_url(storage_path: str) -> str:
    return f"/api/files/{storage_path}"


@api.get("/files/{path:path}")
async def get_file(path: str):
    record = _row(await pool.fetchrow(
        "SELECT * FROM files WHERE storage_path = $1 AND is_deleted = false", path
    ))
    if not record:
        raise HTTPException(404, "Arquivo não encontrado")
    data, content_type = get_object(path)
    headers = {
        "Cache-Control": "public, max-age=86400, immutable",
        "ETag": f'"{record["id"]}"',
    }
    return Response(content=data, media_type=record.get("content_type") or content_type, headers=headers)


async def _admin_upload(admin: Dict[str, Any], mid: str, kind: str, file: UploadFile) -> Dict[str, Any]:
    if kind == "image":
        if file.content_type not in ALLOWED_IMAGE:
            raise HTTPException(400, "Formato de imagem não suportado (use JPG, PNG ou WEBP)")
    elif kind == "video":
        if file.content_type not in ALLOWED_VIDEO:
            raise HTTPException(400, "Formato de vídeo não suportado (use MP4, MOV ou WEBM)")
    ext = EXT_FOR.get(file.content_type, "bin")
    storage_path = f"{APP_NAME}/massagistas/{mid}/{uuid.uuid4().hex}.{ext}"
    data = await file.read()
    max_bytes = 100 * 1024 * 1024 if kind == "video" else 8 * 1024 * 1024
    if len(data) > max_bytes:
        raise HTTPException(413, f"Arquivo excede o limite de {max_bytes // (1024 * 1024)}MB")
    result = put_object(storage_path, data, file.content_type)
    record_id = f"f_{uuid.uuid4().hex[:12]}"
    size = result.get("size", len(data))
    await pool.execute(
        """
        INSERT INTO files (id, massagista_id, kind, storage_path, content_type, size, original_filename, uploaded_by)
        VALUES ($1,$2,$3,$4,$5,$6,$7,$8)
        """,
        record_id, mid, kind, result["path"], file.content_type, size, file.filename, admin["email"],
    )
    return {
        "id": record_id, "massagista_id": mid, "kind": kind, "storage_path": result["path"],
        "content_type": file.content_type, "size": size, "original_filename": file.filename,
        "uploaded_by": admin["email"], "url": _public_file_url(result["path"]),
    }


# ---------------------------------------------------------------------------
# Documentos de verificação (documento de identidade + selfie)
# ---------------------------------------------------------------------------
# Aprovação é manual (admin compara as duas fotos no painel) — sem
# verificação facial automática por decisão consciente, ver migrations/0003.
# Arquivos NÃO passam por _public_file_url/`/api/files` (público) — só saem
# por /admin/verification-documents/{id}/file, atrás de require_admin.
async def _upload_verification_document(mid: str, kind: str, file: UploadFile) -> Dict[str, Any]:
    if kind == "selfie":
        if file.content_type not in ALLOWED_IMAGE:
            raise HTTPException(400, "Formato de imagem não suportado (use JPG, PNG ou WEBP)")
    elif file.content_type not in ALLOWED_DOCUMENT:
        raise HTTPException(400, "Formato não suportado (use JPG, PNG, WEBP ou PDF)")
    ext = EXT_FOR.get(file.content_type, "bin")
    storage_path = f"{APP_NAME}/verification/{mid}/{kind}_{uuid.uuid4().hex}.{ext}"
    data = await file.read()
    if len(data) > 8 * 1024 * 1024:
        raise HTTPException(413, "Arquivo excede o limite de 8MB")

    old_path = await pool.fetchval(
        "SELECT storage_path FROM verification_documents WHERE massagista_id = $1 AND kind = $2", mid, kind,
    )
    result = put_object(storage_path, data, file.content_type)
    doc_id = f"vd_{uuid.uuid4().hex[:12]}"
    row = _row(await pool.fetchrow(
        """
        INSERT INTO verification_documents (id, massagista_id, kind, storage_path, content_type, size)
        VALUES ($1,$2,$3,$4,$5,$6)
        ON CONFLICT (massagista_id, kind) DO UPDATE
            SET id = $1, storage_path = $4, content_type = $5, size = $6, uploaded_at = now()
        RETURNING id, kind, uploaded_at
        """,
        doc_id, mid, kind, result["path"], file.content_type, result.get("size", len(data)),
    ))
    if old_path:
        _storage_full_path(old_path).unlink(missing_ok=True)
    # Reenvio depois de rejeitada: sai do estado "rejeitado" e volta pra fila
    # de análise — sem isso a profissional ficaria presa vendo "rejeitada" no
    # próprio painel mesmo depois de corrigir e reenviar.
    await pool.execute(
        "UPDATE massagistas SET verification_status = 'pending' WHERE id = $1 AND verification_status = 'rejected'",
        mid,
    )
    return row


@api.post("/me/profile/verification/id-document-front")
async def upload_my_id_document_front(request: Request, file: UploadFile = File(...)):
    user = await get_current_user(
        session_token=request.cookies.get("session_token"),
        authorization=request.headers.get("authorization"),
    )
    if not user:
        raise HTTPException(401, "Faça login")
    mid = await pool.fetchval(
        "SELECT id FROM massagistas WHERE owner_user_id = $1 AND is_deleted = false", user["user_id"]
    )
    if not mid:
        raise HTTPException(404, "Crie seu perfil profissional antes de enviar documentos")
    return {"ok": True, "document": await _upload_verification_document(mid, "id_document_front", file)}


@api.post("/me/profile/verification/id-document-back")
async def upload_my_id_document_back(request: Request, file: UploadFile = File(...)):
    user = await get_current_user(
        session_token=request.cookies.get("session_token"),
        authorization=request.headers.get("authorization"),
    )
    if not user:
        raise HTTPException(401, "Faça login")
    mid = await pool.fetchval(
        "SELECT id FROM massagistas WHERE owner_user_id = $1 AND is_deleted = false", user["user_id"]
    )
    if not mid:
        raise HTTPException(404, "Crie seu perfil profissional antes de enviar documentos")
    return {"ok": True, "document": await _upload_verification_document(mid, "id_document_back", file)}


@api.post("/me/profile/verification/selfie")
async def upload_my_selfie(request: Request, file: UploadFile = File(...)):
    user = await get_current_user(
        session_token=request.cookies.get("session_token"),
        authorization=request.headers.get("authorization"),
    )
    if not user:
        raise HTTPException(401, "Faça login")
    mid = await pool.fetchval(
        "SELECT id FROM massagistas WHERE owner_user_id = $1 AND is_deleted = false", user["user_id"]
    )
    if not mid:
        raise HTTPException(404, "Crie seu perfil profissional antes de enviar documentos")
    return {"ok": True, "document": await _upload_verification_document(mid, "selfie", file)}


@api.get("/me/profile/verification/status")
async def my_verification_documents_status(request: Request):
    user = await get_current_user(
        session_token=request.cookies.get("session_token"),
        authorization=request.headers.get("authorization"),
    )
    if not user:
        raise HTTPException(401, "Faça login")
    mid = await pool.fetchval(
        "SELECT id FROM massagistas WHERE owner_user_id = $1 AND is_deleted = false", user["user_id"]
    )
    if not mid:
        return {"id_document_front": None, "id_document_back": None, "selfie": None}
    rows = await pool.fetch(
        "SELECT kind, uploaded_at FROM verification_documents WHERE massagista_id = $1", mid
    )
    by_kind = {r["kind"]: r["uploaded_at"].isoformat() for r in rows}
    return {
        "id_document_front": by_kind.get("id_document_front"),
        "id_document_back": by_kind.get("id_document_back"),
        "selfie": by_kind.get("selfie"),
    }


@api.get("/me/profile/verification/{kind}/file")
async def my_verification_document_file(kind: str, request: Request):
    user = await get_current_user(
        session_token=request.cookies.get("session_token"),
        authorization=request.headers.get("authorization"),
    )
    if not user:
        raise HTTPException(401, "Faça login")
    if kind not in ("id_document_front", "id_document_back", "selfie"):
        raise HTTPException(400, "Tipo inválido")
    mid = await pool.fetchval(
        "SELECT id FROM massagistas WHERE owner_user_id = $1 AND is_deleted = false", user["user_id"]
    )
    if not mid:
        raise HTTPException(404, "Perfil não encontrado")
    record = _row(await pool.fetchrow(
        "SELECT * FROM verification_documents WHERE massagista_id = $1 AND kind = $2", mid, kind
    ))
    if not record:
        raise HTTPException(404, "Documento não encontrado")
    data, content_type = get_object(record["storage_path"])
    return Response(content=data, media_type=record.get("content_type") or content_type)


@api.get("/admin/massagistas/{mid}/verification-documents")
async def admin_list_verification_documents(mid: str, request: Request):
    await require_admin(request)
    rows = await pool.fetch(
        "SELECT id, kind, content_type, uploaded_at FROM verification_documents WHERE massagista_id = $1", mid
    )
    return [
        {**_row(r), "url": f"/admin/verification-documents/{r['id']}/file"}
        for r in rows
    ]


@api.get("/admin/verification-documents/{doc_id}/file")
async def admin_get_verification_document_file(doc_id: str, request: Request):
    await require_admin(request)
    record = _row(await pool.fetchrow(
        "SELECT * FROM verification_documents WHERE id = $1", doc_id
    ))
    if not record:
        raise HTTPException(404, "Documento não encontrado")
    data, content_type = get_object(record["storage_path"])
    return Response(content=data, media_type=record.get("content_type") or content_type)


@api.put("/admin/massagistas/{mid}")
async def admin_update_massagista(mid: str, payload: ProfileUpdate, request: Request):
    await require_admin(request)
    existing = await pool.fetchval("SELECT 1 FROM massagistas WHERE id = $1 AND is_deleted = false", mid)
    if not existing:
        raise HTTPException(404, "Massagista não encontrada")

    data = payload.model_dump(exclude_unset=True)
    sets: List[str] = []
    params: List[Any] = []

    def add(col: str, value: Any):
        params.append(value)
        sets.append(f"{col} = ${len(params)}")

    for k in ("name", "bio", "experience_years", "ddd", "phone", "specialties", "languages"):
        if k in data:
            add(k, data[k])
    if "bairro_slug" in data:
        b = BAIRRO_MAP.get(data["bairro_slug"])
        if not b:
            raise HTTPException(400, "Bairro inválido")
        add("bairro", b.name)
        add("bairro_slug", b.slug)
        add("lat", b.lat)
        add("lng", b.lng)
    if "price_60" in data:
        add("price_60", float(data["price_60"]))
        add("hourly_rate", float(data["price_60"]))
    if "price_90" in data:
        add("price_90", float(data["price_90"]))
    if "price_120" in data:
        add("price_120", float(data["price_120"]))

    if sets:
        params.append(mid)
        await pool.execute(f"UPDATE massagistas SET {', '.join(sets)} WHERE id = ${len(params)}", *params)

    fresh = _massagista_out(_row(await pool.fetchrow("SELECT * FROM massagistas WHERE id = $1", mid)))
    return fresh


@api.post("/admin/massagistas/{mid}/photo")
async def upload_photo(mid: str, request: Request, file: UploadFile = File(...)):
    admin = await require_admin(request)
    exists = await pool.fetchval("SELECT 1 FROM massagistas WHERE id = $1 AND is_deleted = false", mid)
    if not exists:
        raise HTTPException(404, "Massagista não encontrada")
    f = await _admin_upload(admin, mid, "image", file)
    url = f["url"]
    await pool.execute("UPDATE massagistas SET gallery = array_append(gallery, $1) WHERE id = $2", url, mid)
    fresh = _massagista_out(_row(await pool.fetchrow("SELECT * FROM massagistas WHERE id = $1", mid)))
    return {"url": url, "massagista": fresh}


@api.delete("/admin/massagistas/{mid}/photo")
async def delete_photo(mid: str, request: Request, url: str = Body(..., embed=True)):
    admin = await require_admin(request)
    m = _massagista_out(_row(await pool.fetchrow("SELECT * FROM massagistas WHERE id = $1 AND is_deleted = false", mid)))
    if not m:
        raise HTTPException(404, "Massagista não encontrada")
    await pool.execute("UPDATE massagistas SET gallery = array_remove(gallery, $1) WHERE id = $2", url, mid)
    # If main_image was this URL, fallback to first gallery item
    if m.get("main_image") == url:
        remaining = [g for g in m.get("gallery", []) if g != url]
        new_main = remaining[0] if remaining else ""
        await pool.execute("UPDATE massagistas SET main_image = $1 WHERE id = $2", new_main, mid)
    # Soft-delete file record if it's an uploaded file
    if "/api/files/" in url:
        storage_path = url.split("/api/files/", 1)[1]
        await pool.execute(
            "UPDATE files SET is_deleted = true, deleted_by = $1, deleted_at = $2 WHERE storage_path = $3",
            admin["email"], datetime.now(timezone.utc), storage_path,
        )
    fresh = _massagista_out(_row(await pool.fetchrow("SELECT * FROM massagistas WHERE id = $1", mid)))
    return {"ok": True, "massagista": fresh}


@api.post("/admin/massagistas/{mid}/set-main")
async def set_main_image(mid: str, request: Request, url: str = Body(..., embed=True)):
    await require_admin(request)
    m = _massagista_out(_row(await pool.fetchrow("SELECT * FROM massagistas WHERE id = $1 AND is_deleted = false", mid)))
    if not m:
        raise HTTPException(404, "Massagista não encontrada")
    if url not in (m.get("gallery") or []):
        raise HTTPException(400, "URL precisa estar na galeria primeiro")
    await pool.execute("UPDATE massagistas SET main_image = $1 WHERE id = $2", url, mid)
    fresh = _massagista_out(_row(await pool.fetchrow("SELECT * FROM massagistas WHERE id = $1", mid)))
    return {"ok": True, "massagista": fresh}


@api.post("/admin/massagistas/{mid}/video")
async def upload_video(
    mid: str,
    request: Request,
    file: UploadFile = File(...),
    thumb: Optional[UploadFile] = File(None),
):
    admin = await require_admin(request)
    m = _massagista_out(_row(await pool.fetchrow("SELECT * FROM massagistas WHERE id = $1 AND is_deleted = false", mid)))
    if not m:
        raise HTTPException(404, "Massagista não encontrada")
    f = await _admin_upload(admin, mid, "video", file)
    url = f["url"]
    # Soft-delete previous video file record if it pointed at storage
    prev = m.get("video_url", "")
    if prev and "/api/files/" in prev:
        storage_path = prev.split("/api/files/", 1)[1]
        await pool.execute(
            "UPDATE files SET is_deleted = true, deleted_at = $1 WHERE storage_path = $2",
            datetime.now(timezone.utc), storage_path,
        )
    # If thumbnail file provided (extracted from video on client), use it
    video_thumb = None
    if thumb is not None:
        tf = await _admin_upload(admin, mid, "image", thumb)
        video_thumb = tf["url"]
    elif not m.get("video_thumb"):
        video_thumb = m.get("main_image") or (m.get("gallery") or [""])[0]
    if video_thumb is not None:
        await pool.execute("UPDATE massagistas SET video_url = $1, video_thumb = $2 WHERE id = $3", url, video_thumb, mid)
    else:
        await pool.execute("UPDATE massagistas SET video_url = $1 WHERE id = $2", url, mid)
    fresh = _massagista_out(_row(await pool.fetchrow("SELECT * FROM massagistas WHERE id = $1", mid)))
    return {"url": url, "massagista": fresh}


@api.post("/admin/massagistas/{mid}/video-thumb")
async def upload_video_thumb(mid: str, request: Request, file: UploadFile = File(...)):
    admin = await require_admin(request)
    m = _massagista_out(_row(await pool.fetchrow("SELECT * FROM massagistas WHERE id = $1 AND is_deleted = false", mid)))
    if not m:
        raise HTTPException(404, "Massagista não encontrada")
    if not m.get("video_url"):
        raise HTTPException(400, "Profissional não possui vídeo")
    f = await _admin_upload(admin, mid, "image", file)
    await pool.execute("UPDATE massagistas SET video_thumb = $1 WHERE id = $2", f["url"], mid)
    fresh = _massagista_out(_row(await pool.fetchrow("SELECT * FROM massagistas WHERE id = $1", mid)))
    return {"url": f["url"], "massagista": fresh}


# ---------------------------------------------------------------------------
# Auth (Emergent Google Auth)
# ---------------------------------------------------------------------------
@api.post("/auth/session")
async def auth_session(request: Request, response: Response):
    """Frontend sends X-Session-ID header (from URL fragment) — backend exchanges with Emergent."""
    session_id = request.headers.get("X-Session-ID")
    if not session_id:
        raise HTTPException(400, "Missing X-Session-ID header")
    async with httpx.AsyncClient(timeout=15.0) as hc:
        r = await hc.get(EMERGENT_AUTH_SESSION_URL, headers={"X-Session-ID": session_id})
    if r.status_code != 200:
        raise HTTPException(401, "Invalid session")
    data = r.json()
    email = data["email"]
    name = data.get("name", email)
    picture = data.get("picture", "")
    session_token = data["session_token"]

    # Upsert user
    is_admin_env = email.lower() in ADMIN_EMAILS
    user = _row(await pool.fetchrow("SELECT * FROM users WHERE email = $1", email))
    if not user:
        # First-ever user becomes admin automatically (bootstrap),
        # or any email in ADMIN_EMAILS env var
        total_users = await pool.fetchval("SELECT count(*) FROM users")
        is_admin = is_admin_env or total_users == 0
        user_id = f"user_{uuid.uuid4().hex[:12]}"
        created_at = datetime.now(timezone.utc)
        await pool.execute(
            "INSERT INTO users (user_id, email, name, picture, is_admin, created_at) VALUES ($1,$2,$3,$4,$5,$6)",
            user_id, email, name, picture, is_admin, created_at,
        )
        user = {
            "user_id": user_id, "email": email, "name": name, "picture": picture,
            "is_admin": is_admin, "created_at": created_at.isoformat(),
        }
    else:
        is_admin = bool(user.get("is_admin")) or is_admin_env
        await pool.execute(
            "UPDATE users SET name = $1, picture = $2, is_admin = $3 WHERE email = $4",
            name, picture, is_admin, email,
        )
        user["name"] = name
        user["picture"] = picture
        user["is_admin"] = is_admin

    # Persist session
    expires = datetime.now(timezone.utc) + timedelta(days=7)
    await pool.execute(
        "INSERT INTO user_sessions (session_token, user_id, expires_at) VALUES ($1,$2,$3)",
        session_token, user["user_id"], expires,
    )

    # Set httpOnly cookie
    response.set_cookie(
        key="session_token",
        value=session_token,
        httponly=True,
        secure=True,
        samesite="none",
        path="/",
        max_age=7 * 24 * 60 * 60,
    )
    return {"user": user, "session_token": session_token}


@api.get("/auth/me")
async def auth_me(
    session_token: Optional[str] = Cookie(default=None),
    authorization: Optional[str] = Header(default=None),
):
    user = await get_current_user(session_token=session_token, authorization=authorization)
    if not user:
        raise HTTPException(401, "Not authenticated")
    return user


@api.post("/auth/logout")
async def auth_logout(
    response: Response,
    session_token: Optional[str] = Cookie(default=None),
    authorization: Optional[str] = Header(default=None),
):
    token = session_token
    if not token and authorization and authorization.lower().startswith("bearer "):
        token = authorization.split(" ", 1)[1].strip()
    if token:
        await pool.execute("DELETE FROM user_sessions WHERE session_token = $1", token)
    response.delete_cookie("session_token", path="/")
    return {"ok": True}


# ---------------------------------------------------------------------------
# Bookings
# ---------------------------------------------------------------------------
def _amount_for(m: Dict[str, Any], duration: int) -> float:
    if duration == 60:
        return float(m["price_60"])
    if duration == 90:
        return float(m["price_90"])
    if duration == 120:
        return float(m["price_120"])
    raise HTTPException(400, "Duração inválida")


@api.post("/bookings")
async def create_booking(payload: BookingCreate, request: Request):
    user = await get_current_user(
        session_token=request.cookies.get("session_token"),
        authorization=request.headers.get("authorization"),
    )
    if not user:
        raise HTTPException(401, "Faça login para reservar")
    m = _massagista_out(_row(await pool.fetchrow(
        "SELECT * FROM massagistas WHERE id = $1 AND is_deleted = false", payload.massagista_id
    )))
    if not m:
        raise HTTPException(404, "Massagista não encontrada")
    if payload.location_type not in ("studio", "home"):
        raise HTTPException(400, "Local inválido")
    if payload.location_type == "home" and not (payload.address and payload.address.strip()):
        raise HTTPException(400, "Endereço obrigatório para atendimento em domicílio")
    amount = _amount_for(m, payload.duration)
    booking_id = f"b_{uuid.uuid4().hex[:10]}"
    row = await pool.fetchrow(
        """
        INSERT INTO bookings (id, user_id, user_email, massagista_id, massagista_name, massagista_image,
                               bairro, date, time, duration, location_type, address, notes, amount)
        VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14)
        RETURNING *
        """,
        booking_id, user["user_id"], user["email"], m["id"], m["name"], m["main_image"], m["bairro"],
        _parse_date(payload.date), _parse_time(payload.time), payload.duration, payload.location_type,
        payload.address, payload.notes, amount,
    )
    return _row(row)


@api.get("/bookings/me")
async def my_bookings(request: Request):
    user = await get_current_user(
        session_token=request.cookies.get("session_token"),
        authorization=request.headers.get("authorization"),
    )
    if not user:
        raise HTTPException(401, "Not authenticated")
    rows = await pool.fetch(
        "SELECT * FROM bookings WHERE user_id = $1 ORDER BY created_at DESC LIMIT 200", user["user_id"]
    )
    return _rows(rows)


@api.get("/bookings/{bid}")
async def get_booking(bid: str, request: Request):
    user = await get_current_user(
        session_token=request.cookies.get("session_token"),
        authorization=request.headers.get("authorization"),
    )
    if not user:
        raise HTTPException(401, "Not authenticated")
    doc = _row(await pool.fetchrow("SELECT * FROM bookings WHERE id = $1 AND user_id = $2", bid, user["user_id"]))
    if not doc:
        raise HTTPException(404, "Reserva não encontrada")
    return doc


# ---------------------------------------------------------------------------
# Stripe checkout (SDK oficial `stripe` — ver .ai/context/CONTRACTS.md #9)
# ---------------------------------------------------------------------------
@api.post("/checkout/session")
async def create_checkout(payload: CheckoutCreateReq, http_request: Request):
    user = await get_current_user(
        session_token=http_request.cookies.get("session_token"),
        authorization=http_request.headers.get("authorization"),
    )
    if not user:
        raise HTTPException(401, "Faça login")
    booking = _row(await pool.fetchrow(
        "SELECT * FROM bookings WHERE id = $1 AND user_id = $2", payload.booking_id, user["user_id"]
    ))
    if not booking:
        raise HTTPException(404, "Reserva não encontrada")

    origin = payload.origin_url.rstrip("/")
    success_url = f"{origin}/checkout/success?session_id={{CHECKOUT_SESSION_ID}}"
    cancel_url = f"{origin}/reserva/{booking['id']}?cancelled=1"

    # Amount comes from DB only (server-side)
    amount_brl = float(booking["amount"])
    session = await stripe.checkout.Session.create_async(
        mode="payment",
        line_items=[{
            "price_data": {
                "currency": "brl",
                "product_data": {"name": f"Reserva · {booking['massagista_name']}"},
                "unit_amount": round(amount_brl * 100),
            },
            "quantity": 1,
        }],
        success_url=success_url,
        cancel_url=cancel_url,
        metadata={
            "booking_id": booking["id"],
            "user_id": user["user_id"],
            "user_email": user["email"],
        },
    )

    # Save payment transaction
    await pool.execute(
        """
        INSERT INTO payment_transactions (session_id, booking_id, user_id, user_email, amount, status, payment_status)
        VALUES ($1,$2,$3,$4,$5,'initiated','pending')
        """,
        session.id, booking["id"], user["user_id"], user["email"], amount_brl,
    )

    await pool.execute("UPDATE bookings SET payment_session_id = $1 WHERE id = $2", session.id, booking["id"])

    return {"url": session.url, "session_id": session.id}


@api.get("/checkout/status/{session_id}")
async def checkout_status(session_id: str, http_request: Request):
    tx = _row(await pool.fetchrow("SELECT * FROM payment_transactions WHERE session_id = $1", session_id))
    if not tx:
        raise HTTPException(404, "Pagamento não encontrado")

    session = await stripe.checkout.Session.retrieve_async(session_id)

    # Idempotent update
    booking = _row(await pool.fetchrow("SELECT * FROM bookings WHERE id = $1", tx["booking_id"]))
    booking_already_confirmed = bool(booking and booking.get("status") == "confirmed")

    new_status = "completed" if session.payment_status == "paid" else session.status
    await pool.execute(
        "UPDATE payment_transactions SET status = $1, payment_status = $2, updated_at = $3 WHERE session_id = $4",
        new_status, session.payment_status, datetime.now(timezone.utc), session_id,
    )

    if session.payment_status == "paid" and not booking_already_confirmed:
        await pool.execute("UPDATE bookings SET status = 'confirmed' WHERE id = $1", tx["booking_id"])

    return {
        "status": session.status,
        "payment_status": session.payment_status,
        "amount_total": session.amount_total,
        "currency": session.currency,
        "booking_id": tx["booking_id"],
    }


@api.post("/webhook/stripe")
async def stripe_webhook(request: Request):
    body = await request.body()
    signature = request.headers.get("Stripe-Signature")
    try:
        evt = stripe.Webhook.construct_event(body, signature, STRIPE_WEBHOOK_SECRET)
    except Exception as e:
        logger.exception("Webhook error: %s", e)
        raise HTTPException(400, "Bad webhook")

    obj = evt["data"]["object"]
    if evt["type"] in ("checkout.session.completed", "checkout.session.async_payment_succeeded"):
        session_id = obj["id"]
        payment_status = obj.get("payment_status", "unpaid")
        await pool.execute(
            "UPDATE payment_transactions SET payment_status = $1, updated_at = $2 WHERE session_id = $3",
            payment_status, datetime.now(timezone.utc), session_id,
        )
        if payment_status == "paid":
            tx = _row(await pool.fetchrow("SELECT * FROM payment_transactions WHERE session_id = $1", session_id))
            if tx:
                await pool.execute(
                    "UPDATE bookings SET status = 'confirmed' WHERE id = $1 AND status != 'confirmed'",
                    tx["booking_id"],
                )
    return {"received": True}


# ---------------------------------------------------------------------------
# Reviews
# ---------------------------------------------------------------------------
@api.post("/bookings/{bid}/review")
async def create_review(bid: str, payload: ReviewCreate, request: Request):
    user = await get_current_user(
        session_token=request.cookies.get("session_token"),
        authorization=request.headers.get("authorization"),
    )
    if not user:
        raise HTTPException(401, "Faça login")
    booking = _row(await pool.fetchrow("SELECT * FROM bookings WHERE id = $1 AND user_id = $2", bid, user["user_id"]))
    if not booking:
        raise HTTPException(404, "Reserva não encontrada")
    if booking["status"] != "confirmed":
        raise HTTPException(400, "Só é possível avaliar reservas confirmadas")
    existing = await pool.fetchval("SELECT 1 FROM reviews WHERE booking_id = $1", bid)
    if existing:
        raise HTTPException(400, "Você já avaliou esta reserva")

    review_id = f"r_{uuid.uuid4().hex[:10]}"
    comment = (payload.comment or "").strip() or None
    review = _row(await pool.fetchrow(
        """
        INSERT INTO reviews (id, booking_id, massagista_id, user_id, user_name, user_picture, rating, comment)
        VALUES ($1,$2,$3,$4,$5,$6,$7,$8)
        RETURNING *
        """,
        review_id, bid, booking["massagista_id"], user["user_id"], user.get("name", "Cliente"),
        user.get("picture", ""), int(payload.rating), comment,
    ))

    # Update massagista aggregate rating
    m = _row(await pool.fetchrow("SELECT reviews, rating FROM massagistas WHERE id = $1", booking["massagista_id"]))
    if m:
        old_count = int(m.get("reviews", 0))
        old_rating = float(m.get("rating", 0.0))
        new_count = old_count + 1
        new_rating = round((old_rating * old_count + review["rating"]) / new_count, 2)
        await pool.execute(
            "UPDATE massagistas SET reviews = $1, rating = $2 WHERE id = $3",
            new_count, new_rating, booking["massagista_id"],
        )

    return review


@api.get("/massagistas/{mid}/reviews")
async def list_reviews(mid: str, limit: int = Query(20, le=100)):
    rows = await pool.fetch(
        "SELECT * FROM reviews WHERE massagista_id = $1 ORDER BY created_at DESC LIMIT $2", mid, limit
    )
    return _rows(rows)


# ---------------------------------------------------------------------------
# Professional self-service (autocadastro)
# ---------------------------------------------------------------------------
async def _require_owner(request: Request, mid: str) -> Dict[str, Any]:
    user = await get_current_user(
        session_token=request.cookies.get("session_token"),
        authorization=request.headers.get("authorization"),
    )
    if not user:
        raise HTTPException(401, "Faça login")
    m = _row(await pool.fetchrow("SELECT * FROM massagistas WHERE id = $1 AND is_deleted = false", mid))
    if not m:
        raise HTTPException(404, "Perfil não encontrado")
    if m.get("owner_user_id") != user["user_id"] and not user.get("is_admin"):
        raise HTTPException(403, "Sem permissão")
    return user


@api.get("/me/profile")
async def my_profile(request: Request):
    user = await get_current_user(
        session_token=request.cookies.get("session_token"),
        authorization=request.headers.get("authorization"),
    )
    if not user:
        raise HTTPException(401, "Faça login")
    doc = _massagista_out(_row(await pool.fetchrow(
        "SELECT * FROM massagistas WHERE owner_user_id = $1 AND is_deleted = false", user["user_id"]
    )))
    return {"profile": doc}


@api.post("/me/profile")
async def create_my_profile(payload: ProfileCreate, request: Request):
    user = await get_current_user(
        session_token=request.cookies.get("session_token"),
        authorization=request.headers.get("authorization"),
    )
    if not user:
        raise HTTPException(401, "Faça login")
    existing = await pool.fetchval("SELECT 1 FROM massagistas WHERE owner_user_id = $1", user["user_id"])
    if existing:
        raise HTTPException(400, "Você já tem um perfil profissional")
    b = BAIRRO_MAP.get(payload.bairro_slug)
    if not b:
        raise HTTPException(400, "Bairro inválido")
    price_60 = float(payload.price_60)
    price_90 = float(payload.price_90) if payload.price_90 else round(price_60 * 1.4, 2)
    price_120 = float(payload.price_120) if payload.price_120 else round(price_60 * 1.8, 2)
    mid = f"m_{uuid.uuid4().hex[:10]}"
    gallery = [user["picture"]] if user.get("picture") else []
    row = await pool.fetchrow(
        """
        INSERT INTO massagistas (
            id, owner_user_id, name, bairro, bairro_slug, lat, lng, rating, reviews, bio, specialties,
            hourly_rate, price_60, price_90, price_120, main_image, gallery, video_url, video_thumb,
            experience_years, languages, ddd, phone, verified, verification_status, verification_notes
        ) VALUES (
            $1,$2,$3,$4,$5,$6,$7,0,0,$8,$9,$10,$10,$11,$12,$13,$14,'','',$15,$16,$17,$18,false,
            'pending', 'Auto-cadastrado — aguardando verificação'
        )
        RETURNING *
        """,
        mid, user["user_id"], payload.name, b.name, b.slug, b.lat, b.lng, payload.bio, payload.specialties,
        price_60, price_90, price_120, user.get("picture", ""), gallery,
        int(payload.experience_years), payload.languages, (payload.ddd or "").strip(), (payload.phone or "").strip(),
    )
    return _massagista_out(_row(row))


@api.put("/me/profile")
async def update_my_profile(payload: ProfileUpdate, request: Request):
    user = await get_current_user(
        session_token=request.cookies.get("session_token"),
        authorization=request.headers.get("authorization"),
    )
    if not user:
        raise HTTPException(401, "Faça login")
    existing = _row(await pool.fetchrow(
        "SELECT * FROM massagistas WHERE owner_user_id = $1 AND is_deleted = false", user["user_id"]
    ))
    if not existing:
        raise HTTPException(404, "Perfil não encontrado")

    data = payload.model_dump(exclude_unset=True)
    sets: List[str] = []
    params: List[Any] = []

    def add(col: str, value: Any):
        params.append(value)
        sets.append(f"{col} = ${len(params)}")

    for k in ("name", "bio", "specialties", "experience_years", "languages"):
        if k in data:
            add(k, data[k])
    if "bairro_slug" in data:
        b = BAIRRO_MAP.get(data["bairro_slug"])
        if not b:
            raise HTTPException(400, "Bairro inválido")
        add("bairro", b.name)
        add("bairro_slug", b.slug)
        add("lat", b.lat)
        add("lng", b.lng)
    if "price_60" in data:
        add("price_60", float(data["price_60"]))
        add("hourly_rate", float(data["price_60"]))
    if "price_90" in data:
        add("price_90", float(data["price_90"]))
    if "price_120" in data:
        add("price_120", float(data["price_120"]))

    if sets:
        params.append(existing["id"])
        await pool.execute(f"UPDATE massagistas SET {', '.join(sets)} WHERE id = ${len(params)}", *params)

    fresh = _massagista_out(_row(await pool.fetchrow("SELECT * FROM massagistas WHERE id = $1", existing["id"])))
    return fresh


@api.post("/me/profile/photo")
async def my_profile_photo(request: Request, file: UploadFile = File(...)):
    user = await get_current_user(
        session_token=request.cookies.get("session_token"),
        authorization=request.headers.get("authorization"),
    )
    if not user:
        raise HTTPException(401, "Faça login")
    m = _massagista_out(_row(await pool.fetchrow(
        "SELECT * FROM massagistas WHERE owner_user_id = $1 AND is_deleted = false", user["user_id"]
    )))
    if not m:
        raise HTTPException(404, "Crie seu perfil primeiro")
    f = await _admin_upload({"email": user["email"]}, m["id"], "image", file)
    url = f["url"]
    # If no real main image yet (or pointing at google picture), set this as main too
    if not m.get("main_image") or m["main_image"] == user.get("picture"):
        await pool.execute(
            "UPDATE massagistas SET gallery = array_append(gallery, $1), main_image = $1 WHERE id = $2", url, m["id"]
        )
    else:
        await pool.execute("UPDATE massagistas SET gallery = array_append(gallery, $1) WHERE id = $2", url, m["id"])
    fresh = _massagista_out(_row(await pool.fetchrow("SELECT * FROM massagistas WHERE id = $1", m["id"])))
    return {"url": url, "massagista": fresh}


@api.delete("/me/profile/photo")
async def my_delete_photo(request: Request, url: str = Body(..., embed=True)):
    user = await get_current_user(
        session_token=request.cookies.get("session_token"),
        authorization=request.headers.get("authorization"),
    )
    if not user:
        raise HTTPException(401, "Faça login")
    m = _massagista_out(_row(await pool.fetchrow(
        "SELECT * FROM massagistas WHERE owner_user_id = $1 AND is_deleted = false", user["user_id"]
    )))
    if not m:
        raise HTTPException(404, "Perfil não encontrado")
    await pool.execute("UPDATE massagistas SET gallery = array_remove(gallery, $1) WHERE id = $2", url, m["id"])
    if m.get("main_image") == url:
        remaining = [g for g in m.get("gallery", []) if g != url]
        await pool.execute(
            "UPDATE massagistas SET main_image = $1 WHERE id = $2", remaining[0] if remaining else "", m["id"]
        )
    if "/api/files/" in url:
        storage_path = url.split("/api/files/", 1)[1]
        await pool.execute(
            "UPDATE files SET is_deleted = true, deleted_by = $1, deleted_at = $2 WHERE storage_path = $3",
            user["email"], datetime.now(timezone.utc), storage_path,
        )
    fresh = _massagista_out(_row(await pool.fetchrow("SELECT * FROM massagistas WHERE id = $1", m["id"])))
    return {"ok": True, "massagista": fresh}


# ---------------------------------------------------------------------------
# WhatsApp click tracking
# ---------------------------------------------------------------------------
@api.post("/whatsapp/click")
async def whatsapp_click(payload: WhatsAppClick, request: Request):
    user = await get_current_user(
        session_token=request.cookies.get("session_token"),
        authorization=request.headers.get("authorization"),
    )
    m = _row(await pool.fetchrow("SELECT * FROM massagistas WHERE id = $1 AND is_deleted = false", payload.massagista_id))
    if not m:
        raise HTTPException(404, "Massagista não encontrada")
    click_id = f"wc_{uuid.uuid4().hex[:10]}"
    await pool.execute(
        """
        INSERT INTO whatsapp_clicks (id, massagista_id, massagista_name, user_id, user_email, user_name, source, user_agent)
        VALUES ($1,$2,$3,$4,$5,$6,$7,$8)
        """,
        click_id, payload.massagista_id, m["name"],
        user["user_id"] if user else None, user["email"] if user else None, user.get("name") if user else None,
        payload.source or "detail", request.headers.get("user-agent", "")[:300],
    )
    return {"ok": True}


@api.get("/admin/whatsapp/stats")
async def whatsapp_stats(request: Request):
    await require_admin(request)
    click_rows = await pool.fetch(
        """
        SELECT massagista_id, count(*) AS clicks,
               count(DISTINCT user_id) FILTER (WHERE user_id IS NOT NULL) AS unique_users,
               max(created_at) AS last_click_at
        FROM whatsapp_clicks
        GROUP BY massagista_id
        """
    )
    by_id = {r["massagista_id"]: _row(r) for r in click_rows}

    # Confirmed bookings per massagista
    booked_rows = await pool.fetch(
        "SELECT massagista_id, count(*) AS confirmed FROM bookings WHERE status = 'confirmed' GROUP BY massagista_id"
    )
    booked_by_id = {r["massagista_id"]: r["confirmed"] for r in booked_rows}

    # Build result with massagista name
    docs = await pool.fetch("SELECT id, name, bairro, main_image FROM massagistas WHERE is_deleted = false LIMIT 500")
    out = []
    total_clicks = 0
    total_confirmed = 0
    for d in docs:
        r = by_id.get(d["id"], {})
        clicks = int(r.get("clicks", 0))
        unique = int(r.get("unique_users", 0))
        confirmed = int(booked_by_id.get(d["id"], 0))
        conversion = round((confirmed / clicks) * 100, 1) if clicks > 0 else None
        out.append({
            "massagista_id": d["id"],
            "name": d["name"],
            "bairro": d["bairro"],
            "main_image": d["main_image"],
            "clicks": clicks,
            "unique_users": unique,
            "confirmed_bookings": confirmed,
            "conversion_rate_pct": conversion,
            "last_click_at": r.get("last_click_at"),
        })
        total_clicks += clicks
        total_confirmed += confirmed
    out.sort(key=lambda x: -x["clicks"])
    return {
        "total_clicks": total_clicks,
        "total_confirmed_bookings": total_confirmed,
        "global_conversion_pct": round((total_confirmed / total_clicks) * 100, 1) if total_clicks > 0 else None,
        "by_massagista": out,
    }


# ---------------------------------------------------------------------------
# Admin: bookings (manual confirmation for offline payments)
# ---------------------------------------------------------------------------
@api.get("/admin/bookings")
async def admin_list_bookings(request: Request, status: Optional[str] = Query(None), limit: int = Query(100, le=500)):
    await require_admin(request)
    if status:
        rows = await pool.fetch(
            "SELECT * FROM bookings WHERE status = $1 ORDER BY created_at DESC LIMIT $2", status, limit
        )
    else:
        rows = await pool.fetch("SELECT * FROM bookings ORDER BY created_at DESC LIMIT $1", limit)
    return _rows(rows)


@api.post("/admin/bookings/manual")
async def admin_manual_booking(payload: ManualBookingCreate, request: Request):
    admin = await require_admin(request)
    m = _row(await pool.fetchrow("SELECT * FROM massagistas WHERE id = $1 AND is_deleted = false", payload.massagista_id))
    if not m:
        raise HTTPException(404, "Massagista não encontrada")
    user = _row(await pool.fetchrow("SELECT * FROM users WHERE email = $1", payload.user_email.strip().lower()))
    if not user:
        raise HTTPException(404, "Cliente não encontrado — peça para o cliente fazer login pelo menos uma vez antes")
    amount = _amount_for(m, payload.duration)
    method = payload.payment_method if payload.payment_method in ("whatsapp", "pix", "cash", "manual") else "manual"
    booking_id = f"b_{uuid.uuid4().hex[:10]}"
    row = await pool.fetchrow(
        """
        INSERT INTO bookings (id, user_id, user_email, massagista_id, massagista_name, massagista_image, bairro,
                               date, time, duration, location_type, notes, amount, status, payment_method,
                               manual_confirmed_by, manual_confirmed_at)
        VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,'studio',$11,$12,'confirmed',$13,$14,$15)
        RETURNING *
        """,
        booking_id, user["user_id"], user["email"], m["id"], m["name"], m["main_image"], m["bairro"],
        _parse_date(payload.date), _parse_time(payload.time), payload.duration, payload.notes, amount,
        method, admin["email"], datetime.now(timezone.utc),
    )
    return _row(row)


@api.post("/me/profile/set-main")
async def my_set_main(request: Request, url: str = Body(..., embed=True)):
    user = await get_current_user(
        session_token=request.cookies.get("session_token"),
        authorization=request.headers.get("authorization"),
    )
    if not user:
        raise HTTPException(401, "Faça login")
    m = _massagista_out(_row(await pool.fetchrow(
        "SELECT * FROM massagistas WHERE owner_user_id = $1 AND is_deleted = false", user["user_id"]
    )))
    if not m:
        raise HTTPException(404, "Perfil não encontrado")
    if url not in (m.get("gallery") or []):
        raise HTTPException(400, "URL precisa estar na galeria primeiro")
    await pool.execute("UPDATE massagistas SET main_image = $1 WHERE id = $2", url, m["id"])
    fresh = _massagista_out(_row(await pool.fetchrow("SELECT * FROM massagistas WHERE id = $1", m["id"])))
    return {"ok": True, "massagista": fresh}


@api.post("/me/profile/video")
async def my_profile_video(
    request: Request,
    file: UploadFile = File(...),
    thumb: Optional[UploadFile] = File(None),
):
    user = await get_current_user(
        session_token=request.cookies.get("session_token"),
        authorization=request.headers.get("authorization"),
    )
    if not user:
        raise HTTPException(401, "Faça login")
    m = _massagista_out(_row(await pool.fetchrow(
        "SELECT * FROM massagistas WHERE owner_user_id = $1 AND is_deleted = false", user["user_id"]
    )))
    if not m:
        raise HTTPException(404, "Crie seu perfil primeiro")
    f = await _admin_upload({"email": user["email"]}, m["id"], "video", file)
    url = f["url"]
    prev = m.get("video_url", "")
    if prev and "/api/files/" in prev:
        sp = prev.split("/api/files/", 1)[1]
        await pool.execute(
            "UPDATE files SET is_deleted = true, deleted_at = $1 WHERE storage_path = $2",
            datetime.now(timezone.utc), sp,
        )
    video_thumb = None
    if thumb is not None:
        tf = await _admin_upload({"email": user["email"]}, m["id"], "image", thumb)
        video_thumb = tf["url"]
    elif not m.get("video_thumb"):
        video_thumb = m.get("main_image") or (m.get("gallery") or [""])[0]
    if video_thumb is not None:
        await pool.execute("UPDATE massagistas SET video_url = $1, video_thumb = $2 WHERE id = $3", url, video_thumb, m["id"])
    else:
        await pool.execute("UPDATE massagistas SET video_url = $1 WHERE id = $2", url, m["id"])
    fresh = _massagista_out(_row(await pool.fetchrow("SELECT * FROM massagistas WHERE id = $1", m["id"])))
    return {"url": url, "massagista": fresh}


@api.post("/me/profile/video-thumb")
async def my_profile_video_thumb(request: Request, file: UploadFile = File(...)):
    user = await get_current_user(
        session_token=request.cookies.get("session_token"),
        authorization=request.headers.get("authorization"),
    )
    if not user:
        raise HTTPException(401, "Faça login")
    m = _massagista_out(_row(await pool.fetchrow(
        "SELECT * FROM massagistas WHERE owner_user_id = $1 AND is_deleted = false", user["user_id"]
    )))
    if not m:
        raise HTTPException(404, "Crie seu perfil primeiro")
    if not m.get("video_url"):
        raise HTTPException(400, "Você ainda não tem vídeo")
    f = await _admin_upload({"email": user["email"]}, m["id"], "image", file)
    await pool.execute("UPDATE massagistas SET video_thumb = $1 WHERE id = $2", f["url"], m["id"])
    fresh = _massagista_out(_row(await pool.fetchrow("SELECT * FROM massagistas WHERE id = $1", m["id"])))
    return {"url": f["url"], "massagista": fresh}


# ---------------------------------------------------------------------------
# Profile views tracking
# ---------------------------------------------------------------------------
@api.post("/massagistas/{mid}/view")
async def track_view(mid: str, request: Request):
    """Fire-and-forget view counter. Skips owner self-views and obvious bots."""
    user = await get_current_user(
        session_token=request.cookies.get("session_token"),
        authorization=request.headers.get("authorization"),
    )
    m = _row(await pool.fetchrow(
        "SELECT id, owner_user_id FROM massagistas WHERE id = $1 AND is_deleted = false", mid
    ))
    if not m:
        return {"ok": False}
    # Skip owner self-views
    if user and m.get("owner_user_id") == user.get("user_id"):
        return {"ok": True, "skipped": "owner"}
    ua = (request.headers.get("user-agent") or "")[:300]
    if any(k in ua.lower() for k in ("bot", "crawl", "spider", "preview")):
        return {"ok": True, "skipped": "bot"}
    await pool.execute(
        "INSERT INTO profile_views (id, massagista_id, user_id, user_agent) VALUES ($1,$2,$3,$4)",
        f"pv_{uuid.uuid4().hex[:10]}", mid, user["user_id"] if user else None, ua,
    )
    return {"ok": True}


# ---------------------------------------------------------------------------
# Owner stats panel
# ---------------------------------------------------------------------------
@api.get("/me/stats")
async def my_stats(request: Request):
    user = await get_current_user(
        session_token=request.cookies.get("session_token"),
        authorization=request.headers.get("authorization"),
    )
    if not user:
        raise HTTPException(401, "Faça login")
    m = _massagista_out(_row(await pool.fetchrow(
        "SELECT * FROM massagistas WHERE owner_user_id = $1 AND is_deleted = false", user["user_id"]
    )))
    if not m:
        raise HTTPException(404, "Crie seu perfil primeiro")
    mid = m["id"]
    cutoff_30 = datetime.now(timezone.utc) - timedelta(days=30)

    # Views
    views_total = await pool.fetchval("SELECT count(*) FROM profile_views WHERE massagista_id = $1", mid)
    views_30d = await pool.fetchval(
        "SELECT count(*) FROM profile_views WHERE massagista_id = $1 AND created_at >= $2", mid, cutoff_30
    )

    # WhatsApp clicks
    wa_total = await pool.fetchval("SELECT count(*) FROM whatsapp_clicks WHERE massagista_id = $1", mid)
    wa_30d = await pool.fetchval(
        "SELECT count(*) FROM whatsapp_clicks WHERE massagista_id = $1 AND created_at >= $2", mid, cutoff_30
    )

    # Bookings by status
    status_rows = await pool.fetch(
        "SELECT status, count(*) AS count, sum(amount) AS revenue FROM bookings WHERE massagista_id = $1 GROUP BY status",
        mid,
    )
    by_status = {r["status"]: {"count": int(r["count"]), "revenue": float(r["revenue"] or 0)} for r in status_rows}
    confirmed_count = by_status.get("confirmed", {}).get("count", 0) + by_status.get("completed", {}).get("count", 0)
    revenue_confirmed = by_status.get("confirmed", {}).get("revenue", 0) + by_status.get("completed", {}).get("revenue", 0)

    # Recent bookings (10 last)
    recent = _rows(await pool.fetch(
        """
        SELECT id, user_email, date, time, duration, amount, status, created_at
        FROM bookings WHERE massagista_id = $1 ORDER BY created_at DESC LIMIT 10
        """,
        mid,
    ))

    # Conversion (confirmed / views)
    conversion = round((confirmed_count / views_total) * 100, 1) if views_total > 0 else None

    return {
        "massagista_id": mid,
        "name": m.get("name"),
        "verified": bool(m.get("verified")),
        "views": {"total": views_total, "last_30d": views_30d},
        "whatsapp_clicks": {"total": wa_total, "last_30d": wa_30d},
        "bookings": {
            "pending_payment": by_status.get("pending_payment", {}).get("count", 0),
            "confirmed": by_status.get("confirmed", {}).get("count", 0),
            "completed": by_status.get("completed", {}).get("count", 0),
            "cancelled": by_status.get("cancelled", {}).get("count", 0),
            "total": sum(v["count"] for v in by_status.values()),
        },
        "revenue": {
            "confirmed": float(revenue_confirmed),
            "currency": "BRL",
        },
        "rating": {
            "average": float(m.get("rating") or 0),
            "count": int(m.get("reviews") or 0),
        },
        "conversion_rate_pct": conversion,
        "recent_bookings": recent,
    }


# ---------------------------------------------------------------------------
# Open Graph dynamic link (shares from WhatsApp/Insta show rich preview)
# ---------------------------------------------------------------------------
def _absolutize(url: str, base: str) -> str:
    if not url:
        return ""
    if url.startswith("http://") or url.startswith("https://"):
        return url
    if url.startswith("/"):
        return base.rstrip("/") + url
    return url


@api.get("/og/m/{mid}", response_class=HTMLResponse)
async def og_share(mid: str, request: Request, foto: Optional[int] = None):
    """Returns an HTML page with Open Graph meta tags + JS/meta redirect.
    Crawlers (WhatsApp, Telegram, Facebook, X) see the OG tags; real users get redirected."""
    import html as html_lib
    import json as _json
    m = _massagista_out(_row(await pool.fetchrow("SELECT * FROM massagistas WHERE id = $1 AND is_deleted = false", mid)))
    if not m:
        raise HTTPException(404, "Profissional não encontrada")

    base = str(request.base_url).rstrip("/")
    gallery = m.get("gallery") or []
    image = m.get("main_image") or (gallery[0] if gallery else "")
    if foto and 1 <= foto <= len(gallery):
        image = gallery[foto - 1]
    image_abs = _absolutize(image, base)

    title = f"{m.get('name','Profissional')} · Prime Encontros"
    bairro = m.get("bairro", "Rio de Janeiro")
    bio = (m.get("bio") or "").strip()
    desc = bio if len(bio) >= 30 else f"Massagem profissional em {bairro} · Prime Encontros · Reserva online segura"
    desc = desc[:280]

    target = f"/massagista/{mid}"
    if foto:
        target += f"?foto={foto}"
    target_abs = base + target

    # Safe-escape values
    e = html_lib.escape
    html = f"""<!doctype html>
<html lang="pt-BR">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{e(title)}</title>
<meta name="description" content="{e(desc)}">
<meta property="og:type" content="profile">
<meta property="og:site_name" content="Prime Encontros">
<meta property="og:title" content="{e(title)}">
<meta property="og:description" content="{e(desc)}">
<meta property="og:image" content="{e(image_abs)}">
<meta property="og:image:width" content="1200">
<meta property="og:image:height" content="1200">
<meta property="og:url" content="{e(target_abs)}">
<meta property="og:locale" content="pt_BR">
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:title" content="{e(title)}">
<meta name="twitter:description" content="{e(desc)}">
<meta name="twitter:image" content="{e(image_abs)}">
<link rel="canonical" href="{e(target_abs)}">
<meta http-equiv="refresh" content="0;url={e(target)}">
<script>window.location.replace({_json.dumps(target)});</script>
<style>body{{font-family:system-ui;background:#000;color:#fff;display:flex;align-items:center;justify-content:center;height:100vh;margin:0}}a{{color:#ef4444}}</style>
</head>
<body>
<p>Carregando perfil de <a href="{e(target)}">{e(m.get('name',''))}</a>...</p>
</body>
</html>"""
    return HTMLResponse(content=html, headers={"Cache-Control": "public, max-age=300"})


# ---------------------------------------------------------------------------
# Promotional card (PNG 1080x1080) — for Instagram/Status sharing
# ---------------------------------------------------------------------------
@api.get("/massagistas/{mid}/promo-card.png")
async def promo_card(mid: str, request: Request):
    m = _massagista_out(_row(await pool.fetchrow("SELECT * FROM massagistas WHERE id = $1 AND is_deleted = false", mid)))
    if not m:
        raise HTTPException(404, "Profissional não encontrada")
    base = str(request.base_url).rstrip("/")
    img_url = m.get("main_image") or ((m.get("gallery") or [""])[0])
    if img_url and img_url.startswith("/api/"):
        img_url = base + img_url
    png_bytes = await generate_promo_card(
        main_image_url=img_url,
        name=m.get("name", "Profissional"),
        bairro=m.get("bairro", "Rio de Janeiro"),
        rating=float(m.get("rating") or 0),
        reviews=int(m.get("reviews") or 0),
        verified=bool(m.get("verified")),
        cta_domain="primeencontros.com.br",
    )
    safe_name = "".join(c if c.isalnum() else "-" for c in m.get("name", "card")).strip("-").lower()[:40]
    headers = {
        "Cache-Control": "public, max-age=600",
        "Content-Disposition": f'inline; filename="prime-{safe_name}.png"',
    }
    return Response(content=png_bytes, media_type="image/png", headers=headers)



# ---------------------------------------------------------------------------
# App wiring
# ---------------------------------------------------------------------------
app.include_router(api)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origin_regex=".*",
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def startup():
    global pool
    # min/max_size baixos de propósito — RAM é escassa na VPS (ver .ai/docs/DEPLOY.md)
    pool = await asyncpg.create_pool(DATABASE_URL, min_size=1, max_size=5)
    STORAGE_DIR.mkdir(parents=True, exist_ok=True)
    await seed_massagistas()


@app.on_event("shutdown")
async def shutdown():
    await pool.close()
