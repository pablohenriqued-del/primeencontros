"""End-to-end backend tests for Oásis Rio."""
import requests
import pytest


# ----- Public: health -----
class TestRoot:
    def test_root(self, base_url):
        r = requests.get(f"{base_url}/api/")
        assert r.status_code == 200
        data = r.json()
        assert data["status"] == "ok"


# ----- Public: bairros -----
class TestBairros:
    def test_list_bairros(self, base_url):
        r = requests.get(f"{base_url}/api/bairros")
        assert r.status_code == 200
        items = r.json()
        assert isinstance(items, list)
        assert len(items) == 12
        slugs = {b["slug"] for b in items}
        assert "ipanema" in slugs and "leblon" in slugs
        for b in items:
            assert isinstance(b["lat"], (int, float))
            assert isinstance(b["lng"], (int, float))


# ----- Public: massagistas -----
class TestMassagistas:
    def test_list_all(self, base_url):
        r = requests.get(f"{base_url}/api/massagistas")
        assert r.status_code == 200
        items = r.json()
        assert len(items) == 12
        for it in items:
            assert "id" in it and "price_60" in it and "price_90" in it and "price_120" in it
            assert "gallery" in it and "video_url" in it
            assert "_id" not in it  # Mongo _id must be excluded

    def test_filter_by_bairro(self, base_url):
        r = requests.get(f"{base_url}/api/massagistas", params={"bairro": "ipanema"})
        assert r.status_code == 200
        items = r.json()
        assert len(items) >= 1
        assert all(it["bairro_slug"] == "ipanema" for it in items)

    def test_search_specialty(self, base_url):
        r = requests.get(f"{base_url}/api/massagistas", params={"q": "Relaxante"})
        assert r.status_code == 200
        items = r.json()
        assert len(items) >= 1
        # All returned items should have specialty (case-insensitive) matching
        for it in items:
            text = " ".join(it["specialties"]).lower() + it["name"].lower() + it["bairro"].lower()
            assert "relaxante" in text

    def test_geo_sort(self, base_url):
        # Ipanema coords
        r = requests.get(f"{base_url}/api/massagistas",
                         params={"lat": -22.9839, "lng": -43.2045})
        assert r.status_code == 200
        items = r.json()
        assert len(items) == 12
        for it in items:
            assert "distance_km" in it
        dists = [it["distance_km"] for it in items]
        assert dists == sorted(dists)
        # Closest should be Ipanema
        assert items[0]["bairro_slug"] == "ipanema"

    def test_detail(self, base_url):
        r = requests.get(f"{base_url}/api/massagistas")
        first = r.json()[0]
        r2 = requests.get(f"{base_url}/api/massagistas/{first['id']}")
        assert r2.status_code == 200
        d = r2.json()
        assert d["id"] == first["id"]
        assert "gallery" in d and isinstance(d["gallery"], list)
        assert "video_url" in d
        assert "price_60" in d and "price_90" in d and "price_120" in d

    def test_detail_404(self, base_url):
        r = requests.get(f"{base_url}/api/massagistas/does-not-exist")
        assert r.status_code == 404


# ----- Auth -----
class TestAuth:
    def test_auth_me_no_token(self, base_url):
        r = requests.get(f"{base_url}/api/auth/me")
        assert r.status_code == 401

    def test_auth_me_with_token(self, auth_client, base_url, test_user):
        r = auth_client.get(f"{base_url}/api/auth/me")
        assert r.status_code == 200
        data = r.json()
        assert data["user_id"] == test_user["user_id"]
        assert data["email"] == test_user["email"]


# ----- Bookings -----
@pytest.fixture(scope="class")
def first_massagista(base_url):
    r = requests.get(f"{base_url}/api/massagistas")
    return r.json()[0]


class TestBookings:
    def test_create_booking_no_auth(self, base_url, first_massagista):
        r = requests.post(f"{base_url}/api/bookings", json={
            "massagista_id": first_massagista["id"],
            "date": "2026-02-15", "time": "10:00",
            "duration": 60, "location_type": "studio",
        })
        assert r.status_code == 401

    def test_create_booking_home_no_address(self, auth_client, base_url, first_massagista):
        r = auth_client.post(f"{base_url}/api/bookings", json={
            "massagista_id": first_massagista["id"],
            "date": "2026-02-15", "time": "10:00",
            "duration": 60, "location_type": "home",
        })
        assert r.status_code == 400

    def test_create_booking_invalid_duration(self, auth_client, base_url, first_massagista):
        r = auth_client.post(f"{base_url}/api/bookings", json={
            "massagista_id": first_massagista["id"],
            "date": "2026-02-15", "time": "10:00",
            "duration": 45, "location_type": "studio",
        })
        assert r.status_code == 400

    def test_create_booking_invalid_location(self, auth_client, base_url, first_massagista):
        r = auth_client.post(f"{base_url}/api/bookings", json={
            "massagista_id": first_massagista["id"],
            "date": "2026-02-15", "time": "10:00",
            "duration": 60, "location_type": "park",
        })
        assert r.status_code == 400

    def test_create_booking_unknown_massagista(self, auth_client, base_url):
        r = auth_client.post(f"{base_url}/api/bookings", json={
            "massagista_id": "m_unknown_xx",
            "date": "2026-02-15", "time": "10:00",
            "duration": 60, "location_type": "studio",
        })
        assert r.status_code == 404

    def test_create_booking_studio_60(self, auth_client, base_url, first_massagista, test_user):
        r = auth_client.post(f"{base_url}/api/bookings", json={
            "massagista_id": first_massagista["id"],
            "date": "2026-02-20", "time": "14:00",
            "duration": 60, "location_type": "studio",
            "notes": "Test booking",
        })
        assert r.status_code == 200, r.text
        b = r.json()
        assert b["status"] == "pending_payment"
        assert b["user_id"] == test_user["user_id"]
        assert b["amount"] == first_massagista["price_60"]
        assert b["currency"] == "brl"
        assert b["duration"] == 60
        pytest.shared_booking_id = b["id"]

    def test_create_booking_home_90(self, auth_client, base_url, first_massagista):
        r = auth_client.post(f"{base_url}/api/bookings", json={
            "massagista_id": first_massagista["id"],
            "date": "2026-02-21", "time": "16:00",
            "duration": 90, "location_type": "home",
            "address": "Rua Exemplo 100, Ipanema",
        })
        assert r.status_code == 200
        b = r.json()
        assert b["amount"] == first_massagista["price_90"]
        assert b["location_type"] == "home"

    def test_list_my_bookings(self, auth_client, base_url):
        r = auth_client.get(f"{base_url}/api/bookings/me")
        assert r.status_code == 200
        items = r.json()
        assert isinstance(items, list)
        assert len(items) >= 2

    def test_list_my_bookings_no_auth(self, base_url):
        r = requests.get(f"{base_url}/api/bookings/me")
        assert r.status_code == 401


# ----- Checkout / Stripe -----
class TestCheckout:
    def test_create_checkout_session(self, auth_client, base_url, first_massagista):
        # Create a fresh booking
        rb = auth_client.post(f"{base_url}/api/bookings", json={
            "massagista_id": first_massagista["id"],
            "date": "2026-03-01", "time": "11:00",
            "duration": 60, "location_type": "studio",
        })
        assert rb.status_code == 200
        booking = rb.json()
        r = auth_client.post(f"{base_url}/api/checkout/session", json={
            "booking_id": booking["id"],
            "origin_url": "https://example.com",
        })
        assert r.status_code == 200, r.text
        data = r.json()
        assert "url" in data and data["url"].startswith("http")
        assert "session_id" in data and data["session_id"]
        pytest.shared_session_id = data["session_id"]
        pytest.shared_booking_id_for_checkout = booking["id"]

    def test_checkout_no_auth(self, base_url):
        r = requests.post(f"{base_url}/api/checkout/session", json={
            "booking_id": "any", "origin_url": "https://example.com",
        })
        assert r.status_code == 401

    def test_checkout_status(self, auth_client, base_url, mongo_db):
        sid = getattr(pytest, "shared_session_id", None)
        assert sid, "session_id missing"
        r = auth_client.get(f"{base_url}/api/checkout/status/{sid}")
        assert r.status_code == 200, r.text
        data = r.json()
        assert "status" in data and "payment_status" in data
        # In test mode Stripe payment_status will likely be 'unpaid' -> booking should remain pending
        tx = mongo_db.payment_transactions.find_one({"session_id": sid})
        assert tx is not None
        assert tx["payment_status"] in ("paid", "unpaid", "pending", "no_payment_required")

    def test_checkout_status_idempotent(self, auth_client, base_url, mongo_db):
        sid = pytest.shared_session_id
        # Force the booking to "confirmed" + tx paid to simulate already-paid scenario
        bid = pytest.shared_booking_id_for_checkout
        mongo_db.bookings.update_one({"id": bid}, {"$set": {"status": "confirmed"}})
        r = auth_client.get(f"{base_url}/api/checkout/status/{sid}")
        assert r.status_code == 200
        # Booking must still be 'confirmed' (no toggle/regression)
        b = mongo_db.bookings.find_one({"id": bid})
        assert b["status"] == "confirmed"

    def test_checkout_status_unknown(self, auth_client, base_url):
        r = auth_client.get(f"{base_url}/api/checkout/status/cs_unknown_xxxxxxxx")
        assert r.status_code == 404


# ----- Logout -----
class TestLogout:
    def test_logout_with_bearer(self, mongo_db, base_url):
        # Create a separate session for logout test so we don't kill the main test_user session
        from datetime import datetime, timezone, timedelta
        import secrets, time
        uid = f"user_logout_{secrets.token_hex(4)}"
        tok = f"test_token_logout_{int(time.time()*1000)}"
        mongo_db.users.insert_one({"user_id": uid, "email": "lo@x.test", "name": "L", "picture": "", "created_at": "2026-01-01"})
        mongo_db.user_sessions.insert_one({
            "user_id": uid, "session_token": tok,
            "expires_at": (datetime.now(timezone.utc) + timedelta(days=1)).isoformat(),
            "created_at": datetime.now(timezone.utc).isoformat(),
        })
        # NOTE: backend's auth_logout only reads session_token from Cookie, not Authorization header.
        # So passing the token as a cookie is required for actual deletion.
        r = requests.post(f"{base_url}/api/auth/logout", cookies={"session_token": tok})
        assert r.status_code == 200
        assert mongo_db.user_sessions.find_one({"session_token": tok}) is None
        # Cleanup
        mongo_db.users.delete_one({"user_id": uid})
