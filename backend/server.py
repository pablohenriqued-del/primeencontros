"""
Oásis Rio – Backend API
Massage therapist marketplace for Rio de Janeiro.
"""
import os
import uuid
import math
import logging
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import List, Optional, Dict, Any

import httpx
from fastapi import FastAPI, APIRouter, HTTPException, Request, Response, Cookie, Header, Query
from fastapi.responses import JSONResponse
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
EMERGENT_AUTH_SESSION_URL = "https://demobackend.emergentagent.com/auth/v1/env/oauth/session-data"
ADMIN_EMAILS = {e.strip().lower() for e in os.environ.get("ADMIN_EMAILS", "").split(",") if e.strip()}

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

# Portraits — curated Unsplash images
PORTRAITS = [
    "https://images.unsplash.com/photo-1598901978648-4d1c0d66518a?crop=entropy&cs=srgb&fm=jpg&w=800&q=80",
    "https://images.unsplash.com/photo-1756699197173-5ef672a423fa?crop=entropy&cs=srgb&fm=jpg&w=800&q=80",
    "https://images.unsplash.com/photo-1746813628081-0c8c1611aace?crop=entropy&cs=srgb&fm=jpg&w=800&q=80",
    "https://images.unsplash.com/photo-1573496359142-b8d87734a5a2?crop=entropy&cs=srgb&fm=jpg&w=800&q=80",
    "https://images.unsplash.com/photo-1544005313-94ddf0286df2?crop=entropy&cs=srgb&fm=jpg&w=800&q=80",
    "https://images.unsplash.com/photo-1494790108377-be9c29b29330?crop=entropy&cs=srgb&fm=jpg&w=800&q=80",
    "https://images.unsplash.com/photo-1500648767791-00dcc994a43e?crop=entropy&cs=srgb&fm=jpg&w=800&q=80",
    "https://images.unsplash.com/photo-1438761681033-6461ffad8d80?crop=entropy&cs=srgb&fm=jpg&w=800&q=80",
    "https://images.unsplash.com/photo-1487412720507-e7ab37603c6f?crop=entropy&cs=srgb&fm=jpg&w=800&q=80",
    "https://images.unsplash.com/photo-1521119989659-a83eee488004?crop=entropy&cs=srgb&fm=jpg&w=800&q=80",
    "https://images.unsplash.com/photo-1607746882042-944635dfe10e?crop=entropy&cs=srgb&fm=jpg&w=800&q=80",
    "https://images.unsplash.com/photo-1580489944761-15a19d654956?crop=entropy&cs=srgb&fm=jpg&w=800&q=80",
]

SEED_PROFILES = [
    ("Camila Souza", "ipanema", 4.9, 213, "Especialista em massagem relaxante e pedras quentes. Atendimento humanizado em estúdio com vista para o mar.",
        ["Relaxante", "Pedras Quentes", "Shiatsu"], 220.0, 8, ["Português", "Inglês"]),
    ("Mariana Costa", "leblon", 4.8, 187, "Terapeuta com formação em terapias orientais. Foco em alívio de tensões e dores musculares crônicas.",
        ["Shiatsu", "Tui Ná", "Reflexologia"], 280.0, 12, ["Português", "Inglês", "Espanhol"]),
    ("Rafael Silva", "copacabana", 4.7, 156, "Massoterapeuta esportivo com experiência em atletas profissionais. Recuperação muscular pós-treino.",
        ["Esportiva", "Drenagem", "Liberação Miofascial"], 250.0, 10, ["Português"]),
    ("Beatriz Almeida", "botafogo", 4.9, 298, "Sou apaixonada por aromaterapia. Sessões que combinam óleos essenciais e técnica suave.",
        ["Aromaterapia", "Relaxante", "Sueca"], 200.0, 6, ["Português", "Francês"]),
    ("Luís Henrique", "flamengo", 4.6, 92, "Quiropraxia e massagem ortopédica. Indicado para quem trabalha horas no computador.",
        ["Quiropraxia", "Ortopédica", "Postura"], 240.0, 9, ["Português"]),
    ("Isabela Martins", "jardim-botanico", 4.9, 341, "Drenagem linfática modeladora e pós-cirúrgico. Ambiente tranquilo no Jardim Botânico.",
        ["Drenagem Linfática", "Modeladora", "Pós-cirúrgico"], 260.0, 11, ["Português", "Inglês"]),
    ("André Pereira", "tijuca", 4.5, 78, "Massagem terapêutica com 7 anos de experiência. Atendo na clínica ou no seu endereço.",
        ["Terapêutica", "Relaxante", "Anti-stress"], 180.0, 7, ["Português"]),
    ("Fernanda Lima", "barra-da-tijuca", 4.8, 220, "Bambuterapia e ventosaterapia. Técnicas integradas para bem-estar profundo.",
        ["Bambuterapia", "Ventosaterapia", "Relaxante"], 270.0, 9, ["Português", "Inglês"]),
    ("Gustavo Rocha", "laranjeiras", 4.7, 134, "Massagem desportiva e liberação de gatilhos. Atendimento direto, sem firulas.",
        ["Esportiva", "Pontos de Gatilho", "Profunda"], 230.0, 8, ["Português", "Espanhol"]),
    ("Patrícia Nogueira", "lagoa", 4.9, 256, "Reiki e massagem energética. Para quem busca um equilíbrio além do físico.",
        ["Reiki", "Energética", "Relaxante"], 210.0, 13, ["Português", "Inglês"]),
    ("Diego Vasconcelos", "urca", 4.8, 167, "Estúdio acolhedor na Urca. Massagem sueca e desportiva de alto padrão.",
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
        gallery = [portrait, SPA1, SPA2, PORTRAITS[(i + 3) % len(PORTRAITS)]]
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
    """Backfill verification fields on existing seed docs."""
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
    await seed_massagistas()
    await migrate_massagistas()


@app.on_event("shutdown")
async def shutdown():
    client.close()
