"""Iteration 4 backend tests:
- Reviews (POST /api/bookings/{id}/review, GET /api/massagistas/{id}/reviews)
- Professional self-cadastro (/me/profile, /me/profile/photo, set-main, delete, video)
- Cache-Control on /api/files
"""
import io
import os
import uuid
import pytest
import requests
from datetime import datetime, timezone, timedelta

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "http://localhost:8001").rstrip("/")
ADMIN_TOKEN = os.environ.get("ADMIN_TOKEN", "test_admin_token_1781314522749")
NONADMIN_TOKEN = os.environ.get("NONADMIN_TOKEN", "test_nonadmin_token_1781314522758")

# Fixture "mongo" vem de conftest.py (shim sobre Postgres — nome mantido de propósito, ver conftest.py)


@pytest.fixture(scope="module")
def admin_user(mongo):
    s = mongo.user_sessions.find_one({"session_token": ADMIN_TOKEN})
    assert s, "admin session missing — refresh credentials"
    u = mongo.users.find_one({"user_id": s["user_id"]}, {"_id": 0})
    return u


@pytest.fixture(scope="module")
def nonadmin_user(mongo):
    s = mongo.user_sessions.find_one({"session_token": NONADMIN_TOKEN})
    assert s, "non-admin session missing"
    u = mongo.users.find_one({"user_id": s["user_id"]}, {"_id": 0})
    return u


def H(tok=None):
    h = {"Content-Type": "application/json"}
    if tok:
        h["Authorization"] = f"Bearer {tok}"
    return h


# ============================================================
# REVIEWS
# ============================================================
class TestReviews:
    def _insert_booking(self, mongo, user_id, mid, status="confirmed"):
        bid = f"b_test_{uuid.uuid4().hex[:8]}"
        mongo.bookings.insert_one({
            "id": bid, "user_id": user_id, "user_email": "qa@test",
            "massagista_id": mid, "massagista_name": "X",
            "massagista_image": "", "bairro": "Ipanema",
            "date": "2026-01-15", "time": "14:00", "duration": 60,
            "location_type": "studio", "amount": 300.0, "currency": "brl",
            "status": status, "created_at": datetime.now(timezone.utc).isoformat(),
        })
        return bid

    def test_review_requires_auth(self):
        r = requests.post(f"{BASE_URL}/api/bookings/anything/review",
                          headers=H(), json={"rating": 5})
        assert r.status_code == 401

    def test_review_unknown_booking_404(self):
        r = requests.post(f"{BASE_URL}/api/bookings/does_not_exist/review",
                          headers=H(NONADMIN_TOKEN), json={"rating": 5})
        assert r.status_code == 404

    def test_review_pending_booking_400(self, mongo, nonadmin_user):
        # massagista_id precisa existir de verdade (FK no Postgres — não existia sob Mongo)
        mid = mongo.massagistas.find_one({"id": {"$regex": "^m"}})["id"]
        bid = self._insert_booking(mongo, nonadmin_user["user_id"], mid, status="pending_payment")
        try:
            r = requests.post(f"{BASE_URL}/api/bookings/{bid}/review",
                              headers=H(NONADMIN_TOKEN), json={"rating": 5})
            assert r.status_code == 400
        finally:
            mongo.bookings.delete_one({"id": bid})

    def test_review_rating_bounds_422(self, mongo, nonadmin_user):
        mid = mongo.massagistas.find_one({"id": {"$regex": "^m"}})["id"]
        bid = self._insert_booking(mongo, nonadmin_user["user_id"], mid)
        try:
            r0 = requests.post(f"{BASE_URL}/api/bookings/{bid}/review",
                               headers=H(NONADMIN_TOKEN), json={"rating": 0})
            assert r0.status_code == 422
            r6 = requests.post(f"{BASE_URL}/api/bookings/{bid}/review",
                               headers=H(NONADMIN_TOKEN), json={"rating": 6})
            assert r6.status_code == 422
        finally:
            mongo.bookings.delete_one({"id": bid})

    def test_review_happy_path_and_aggregate(self, mongo, nonadmin_user):
        # pick a real seeded massagista
        m = mongo.massagistas.find_one({"id": {"$regex": "^m"}}, {"_id": 0})
        assert m
        mid = m["id"]
        old_count = int(m.get("reviews", 0))
        old_rating = float(m.get("rating", 0.0))
        bid = self._insert_booking(mongo, nonadmin_user["user_id"], mid)
        review_id = None
        try:
            r = requests.post(f"{BASE_URL}/api/bookings/{bid}/review",
                              headers=H(NONADMIN_TOKEN),
                              json={"rating": 5, "comment": "TEST_review excelente"})
            assert r.status_code == 200, r.text
            data = r.json()
            assert "id" in data and data["rating"] == 5
            assert data["comment"] == "TEST_review excelente"
            assert "user_name" in data
            review_id = data["id"]

            # duplicate -> 400
            r2 = requests.post(f"{BASE_URL}/api/bookings/{bid}/review",
                               headers=H(NONADMIN_TOKEN), json={"rating": 4})
            assert r2.status_code == 400

            # massagista aggregate updated
            m2 = mongo.massagistas.find_one({"id": mid}, {"_id": 0})
            assert m2["reviews"] == old_count + 1
            expected = round((old_rating * old_count + 5) / (old_count + 1), 2)
            assert abs(m2["rating"] - expected) < 0.01

            # GET /reviews
            rg = requests.get(f"{BASE_URL}/api/massagistas/{mid}/reviews")
            assert rg.status_code == 200
            lst = rg.json()
            assert any(x["id"] == review_id for x in lst)
        finally:
            # reviews antes de bookings — FK reviews.booking_id no Postgres
            # (Mongo não enforcement isso, então a ordem antiga não importava)
            if review_id:
                mongo.reviews.delete_one({"id": review_id})
                # rollback aggregate
                mongo.massagistas.update_one({"id": mid},
                                             {"$set": {"reviews": old_count, "rating": old_rating}})
            mongo.bookings.delete_one({"id": bid})


# ============================================================
# PROFESSIONAL SELF-CADASTRO
# ============================================================
@pytest.fixture
def fresh_pro_user(mongo):
    """Mint a one-off user + session that has no profile yet, and cleanup."""
    uid = f"user_protest_{uuid.uuid4().hex[:8]}"
    tok = f"test_pro_token_{uuid.uuid4().hex[:8]}"
    mongo.users.insert_one({
        "user_id": uid, "email": f"qa+pro+{uid}@test", "name": "Pro QA",
        "picture": "https://i.pravatar.cc/150?u=" + uid,
        "created_at": datetime.now(timezone.utc).isoformat(),
    })
    mongo.user_sessions.insert_one({
        "user_id": uid, "session_token": tok,
        "expires_at": (datetime.now(timezone.utc) + timedelta(days=1)).isoformat(),
        "created_at": datetime.now(timezone.utc).isoformat(),
    })
    yield {"user_id": uid, "token": tok}
    # cleanup
    mongo.massagistas.delete_many({"owner_user_id": uid})
    mongo.user_sessions.delete_many({"user_id": uid})
    mongo.users.delete_one({"user_id": uid})
    mongo.files.delete_many({"uploaded_by": f"qa+pro+{uid}@test"})


class TestProfile:
    def test_get_profile_requires_auth(self):
        r = requests.get(f"{BASE_URL}/api/me/profile")
        assert r.status_code == 401

    def test_get_profile_null_when_none(self, fresh_pro_user):
        r = requests.get(f"{BASE_URL}/api/me/profile",
                         headers=H(fresh_pro_user["token"]))
        assert r.status_code == 200
        assert r.json() == {"profile": None}

    def test_create_profile_invalid_bairro(self, fresh_pro_user):
        r = requests.post(f"{BASE_URL}/api/me/profile",
                          headers=H(fresh_pro_user["token"]),
                          json={
                              "name": "QA Pro",
                              "bairro_slug": "marte",
                              "bio": "Bio teste de QA com tamanho ok.",
                              "specialties": ["Relaxante"],
                              "price_60": 200, "experience_years": 3,
                              "languages": ["pt"],
                          })
        assert r.status_code == 400

    def test_create_then_dup_then_update(self, mongo, fresh_pro_user):
        tok = fresh_pro_user["token"]
        uid = fresh_pro_user["user_id"]
        payload = {
            "name": "QA Pro", "bairro_slug": "ipanema",
            "bio": "Bio teste com mais de 10 chars",
            "specialties": ["Relaxante", "Sueca"],
            "price_60": 300, "experience_years": 5, "languages": ["pt", "en"],
        }
        r = requests.post(f"{BASE_URL}/api/me/profile", headers=H(tok), json=payload)
        assert r.status_code == 200, r.text
        doc = r.json()
        assert doc["owner_user_id"] == uid
        assert doc["bairro"] == "Ipanema"
        assert doc["verified"] is False
        assert abs(doc["lat"] - (-22.9839)) < 0.01
        assert "id" in doc and doc["id"].startswith("m_")

        # GET shows it
        rg = requests.get(f"{BASE_URL}/api/me/profile", headers=H(tok))
        assert rg.json()["profile"]["id"] == doc["id"]

        # duplicate -> 400
        r2 = requests.post(f"{BASE_URL}/api/me/profile", headers=H(tok), json=payload)
        assert r2.status_code == 400

        # PUT partial update
        up = requests.put(f"{BASE_URL}/api/me/profile", headers=H(tok),
                          json={"bio": "Bio atualizada via QA test"})
        assert up.status_code == 200
        assert up.json()["bio"] == "Bio atualizada via QA test"
        assert up.json()["name"] == "QA Pro"  # unchanged

        # PUT invalid bairro -> 400
        up_bad = requests.put(f"{BASE_URL}/api/me/profile", headers=H(tok),
                              json={"bairro_slug": "neverland"})
        assert up_bad.status_code == 400


# ============================================================
# PROFESSIONAL MEDIA UPLOAD (owner scope)
# ============================================================
class TestProfileMedia:
    def _png_bytes(self):
        # 1x1 PNG
        return bytes.fromhex(
            "89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c489"
            "0000000a49444154789c63000100000500010d0a2db40000000049454e44ae426082"
        )

    def test_photo_endpoint_requires_auth(self):
        r = requests.post(f"{BASE_URL}/api/me/profile/photo",
                          files={"file": ("a.png", self._png_bytes(), "image/png")})
        assert r.status_code == 401

    def test_photo_no_profile_404(self, fresh_pro_user):
        r = requests.post(
            f"{BASE_URL}/api/me/profile/photo",
            headers={"Authorization": f"Bearer {fresh_pro_user['token']}"},
            files={"file": ("a.png", self._png_bytes(), "image/png")},
        )
        assert r.status_code == 404

    def test_full_media_flow(self, mongo, fresh_pro_user):
        tok = fresh_pro_user["token"]
        # create profile first
        cp = requests.post(f"{BASE_URL}/api/me/profile", headers=H(tok), json={
            "name": "QA Media", "bairro_slug": "leblon",
            "bio": "Bio QA media owner-scoped media tests",
            "specialties": ["Relaxante"], "price_60": 250,
            "experience_years": 2, "languages": ["pt"],
        })
        assert cp.status_code == 200, cp.text

        # upload photo
        up = requests.post(
            f"{BASE_URL}/api/me/profile/photo",
            headers={"Authorization": f"Bearer {tok}"},
            files={"file": ("a.png", self._png_bytes(), "image/png")},
        )
        assert up.status_code == 200, up.text
        url = up.json()["url"]
        assert "/api/files/" in url
        gallery = up.json()["massagista"]["gallery"]
        assert url in gallery

        # set-main with URL not in gallery -> 400
        bad = requests.post(f"{BASE_URL}/api/me/profile/set-main",
                            headers=H(tok), json={"url": "https://nope/x.jpg"})
        assert bad.status_code == 400

        # set-main happy
        sm = requests.post(f"{BASE_URL}/api/me/profile/set-main",
                           headers=H(tok), json={"url": url})
        assert sm.status_code == 200
        assert sm.json()["massagista"]["main_image"] == url

        # delete photo
        dl = requests.delete(f"{BASE_URL}/api/me/profile/photo",
                             headers=H(tok), json={"url": url})
        assert dl.status_code == 200
        assert url not in dl.json()["massagista"]["gallery"]
        # file record soft-deleted
        sp = url.split("/api/files/", 1)[1]
        f = mongo.files.find_one({"storage_path": sp})
        assert f and f.get("is_deleted") is True

        # video upload (tiny MP4 stub bytes)
        vid_bytes = b"\x00\x00\x00\x18ftypmp42" + b"\x00" * 100
        vu = requests.post(
            f"{BASE_URL}/api/me/profile/video",
            headers={"Authorization": f"Bearer {tok}"},
            files={"file": ("v.mp4", vid_bytes, "video/mp4")},
        )
        assert vu.status_code == 200, vu.text
        assert vu.json()["massagista"]["video_url"].startswith(BASE_URL) or \
               "/api/files/" in vu.json()["massagista"]["video_url"]


# ============================================================
# CACHE-CONTROL on /api/files
# ============================================================
class TestCacheControl:
    def test_cache_headers(self, mongo, fresh_pro_user):
        tok = fresh_pro_user["token"]
        # need a profile + uploaded file
        requests.post(f"{BASE_URL}/api/me/profile", headers=H(tok), json={
            "name": "QA Cache", "bairro_slug": "copacabana",
            "bio": "Bio QA cache controle",
            "specialties": ["Relaxante"], "price_60": 200,
            "experience_years": 1, "languages": ["pt"],
        })
        up = requests.post(
            f"{BASE_URL}/api/me/profile/photo",
            headers={"Authorization": f"Bearer {tok}"},
            files={"file": ("a.png", TestProfileMedia()._png_bytes(), "image/png")},
        )
        assert up.status_code == 200, up.text
        url = up.json()["url"]
        # /api/files/{path}
        full = url if url.startswith("http") else (BASE_URL + url)
        r = requests.get(full)
        assert r.status_code == 200
        cc = r.headers.get("Cache-Control", "")
        assert "max-age=86400" in cc and "immutable" in cc and "public" in cc, f"got: {cc!r}"
        assert r.headers.get("ETag"), "ETag missing"
