"""
Oásis Rio – Backend API
Massage therapist marketplace for Rio de Janeiro.
"""
import os
import io
import uuid
import math
import logging
import requests
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import List, Optional, Dict, Any

import httpx
from fastapi import FastAPI, APIRouter, HTTPException, Request, Response, Cookie, Header, Query, UploadFile, File, Body
from fastapi.responses import JSONResponse, StreamingResponse, HTMLResponse
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
from pydantic import BaseModel, Field

from emergentintegrations.payments.stripe.checkout import (
    StripeCheckout,
    CheckoutSessionResponse,
    CheckoutStatusResponse,
    CheckoutSessionRequest,
)

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / ".env")

# ---------------------------------------------------------------------------
# Mongo
# ---------------------------------------------------------------------------
mongo_url = os.environ["MONGO_URL"]
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ["DB_NAME"]]

STRIPE_API_KEY = os.environ.get("STRIPE_API_KEY", "")
EMERGENT_LLM_KEY = os.environ.get("EMERGENT_LLM_KEY", "")
EMERGENT_AUTH_SESSION_URL = "https://demobackend.emergentagent.com/auth/v1/env/oauth/session-data"
ADMIN_EMAILS = {e.strip().lower() for e in os.environ.get("ADMIN_EMAILS", "").split(",") if e.strip()}

# ---------------------------------------------------------------------------
# Object storage (Emergent)
# ---------------------------------------------------------------------------
STORAGE_URL = "https://integrations.emergentagent.com/objstore/api/v1/storage"
APP_NAME = "prime-encontros"
_storage_key: Optional[str] = None
ALLOWED_IMAGE = {"image/jpeg", "image/jpg", "image/png", "image/webp"}
ALLOWED_VIDEO = {"video/mp4", "video/quicktime", "video/webm"}
EXT_FOR = {
    "image/jpeg": "jpg", "image/jpg": "jpg", "image/png": "png", "image/webp": "webp",
    "video/mp4": "mp4", "video/quicktime": "mov", "video/webm": "webm",
}


def init_storage() -> Optional[str]:
    global _storage_key
    if _storage_key:
        return _storage_key
    if not EMERGENT_LLM_KEY:
        logger.error("EMERGENT_LLM_KEY missing — storage disabled")
        return None
    try:
        r = requests.post(f"{STORAGE_URL}/init", json={"emergent_key": EMERGENT_LLM_KEY}, timeout=30)
        r.raise_for_status()
        _storage_key = r.json()["storage_key"]
        logger.info("Storage initialized")
        return _storage_key
    except Exception as e:
        logger.exception("Storage init failed: %s", e)
        return None


def put_object(path: str, data: bytes, content_type: str) -> Dict[str, Any]:
    key = init_storage()
    if not key:
        raise HTTPException(500, "Object storage indisponível")
    r = requests.put(
        f"{STORAGE_URL}/objects/{path}",
        headers={"X-Storage-Key": key, "Content-Type": content_type},
        data=data, timeout=120,
    )
    if r.status_code == 403:
        global _storage_key
        _storage_key = None
        key = init_storage()
        r = requests.put(
            f"{STORAGE_URL}/objects/{path}",
            headers={"X-Storage-Key": key, "Content-Type": content_type},
            data=data, timeout=120,
        )
    r.raise_for_status()
    return r.json()


def get_object(path: str) -> tuple:
    key = init_storage()
    if not key:
        raise HTTPException(500, "Object storage indisponível")
    r = requests.get(
        f"{STORAGE_URL}/objects/{path}",
        headers={"X-Storage-Key": key}, timeout=60,
    )
    if r.status_code == 403:
        global _storage_key
        _storage_key = None
        key = init_storage()
        r = requests.get(
            f"{STORAGE_URL}/objects/{path}",
            headers={"X-Storage-Key": key}, timeout=60,
        )
    if r.status_code == 404:
        raise HTTPException(404, "Arquivo não encontrado")
    r.raise_for_status()
    return r.content, r.headers.get("Content-Type", "application/octet-stream")

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
    count = await db.massagistas.count_documents({})
    if count > 0:
        return
    docs = []
    for i, (name, bairro_slug, rating, reviews, bio, specs, base_price, exp, langs) in enumerate(SEED_PROFILES):
        b = BAIRRO_MAP[bairro_slug]
        # small jitter so two massagistas in same bairro have slightly different coords
        jitter_lat = (i % 5) * 0.0008
        jitter_lng = (i % 4) * 0.0008
        portrait = PORTRAITS[i % len(PORTRAITS)]
        gallery = [portrait, SPA1, SPA2, SPA3 if i % 2 == 0 else SPA4]
        m = {
            "id": f"m_{uuid.uuid4().hex[:10]}",
            "name": name,
            "bairro": b.name,
            "bairro_slug": b.slug,
            "lat": b.lat + jitter_lat,
            "lng": b.lng + jitter_lng,
            "rating": rating,
            "reviews": reviews,
            "bio": bio,
            "specialties": specs,
            "hourly_rate": base_price,
            "price_60": base_price,
            "price_90": round(base_price * 1.4, 2),
            "price_120": round(base_price * 1.8, 2),
            "main_image": portrait,
            "gallery": gallery,
            "video_url": SAMPLE_VIDEO,
            "video_thumb": SPA1,
            "experience_years": exp,
            "languages": langs,
            "ddd": "21",
            "phone": f"99{(80000000 + i * 137):08d}",
            "verified": i < 8,  # first 8 are pre-verified for demo
            "verification": {
                "status": "verified" if i < 8 else "pending",
                "id_check": i < 8,
                "photo_check": i < 8,
                "address_check": i < 8,
                "verified_at": datetime.now(timezone.utc).isoformat() if i < 8 else None,
                "verified_by": "system_seed" if i < 8 else None,
            },
        }
        docs.append(m)
    await db.massagistas.insert_many(docs)
    logger.info(f"Seeded {len(docs)} massagistas")


async def migrate_massagistas():
    """Backfill verification + phone fields on existing seed docs."""
    await db.massagistas.update_many(
        {"verified": {"$exists": False}},
        {"$set": {
            "verified": False,
            "verification": {
                "status": "pending",
                "id_check": False,
                "photo_check": False,
                "address_check": False,
                "verified_at": None,
                "verified_by": None,
            },
        }},
    )
    await db.massagistas.update_many(
        {"ddd": {"$exists": False}},
        {"$set": {"ddd": "21", "phone": ""}},
    )


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


def clean(doc: Dict[str, Any]) -> Dict[str, Any]:
    doc.pop("_id", None)
    return doc


async def get_current_user(
    session_token: Optional[str] = Cookie(default=None),
    authorization: Optional[str] = Header(default=None),
) -> Optional[Dict[str, Any]]:
    token = session_token
    if not token and authorization and authorization.lower().startswith("bearer "):
        token = authorization.split(" ", 1)[1].strip()
    if not token:
        return None
    sess = await db.user_sessions.find_one({"session_token": token}, {"_id": 0})
    if not sess:
        return None
    expires_at = sess["expires_at"]
    if isinstance(expires_at, str):
        expires_at = datetime.fromisoformat(expires_at)
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    if expires_at < datetime.now(timezone.utc):
        return None
    user = await db.users.find_one({"user_id": sess["user_id"]}, {"_id": 0})
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
    query: Dict[str, Any] = {}
    if bairro:
        query["bairro_slug"] = bairro
    if verified_only:
        query["verified"] = True
    if q:
        query["$or"] = [
            {"name": {"$regex": q, "$options": "i"}},
            {"specialties": {"$regex": q, "$options": "i"}},
            {"bairro": {"$regex": q, "$options": "i"}},
        ]
    docs = await db.massagistas.find(query, {"_id": 0}).to_list(200)
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
    doc = await db.massagistas.find_one({"id": mid}, {"_id": 0})
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


@api.get("/admin/verification/queue")
async def verification_queue(request: Request):
    await require_admin(request)
    docs = await db.massagistas.find(
        {"$or": [{"verified": False}, {"verified": {"$exists": False}}]},
        {"_id": 0},
    ).to_list(500)
    return docs


@api.get("/admin/verification/all")
async def verification_all(request: Request):
    await require_admin(request)
    docs = await db.massagistas.find({}, {"_id": 0}).to_list(500)
    docs.sort(key=lambda x: (x.get("verified", False), x["name"]))
    return docs


@api.post("/admin/verification/{mid}/approve")
async def approve_verification(mid: str, payload: VerificationAction, request: Request):
    admin = await require_admin(request)
    m = await db.massagistas.find_one({"id": mid}, {"_id": 0})
    if not m:
        raise HTTPException(404, "Massagista não encontrada")
    verification = {
        "status": "verified",
        "id_check": payload.id_check,
        "photo_check": payload.photo_check,
        "address_check": payload.address_check,
        "verified_at": datetime.now(timezone.utc).isoformat(),
        "verified_by": admin["email"],
        "notes": payload.notes,
    }
    await db.massagistas.update_one(
        {"id": mid},
        {"$set": {"verified": True, "verification": verification}},
    )
    return {"ok": True, "verification": verification}


@api.post("/admin/verification/{mid}/reject")
async def reject_verification(mid: str, payload: VerificationAction, request: Request):
    admin = await require_admin(request)
    m = await db.massagistas.find_one({"id": mid}, {"_id": 0})
    if not m:
        raise HTTPException(404, "Massagista não encontrada")
    verification = {
        "status": "rejected",
        "id_check": payload.id_check,
        "photo_check": payload.photo_check,
        "address_check": payload.address_check,
        "verified_at": datetime.now(timezone.utc).isoformat(),
        "verified_by": admin["email"],
        "notes": payload.notes,
    }
    await db.massagistas.update_one(
        {"id": mid},
        {"$set": {"verified": False, "verification": verification}},
    )
    return {"ok": True, "verification": verification}


@api.post("/admin/verification/{mid}/revoke")
async def revoke_verification(mid: str, request: Request):
    admin = await require_admin(request)
    m = await db.massagistas.find_one({"id": mid}, {"_id": 0})
    if not m:
        raise HTTPException(404, "Massagista não encontrada")
    await db.massagistas.update_one(
        {"id": mid},
        {"$set": {
            "verified": False,
            "verification": {
                "status": "pending",
                "id_check": False,
                "photo_check": False,
                "address_check": False,
                "verified_at": None,
                "verified_by": admin["email"],
                "notes": "Revogada para nova verificação",
            },
        }},
    )
    return {"ok": True}


# ---------------------------------------------------------------------------
# Files (object storage)
# ---------------------------------------------------------------------------
def _public_file_url(storage_path: str) -> str:
    return f"/api/files/{storage_path}"


@api.get("/files/{path:path}")
async def get_file(path: str):
    record = await db.files.find_one({"storage_path": path, "is_deleted": False}, {"_id": 0})
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
    record = {
        "id": f"f_{uuid.uuid4().hex[:12]}",
        "massagista_id": mid,
        "kind": kind,
        "storage_path": result["path"],
        "content_type": file.content_type,
        "size": result.get("size", len(data)),
        "original_filename": file.filename,
        "uploaded_by": admin["email"],
        "is_deleted": False,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    await db.files.insert_one(dict(record))
    return {**record, "url": _public_file_url(result["path"])}


@api.put("/admin/massagistas/{mid}")
async def admin_update_massagista(mid: str, payload: ProfileUpdate, request: Request):
    await require_admin(request)
    existing = await db.massagistas.find_one({"id": mid}, {"_id": 0})
    if not existing:
        raise HTTPException(404, "Massagista não encontrada")

    update: Dict[str, Any] = {}
    data = payload.model_dump(exclude_unset=True)
    for k in ("name", "bio", "specialties", "experience_years", "languages", "ddd", "phone"):
        if k in data:
            update[k] = data[k]
    if "bairro_slug" in data:
        b = BAIRRO_MAP.get(data["bairro_slug"])
        if not b:
            raise HTTPException(400, "Bairro inválido")
        update.update({"bairro": b.name, "bairro_slug": b.slug, "lat": b.lat, "lng": b.lng})
    if "price_60" in data:
        update["price_60"] = float(data["price_60"])
        update["hourly_rate"] = float(data["price_60"])
    if "price_90" in data:
        update["price_90"] = float(data["price_90"])
    if "price_120" in data:
        update["price_120"] = float(data["price_120"])

    if update:
        await db.massagistas.update_one({"id": mid}, {"$set": update})
    fresh = await db.massagistas.find_one({"id": mid}, {"_id": 0})
    return fresh



@api.post("/admin/massagistas/{mid}/photo")
async def upload_photo(mid: str, request: Request, file: UploadFile = File(...)):
    admin = await require_admin(request)
    m = await db.massagistas.find_one({"id": mid}, {"_id": 0})
    if not m:
        raise HTTPException(404, "Massagista não encontrada")
    f = await _admin_upload(admin, mid, "image", file)
    url = f["url"]
    # Append to gallery; if first photo, also set as main_image
    update = {"$push": {"gallery": url}}
    if not m.get("main_image") or m.get("main_image", "").startswith("https://images.unsplash.com"):
        # Don't auto-override the seed main; admin can set explicitly
        pass
    await db.massagistas.update_one({"id": mid}, update)
    fresh = await db.massagistas.find_one({"id": mid}, {"_id": 0})
    return {"url": url, "massagista": fresh}


@api.delete("/admin/massagistas/{mid}/photo")
async def delete_photo(mid: str, request: Request, url: str = Body(..., embed=True)):
    admin = await require_admin(request)
    m = await db.massagistas.find_one({"id": mid}, {"_id": 0})
    if not m:
        raise HTTPException(404, "Massagista não encontrada")
    await db.massagistas.update_one({"id": mid}, {"$pull": {"gallery": url}})
    # If main_image was this URL, fallback to first gallery item
    if m.get("main_image") == url:
        remaining = [g for g in m.get("gallery", []) if g != url]
        new_main = remaining[0] if remaining else ""
        await db.massagistas.update_one({"id": mid}, {"$set": {"main_image": new_main}})
    # Soft-delete file record if it's an uploaded file
    if "/api/files/" in url:
        storage_path = url.split("/api/files/", 1)[1]
        await db.files.update_one(
            {"storage_path": storage_path},
            {"$set": {"is_deleted": True, "deleted_by": admin["email"], "deleted_at": datetime.now(timezone.utc).isoformat()}},
        )
    fresh = await db.massagistas.find_one({"id": mid}, {"_id": 0})
    return {"ok": True, "massagista": fresh}


@api.post("/admin/massagistas/{mid}/set-main")
async def set_main_image(mid: str, request: Request, url: str = Body(..., embed=True)):
    await require_admin(request)
    m = await db.massagistas.find_one({"id": mid}, {"_id": 0})
    if not m:
        raise HTTPException(404, "Massagista não encontrada")
    if url not in (m.get("gallery") or []):
        raise HTTPException(400, "URL precisa estar na galeria primeiro")
    await db.massagistas.update_one({"id": mid}, {"$set": {"main_image": url}})
    fresh = await db.massagistas.find_one({"id": mid}, {"_id": 0})
    return {"ok": True, "massagista": fresh}


@api.post("/admin/massagistas/{mid}/video")
async def upload_video(
    mid: str,
    request: Request,
    file: UploadFile = File(...),
    thumb: Optional[UploadFile] = File(None),
):
    admin = await require_admin(request)
    m = await db.massagistas.find_one({"id": mid}, {"_id": 0})
    if not m:
        raise HTTPException(404, "Massagista não encontrada")
    f = await _admin_upload(admin, mid, "video", file)
    url = f["url"]
    # Soft-delete previous video file record if it pointed at storage
    prev = m.get("video_url", "")
    if prev and "/api/files/" in prev:
        storage_path = prev.split("/api/files/", 1)[1]
        await db.files.update_one(
            {"storage_path": storage_path},
            {"$set": {"is_deleted": True, "deleted_at": datetime.now(timezone.utc).isoformat()}},
        )
    update = {"video_url": url}
    # If thumbnail file provided (extracted from video on client), use it
    if thumb is not None:
        tf = await _admin_upload(admin, mid, "image", thumb)
        update["video_thumb"] = tf["url"]
    elif not m.get("video_thumb"):
        update["video_thumb"] = m.get("main_image") or (m.get("gallery") or [""])[0]
    await db.massagistas.update_one({"id": mid}, {"$set": update})
    fresh = await db.massagistas.find_one({"id": mid}, {"_id": 0})
    return {"url": url, "massagista": fresh}


@api.post("/admin/massagistas/{mid}/video-thumb")
async def upload_video_thumb(mid: str, request: Request, file: UploadFile = File(...)):
    admin = await require_admin(request)
    m = await db.massagistas.find_one({"id": mid}, {"_id": 0})
    if not m:
        raise HTTPException(404, "Massagista não encontrada")
    if not m.get("video_url"):
        raise HTTPException(400, "Profissional não possui vídeo")
    f = await _admin_upload(admin, mid, "image", file)
    await db.massagistas.update_one({"id": mid}, {"$set": {"video_thumb": f["url"]}})
    fresh = await db.massagistas.find_one({"id": mid}, {"_id": 0})
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
    user = await db.users.find_one({"email": email}, {"_id": 0})
    is_admin_env = email.lower() in ADMIN_EMAILS
    if not user:
        # First-ever user becomes admin automatically (bootstrap),
        # or any email in ADMIN_EMAILS env var
        total_users = await db.users.count_documents({})
        is_admin = is_admin_env or total_users == 0
        user_id = f"user_{uuid.uuid4().hex[:12]}"
        user = {
            "user_id": user_id,
            "email": email,
            "name": name,
            "picture": picture,
            "is_admin": is_admin,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        await db.users.insert_one(dict(user))
    else:
        update = {"name": name, "picture": picture}
        if is_admin_env and not user.get("is_admin"):
            update["is_admin"] = True
        await db.users.update_one({"email": email}, {"$set": update})
        user.update(update)

    # Persist session
    expires = datetime.now(timezone.utc) + timedelta(days=7)
    await db.user_sessions.insert_one({
        "user_id": user["user_id"],
        "session_token": session_token,
        "expires_at": expires.isoformat(),
        "created_at": datetime.now(timezone.utc).isoformat(),
    })

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
        await db.user_sessions.delete_one({"session_token": token})
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
    m = await db.massagistas.find_one({"id": payload.massagista_id}, {"_id": 0})
    if not m:
        raise HTTPException(404, "Massagista não encontrada")
    if payload.location_type not in ("studio", "home"):
        raise HTTPException(400, "Local inválido")
    if payload.location_type == "home" and not (payload.address and payload.address.strip()):
        raise HTTPException(400, "Endereço obrigatório para atendimento em domicílio")
    amount = _amount_for(m, payload.duration)
    booking = {
        "id": f"b_{uuid.uuid4().hex[:10]}",
        "user_id": user["user_id"],
        "user_email": user["email"],
        "massagista_id": m["id"],
        "massagista_name": m["name"],
        "massagista_image": m["main_image"],
        "bairro": m["bairro"],
        "date": payload.date,
        "time": payload.time,
        "duration": payload.duration,
        "location_type": payload.location_type,
        "address": payload.address,
        "notes": payload.notes,
        "amount": amount,
        "currency": "brl",
        "status": "pending_payment",
        "payment_session_id": None,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    await db.bookings.insert_one(dict(booking))
    return booking


@api.get("/bookings/me")
async def my_bookings(request: Request):
    user = await get_current_user(
        session_token=request.cookies.get("session_token"),
        authorization=request.headers.get("authorization"),
    )
    if not user:
        raise HTTPException(401, "Not authenticated")
    docs = await db.bookings.find({"user_id": user["user_id"]}, {"_id": 0}).sort("created_at", -1).to_list(200)
    return docs


@api.get("/bookings/{bid}")
async def get_booking(bid: str, request: Request):
    user = await get_current_user(
        session_token=request.cookies.get("session_token"),
        authorization=request.headers.get("authorization"),
    )
    if not user:
        raise HTTPException(401, "Not authenticated")
    doc = await db.bookings.find_one({"id": bid, "user_id": user["user_id"]}, {"_id": 0})
    if not doc:
        raise HTTPException(404, "Reserva não encontrada")
    return doc


# ---------------------------------------------------------------------------
# Stripe checkout
# ---------------------------------------------------------------------------
def _stripe(http_request: Request) -> StripeCheckout:
    host_url = str(http_request.base_url).rstrip("/")
    webhook_url = f"{host_url}/api/webhook/stripe"
    return StripeCheckout(api_key=STRIPE_API_KEY, webhook_url=webhook_url)


@api.post("/checkout/session")
async def create_checkout(payload: CheckoutCreateReq, http_request: Request):
    user = await get_current_user(
        session_token=http_request.cookies.get("session_token"),
        authorization=http_request.headers.get("authorization"),
    )
    if not user:
        raise HTTPException(401, "Faça login")
    booking = await db.bookings.find_one(
        {"id": payload.booking_id, "user_id": user["user_id"]}, {"_id": 0}
    )
    if not booking:
        raise HTTPException(404, "Reserva não encontrada")

    origin = payload.origin_url.rstrip("/")
    success_url = f"{origin}/checkout/success?session_id={{CHECKOUT_SESSION_ID}}"
    cancel_url = f"{origin}/reserva/{booking['id']}?cancelled=1"

    # Amount comes from DB only (server-side)
    amount_usd_brl = float(booking["amount"])  # BRL
    stripe = _stripe(http_request)
    req = CheckoutSessionRequest(
        amount=amount_usd_brl,
        currency="brl",
        success_url=success_url,
        cancel_url=cancel_url,
        metadata={
            "booking_id": booking["id"],
            "user_id": user["user_id"],
            "user_email": user["email"],
        },
    )
    session: CheckoutSessionResponse = await stripe.create_checkout_session(req)

    # Save payment transaction
    await db.payment_transactions.insert_one({
        "session_id": session.session_id,
        "booking_id": booking["id"],
        "user_id": user["user_id"],
        "user_email": user["email"],
        "amount": amount_usd_brl,
        "currency": "brl",
        "status": "initiated",
        "payment_status": "pending",
        "metadata": {"booking_id": booking["id"]},
        "created_at": datetime.now(timezone.utc).isoformat(),
        "updated_at": datetime.now(timezone.utc).isoformat(),
    })

    await db.bookings.update_one(
        {"id": booking["id"]},
        {"$set": {"payment_session_id": session.session_id}},
    )

    return {"url": session.url, "session_id": session.session_id}


@api.get("/checkout/status/{session_id}")
async def checkout_status(session_id: str, http_request: Request):
    tx = await db.payment_transactions.find_one({"session_id": session_id}, {"_id": 0})
    if not tx:
        raise HTTPException(404, "Pagamento não encontrado")

    stripe = _stripe(http_request)
    status: CheckoutStatusResponse = await stripe.get_checkout_status(session_id)

    # Idempotent update
    booking_already_confirmed = False
    booking = await db.bookings.find_one({"id": tx["booking_id"]}, {"_id": 0})
    if booking and booking.get("status") == "confirmed":
        booking_already_confirmed = True

    new_status = "completed" if status.payment_status == "paid" else status.status
    await db.payment_transactions.update_one(
        {"session_id": session_id},
        {"$set": {
            "status": new_status,
            "payment_status": status.payment_status,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }},
    )

    if status.payment_status == "paid" and not booking_already_confirmed:
        await db.bookings.update_one(
            {"id": tx["booking_id"]},
            {"$set": {"status": "confirmed"}},
        )

    return {
        "status": status.status,
        "payment_status": status.payment_status,
        "amount_total": status.amount_total,
        "currency": status.currency,
        "booking_id": tx["booking_id"],
    }


@api.post("/webhook/stripe")
async def stripe_webhook(request: Request):
    body = await request.body()
    signature = request.headers.get("Stripe-Signature")
    stripe = _stripe(request)
    try:
        evt = await stripe.handle_webhook(body, signature)
    except Exception as e:
        logger.exception("Webhook error: %s", e)
        raise HTTPException(400, "Bad webhook")
    if evt.session_id:
        await db.payment_transactions.update_one(
            {"session_id": evt.session_id},
            {"$set": {
                "payment_status": evt.payment_status,
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }},
        )
        if evt.payment_status == "paid":
            tx = await db.payment_transactions.find_one({"session_id": evt.session_id}, {"_id": 0})
            if tx:
                await db.bookings.update_one(
                    {"id": tx["booking_id"], "status": {"$ne": "confirmed"}},
                    {"$set": {"status": "confirmed"}},
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
    booking = await db.bookings.find_one({"id": bid, "user_id": user["user_id"]}, {"_id": 0})
    if not booking:
        raise HTTPException(404, "Reserva não encontrada")
    if booking["status"] != "confirmed":
        raise HTTPException(400, "Só é possível avaliar reservas confirmadas")
    existing = await db.reviews.find_one({"booking_id": bid}, {"_id": 0})
    if existing:
        raise HTTPException(400, "Você já avaliou esta reserva")

    review = {
        "id": f"r_{uuid.uuid4().hex[:10]}",
        "booking_id": bid,
        "massagista_id": booking["massagista_id"],
        "user_id": user["user_id"],
        "user_name": user.get("name", "Cliente"),
        "user_picture": user.get("picture", ""),
        "rating": int(payload.rating),
        "comment": (payload.comment or "").strip() or None,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    await db.reviews.insert_one(dict(review))

    # Update massagista aggregate rating
    m = await db.massagistas.find_one({"id": booking["massagista_id"]}, {"_id": 0})
    if m:
        old_count = int(m.get("reviews", 0))
        old_rating = float(m.get("rating", 0.0))
        new_count = old_count + 1
        new_rating = round((old_rating * old_count + review["rating"]) / new_count, 2)
        await db.massagistas.update_one(
            {"id": booking["massagista_id"]},
            {"$set": {"reviews": new_count, "rating": new_rating}},
        )

    return review


@api.get("/massagistas/{mid}/reviews")
async def list_reviews(mid: str, limit: int = Query(20, le=100)):
    docs = await db.reviews.find({"massagista_id": mid}, {"_id": 0}).sort("created_at", -1).to_list(limit)
    return docs


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
    m = await db.massagistas.find_one({"id": mid}, {"_id": 0})
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
    doc = await db.massagistas.find_one({"owner_user_id": user["user_id"]}, {"_id": 0})
    return {"profile": doc}


@api.post("/me/profile")
async def create_my_profile(payload: ProfileCreate, request: Request):
    user = await get_current_user(
        session_token=request.cookies.get("session_token"),
        authorization=request.headers.get("authorization"),
    )
    if not user:
        raise HTTPException(401, "Faça login")
    existing = await db.massagistas.find_one({"owner_user_id": user["user_id"]}, {"_id": 0})
    if existing:
        raise HTTPException(400, "Você já tem um perfil profissional")
    b = BAIRRO_MAP.get(payload.bairro_slug)
    if not b:
        raise HTTPException(400, "Bairro inválido")
    price_60 = float(payload.price_60)
    doc = {
        "id": f"m_{uuid.uuid4().hex[:10]}",
        "owner_user_id": user["user_id"],
        "name": payload.name,
        "bairro": b.name,
        "bairro_slug": b.slug,
        "lat": b.lat,
        "lng": b.lng,
        "rating": 0.0,
        "reviews": 0,
        "bio": payload.bio,
        "specialties": payload.specialties,
        "hourly_rate": price_60,
        "price_60": price_60,
        "price_90": float(payload.price_90) if payload.price_90 else round(price_60 * 1.4, 2),
        "price_120": float(payload.price_120) if payload.price_120 else round(price_60 * 1.8, 2),
        "main_image": user.get("picture", ""),
        "gallery": [user.get("picture")] if user.get("picture") else [],
        "video_url": "",
        "video_thumb": "",
        "experience_years": int(payload.experience_years),
        "languages": payload.languages,
        "ddd": (payload.ddd or "").strip(),
        "phone": (payload.phone or "").strip(),
        "verified": False,
        "verification": {
            "status": "pending",
            "id_check": False,
            "photo_check": False,
            "address_check": False,
            "verified_at": None,
            "verified_by": None,
            "notes": "Auto-cadastrado — aguardando verificação",
        },
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    await db.massagistas.insert_one(dict(doc))
    return doc


@api.put("/me/profile")
async def update_my_profile(payload: ProfileUpdate, request: Request):
    user = await get_current_user(
        session_token=request.cookies.get("session_token"),
        authorization=request.headers.get("authorization"),
    )
    if not user:
        raise HTTPException(401, "Faça login")
    existing = await db.massagistas.find_one({"owner_user_id": user["user_id"]}, {"_id": 0})
    if not existing:
        raise HTTPException(404, "Perfil não encontrado")

    update: Dict[str, Any] = {}
    data = payload.model_dump(exclude_unset=True)
    for k in ("name", "bio", "specialties", "experience_years", "languages"):
        if k in data:
            update[k] = data[k]
    if "bairro_slug" in data:
        b = BAIRRO_MAP.get(data["bairro_slug"])
        if not b:
            raise HTTPException(400, "Bairro inválido")
        update.update({"bairro": b.name, "bairro_slug": b.slug, "lat": b.lat, "lng": b.lng})
    if "price_60" in data:
        update["price_60"] = float(data["price_60"])
        update["hourly_rate"] = float(data["price_60"])
    if "price_90" in data:
        update["price_90"] = float(data["price_90"])
    if "price_120" in data:
        update["price_120"] = float(data["price_120"])

    if update:
        await db.massagistas.update_one({"id": existing["id"]}, {"$set": update})
    fresh = await db.massagistas.find_one({"id": existing["id"]}, {"_id": 0})
    return fresh


@api.post("/me/profile/photo")
async def my_profile_photo(request: Request, file: UploadFile = File(...)):
    user = await get_current_user(
        session_token=request.cookies.get("session_token"),
        authorization=request.headers.get("authorization"),
    )
    if not user:
        raise HTTPException(401, "Faça login")
    m = await db.massagistas.find_one({"owner_user_id": user["user_id"]}, {"_id": 0})
    if not m:
        raise HTTPException(404, "Crie seu perfil primeiro")
    f = await _admin_upload({"email": user["email"]}, m["id"], "image", file)
    url = f["url"]
    update = {"$push": {"gallery": url}}
    # If no real main image yet (or pointing at google picture), set this as main
    if not m.get("main_image") or m["main_image"] == user.get("picture"):
        update["$set"] = {"main_image": url}
    await db.massagistas.update_one({"id": m["id"]}, update)
    fresh = await db.massagistas.find_one({"id": m["id"]}, {"_id": 0})
    return {"url": url, "massagista": fresh}


@api.delete("/me/profile/photo")
async def my_delete_photo(request: Request, url: str = Body(..., embed=True)):
    user = await get_current_user(
        session_token=request.cookies.get("session_token"),
        authorization=request.headers.get("authorization"),
    )
    if not user:
        raise HTTPException(401, "Faça login")
    m = await db.massagistas.find_one({"owner_user_id": user["user_id"]}, {"_id": 0})
    if not m:
        raise HTTPException(404, "Perfil não encontrado")
    await db.massagistas.update_one({"id": m["id"]}, {"$pull": {"gallery": url}})
    if m.get("main_image") == url:
        remaining = [g for g in m.get("gallery", []) if g != url]
        await db.massagistas.update_one({"id": m["id"]}, {"$set": {"main_image": remaining[0] if remaining else ""}})
    if "/api/files/" in url:
        storage_path = url.split("/api/files/", 1)[1]
        await db.files.update_one(
            {"storage_path": storage_path},
            {"$set": {"is_deleted": True, "deleted_by": user["email"], "deleted_at": datetime.now(timezone.utc).isoformat()}},
        )
    fresh = await db.massagistas.find_one({"id": m["id"]}, {"_id": 0})
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
    m = await db.massagistas.find_one({"id": payload.massagista_id}, {"_id": 0})
    if not m:
        raise HTTPException(404, "Massagista não encontrada")
    click = {
        "id": f"wc_{uuid.uuid4().hex[:10]}",
        "massagista_id": payload.massagista_id,
        "massagista_name": m["name"],
        "user_id": user["user_id"] if user else None,
        "user_email": user["email"] if user else None,
        "user_name": user.get("name") if user else None,
        "source": payload.source or "detail",
        "user_agent": request.headers.get("user-agent", "")[:300],
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    await db.whatsapp_clicks.insert_one(dict(click))
    return {"ok": True}


@api.get("/admin/whatsapp/stats")
async def whatsapp_stats(request: Request):
    await require_admin(request)
    pipeline = [
        {"$group": {
            "_id": "$massagista_id",
            "clicks": {"$sum": 1},
            "unique_users": {"$addToSet": "$user_id"},
            "last_click_at": {"$max": "$created_at"},
        }},
    ]
    raw = await db.whatsapp_clicks.aggregate(pipeline).to_list(500)
    by_id = {r["_id"]: r for r in raw}

    # Confirmed bookings per massagista
    bookings_pipeline = [
        {"$match": {"status": "confirmed"}},
        {"$group": {"_id": "$massagista_id", "confirmed": {"$sum": 1}}},
    ]
    booked_raw = await db.bookings.aggregate(bookings_pipeline).to_list(500)
    booked_by_id = {r["_id"]: r["confirmed"] for r in booked_raw}

    # Build result with massagista name
    docs = await db.massagistas.find({}, {"_id": 0, "id": 1, "name": 1, "bairro": 1, "main_image": 1}).to_list(500)
    out = []
    total_clicks = 0
    total_confirmed = 0
    for d in docs:
        r = by_id.get(d["id"], {})
        clicks = int(r.get("clicks", 0))
        unique = len([u for u in r.get("unique_users", []) if u])
        confirmed = int(booked_by_id.get(d["id"], 0))
        conversion = round((confirmed / clicks) * 100, 1) if clicks > 0 else None
        out.append({
            "massagista_id": d["id"],
            "name": d["name"],
            "bairro": d.get("bairro"),
            "main_image": d.get("main_image"),
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
    query: Dict[str, Any] = {}
    if status:
        query["status"] = status
    docs = await db.bookings.find(query, {"_id": 0}).sort("created_at", -1).to_list(limit)
    return docs


@api.post("/admin/bookings/manual")
async def admin_manual_booking(payload: ManualBookingCreate, request: Request):
    admin = await require_admin(request)
    m = await db.massagistas.find_one({"id": payload.massagista_id}, {"_id": 0})
    if not m:
        raise HTTPException(404, "Massagista não encontrada")
    user = await db.users.find_one({"email": payload.user_email.strip().lower()}, {"_id": 0})
    if not user:
        raise HTTPException(404, "Cliente não encontrado — peça para o cliente fazer login pelo menos uma vez antes")
    amount = _amount_for(m, payload.duration)
    method = payload.payment_method if payload.payment_method in ("whatsapp", "pix", "cash", "manual") else "manual"
    booking = {
        "id": f"b_{uuid.uuid4().hex[:10]}",
        "user_id": user["user_id"],
        "user_email": user["email"],
        "massagista_id": m["id"],
        "massagista_name": m["name"],
        "massagista_image": m["main_image"],
        "bairro": m["bairro"],
        "date": payload.date,
        "time": payload.time,
        "duration": payload.duration,
        "location_type": "studio",
        "address": None,
        "notes": payload.notes,
        "amount": amount,
        "currency": "brl",
        "status": "confirmed",
        "payment_session_id": None,
        "payment_method": method,
        "manual_confirmed_by": admin["email"],
        "manual_confirmed_at": datetime.now(timezone.utc).isoformat(),
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    await db.bookings.insert_one(dict(booking))
    return booking


@api.post("/me/profile/set-main")
async def my_set_main(request: Request, url: str = Body(..., embed=True)):
    user = await get_current_user(
        session_token=request.cookies.get("session_token"),
        authorization=request.headers.get("authorization"),
    )
    if not user:
        raise HTTPException(401, "Faça login")
    m = await db.massagistas.find_one({"owner_user_id": user["user_id"]}, {"_id": 0})
    if not m:
        raise HTTPException(404, "Perfil não encontrado")
    if url not in (m.get("gallery") or []):
        raise HTTPException(400, "URL precisa estar na galeria primeiro")
    await db.massagistas.update_one({"id": m["id"]}, {"$set": {"main_image": url}})
    fresh = await db.massagistas.find_one({"id": m["id"]}, {"_id": 0})
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
    m = await db.massagistas.find_one({"owner_user_id": user["user_id"]}, {"_id": 0})
    if not m:
        raise HTTPException(404, "Crie seu perfil primeiro")
    f = await _admin_upload({"email": user["email"]}, m["id"], "video", file)
    url = f["url"]
    prev = m.get("video_url", "")
    if prev and "/api/files/" in prev:
        sp = prev.split("/api/files/", 1)[1]
        await db.files.update_one({"storage_path": sp}, {"$set": {"is_deleted": True, "deleted_at": datetime.now(timezone.utc).isoformat()}})
    update = {"video_url": url}
    if thumb is not None:
        tf = await _admin_upload({"email": user["email"]}, m["id"], "image", thumb)
        update["video_thumb"] = tf["url"]
    elif not m.get("video_thumb"):
        update["video_thumb"] = m.get("main_image") or (m.get("gallery") or [""])[0]
    await db.massagistas.update_one({"id": m["id"]}, {"$set": update})
    fresh = await db.massagistas.find_one({"id": m["id"]}, {"_id": 0})
    return {"url": url, "massagista": fresh}


@api.post("/me/profile/video-thumb")
async def my_profile_video_thumb(request: Request, file: UploadFile = File(...)):
    user = await get_current_user(
        session_token=request.cookies.get("session_token"),
        authorization=request.headers.get("authorization"),
    )
    if not user:
        raise HTTPException(401, "Faça login")
    m = await db.massagistas.find_one({"owner_user_id": user["user_id"]}, {"_id": 0})
    if not m:
        raise HTTPException(404, "Crie seu perfil primeiro")
    if not m.get("video_url"):
        raise HTTPException(400, "Você ainda não tem vídeo")
    f = await _admin_upload({"email": user["email"]}, m["id"], "image", file)
    await db.massagistas.update_one({"id": m["id"]}, {"$set": {"video_thumb": f["url"]}})
    fresh = await db.massagistas.find_one({"id": m["id"]}, {"_id": 0})
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
    m = await db.massagistas.find_one({"id": mid}, {"_id": 0, "id": 1, "owner_user_id": 1})
    if not m:
        return {"ok": False}
    # Skip owner self-views
    if user and m.get("owner_user_id") == user.get("user_id"):
        return {"ok": True, "skipped": "owner"}
    ua = (request.headers.get("user-agent") or "")[:300]
    if any(k in ua.lower() for k in ("bot", "crawl", "spider", "preview")):
        return {"ok": True, "skipped": "bot"}
    await db.profile_views.insert_one({
        "id": f"pv_{uuid.uuid4().hex[:10]}",
        "massagista_id": mid,
        "user_id": user["user_id"] if user else None,
        "user_agent": ua,
        "created_at": datetime.now(timezone.utc).isoformat(),
    })
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
    m = await db.massagistas.find_one({"owner_user_id": user["user_id"]}, {"_id": 0})
    if not m:
        raise HTTPException(404, "Crie seu perfil primeiro")
    mid = m["id"]
    now = datetime.now(timezone.utc)
    cutoff_30 = (now - timedelta(days=30)).isoformat()

    # Views
    views_total = await db.profile_views.count_documents({"massagista_id": mid})
    views_30d = await db.profile_views.count_documents({"massagista_id": mid, "created_at": {"$gte": cutoff_30}})

    # WhatsApp clicks
    wa_total = await db.whatsapp_clicks.count_documents({"massagista_id": mid})
    wa_30d = await db.whatsapp_clicks.count_documents({"massagista_id": mid, "created_at": {"$gte": cutoff_30}})

    # Bookings by status
    pipeline = [
        {"$match": {"massagista_id": mid}},
        {"$group": {"_id": "$status", "count": {"$sum": 1}, "revenue": {"$sum": "$amount"}}},
    ]
    raw = await db.bookings.aggregate(pipeline).to_list(50)
    by_status = {r["_id"]: {"count": int(r["count"]), "revenue": float(r.get("revenue", 0) or 0)} for r in raw}
    confirmed_count = by_status.get("confirmed", {}).get("count", 0) + by_status.get("completed", {}).get("count", 0)
    revenue_confirmed = by_status.get("confirmed", {}).get("revenue", 0) + by_status.get("completed", {}).get("revenue", 0)

    # Recent bookings (10 last)
    recent = await db.bookings.find(
        {"massagista_id": mid},
        {"_id": 0, "id": 1, "user_email": 1, "date": 1, "time": 1, "duration": 1, "amount": 1, "status": 1, "created_at": 1},
    ).sort("created_at", -1).to_list(10)

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
    m = await db.massagistas.find_one({"id": mid}, {"_id": 0})
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
    init_storage()
    await seed_massagistas()
    await migrate_massagistas()


@app.on_event("shutdown")
async def shutdown():
    client.close()
