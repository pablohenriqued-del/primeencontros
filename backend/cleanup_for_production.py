"""One-shot cleanup for production readiness.
Run: cd /app/backend && python3 cleanup_for_production.py
"""
from pymongo import MongoClient
import os, uuid
from datetime import datetime, timezone
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))
client = MongoClient(os.environ["MONGO_URL"])
db = client[os.environ["DB_NAME"]]

print("BEFORE:")
print("  massagistas:", db.massagistas.count_documents({}))
print("  bookings:", db.bookings.count_documents({}))
print("  profile_views:", db.profile_views.count_documents({}))

# 1. Wipe transactional data
print("\nDeleted bookings:", db.bookings.delete_many({}).deleted_count)
print("Deleted reviews:", db.reviews.delete_many({}).deleted_count)
print("Deleted whatsapp_clicks:", db.whatsapp_clicks.delete_many({}).deleted_count)
print("Deleted profile_views:", db.profile_views.delete_many({}).deleted_count)
print("Deleted payment_transactions:", db.payment_transactions.delete_many({}).deleted_count)

# 2. Delete all massagistas and create ONE test profile named "Lara"
db.massagistas.delete_many({})
lara = {
    "id": f"m_{uuid.uuid4().hex[:10]}",
    "name": "Lara (perfil teste)",
    "bairro": "Ipanema",
    "age": 28,
    "bio": "Perfil de teste. Edite ou remova antes do lancamento em producao.",
    "gender": "feminino",
    "phone_ddd": "21",
    "phone_number": "999999999",
    "main_image": "https://images.unsplash.com/photo-1544161515-4ab6ce6db874?w=1200&q=80",
    "gallery": [
        "https://images.unsplash.com/photo-1544161515-4ab6ce6db874?w=1200&q=80",
        "https://images.unsplash.com/photo-1540555700478-4be289fbecef?w=1200&q=80",
        "https://images.unsplash.com/photo-1519824145371-296894a0daa9?w=1200&q=80",
        "https://images.unsplash.com/photo-1600334129128-685c5582fd35?w=1200&q=80",
    ],
    "video_url": "",
    "video_thumb": "",
    "specialties": ["Relaxante", "Sueca", "Pedras quentes"],
    "languages": ["Portugues", "Ingles"],
    "price_60": 250, "price_90": 350, "price_120": 450,
    "lat": -22.9840, "lng": -43.1986,
    "rating": 0, "reviews": 0,
    "verified": True,
    "atendimento_domicilio": True,
    "owner_user_id": None,
    "created_at": datetime.now(timezone.utc).isoformat(),
}
db.massagistas.insert_one(lara)
print(f"\nCreated test profile: {lara['id']}  {lara['name']}")

print("\nAFTER:")
print("  massagistas:", db.massagistas.count_documents({}))
print("  bookings:", db.bookings.count_documents({}))
print("  profile_views:", db.profile_views.count_documents({}))
