"""Verification flow tests: public + admin endpoints."""
import os
import requests
import pytest

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "http://localhost:8001").rstrip("/")
ADMIN_TOKEN = os.environ.get("ADMIN_TOKEN", "test_admin_token_1781314522749")
NONADMIN_TOKEN = os.environ.get("NONADMIN_TOKEN", "test_nonadmin_token_1781314522758")


@pytest.fixture(scope="module")
def admin_h():
    return {"Authorization": f"Bearer {ADMIN_TOKEN}"}


@pytest.fixture(scope="module")
def user_h():
    return {"Authorization": f"Bearer {NONADMIN_TOKEN}"}


# --- Public listing -------------------------------------------------------
class TestPublicListing:
    def test_list_all_count(self):
        r = requests.get(f"{BASE_URL}/api/massagistas")
        assert r.status_code == 200
        data = r.json()
        assert len(data) == 12
        # Verified first sort
        verified_top = [m["verified"] for m in data[:8]]
        assert all(verified_top), f"Top 8 should be verified, got {verified_top}"

    def test_verified_only_filter(self):
        r = requests.get(f"{BASE_URL}/api/massagistas", params={"verified_only": "true"})
        assert r.status_code == 200
        data = r.json()
        assert len(data) == 8
        assert all(m["verified"] for m in data)

    def test_detail_has_verification(self):
        r = requests.get(f"{BASE_URL}/api/massagistas")
        mid = r.json()[0]["id"]
        d = requests.get(f"{BASE_URL}/api/massagistas/{mid}").json()
        assert "verified" in d and isinstance(d["verified"], bool)
        v = d.get("verification")
        assert v is not None
        for k in ("status", "id_check", "photo_check", "address_check", "verified_at", "verified_by"):
            assert k in v


# --- Admin auth -----------------------------------------------------------
class TestAdminAuth:
    def test_queue_no_auth_401(self):
        r = requests.get(f"{BASE_URL}/api/admin/verification/queue")
        assert r.status_code == 401

    def test_queue_non_admin_403(self, user_h):
        r = requests.get(f"{BASE_URL}/api/admin/verification/queue", headers=user_h)
        assert r.status_code == 403

    def test_queue_admin_200(self, admin_h):
        r = requests.get(f"{BASE_URL}/api/admin/verification/queue", headers=admin_h)
        assert r.status_code == 200
        data = r.json()
        assert len(data) == 4
        assert all(not m.get("verified", False) for m in data)

    def test_all_admin(self, admin_h):
        r = requests.get(f"{BASE_URL}/api/admin/verification/all", headers=admin_h)
        assert r.status_code == 200
        assert len(r.json()) == 12


# --- Admin moderation actions --------------------------------------------
class TestModeration:
    def _pick_unverified(self, admin_h):
        r = requests.get(f"{BASE_URL}/api/admin/verification/queue", headers=admin_h)
        return r.json()[0]["id"]

    def _pick_verified(self, admin_h):
        r = requests.get(f"{BASE_URL}/api/admin/verification/all", headers=admin_h)
        return next(m for m in r.json() if m.get("verified"))["id"]

    def test_approve_flips_verified(self, admin_h):
        mid = self._pick_unverified(admin_h)
        r = requests.post(
            f"{BASE_URL}/api/admin/verification/{mid}/approve",
            headers=admin_h,
            json={"id_check": True, "photo_check": True, "address_check": True, "notes": "OK"},
        )
        assert r.status_code == 200
        # Verify persisted
        d = requests.get(f"{BASE_URL}/api/massagistas/{mid}").json()
        assert d["verified"] is True
        assert d["verification"]["status"] == "verified"
        assert d["verification"]["verified_by"]
        assert d["verification"]["verified_at"]
        # cleanup: revoke to keep distribution
        requests.post(f"{BASE_URL}/api/admin/verification/{mid}/revoke", headers=admin_h)

    def test_reject_sets_rejected(self, admin_h):
        mid = self._pick_unverified(admin_h)
        r = requests.post(
            f"{BASE_URL}/api/admin/verification/{mid}/reject",
            headers=admin_h,
            json={"id_check": False, "photo_check": True, "address_check": True, "notes": "doc invalid"},
        )
        assert r.status_code == 200
        d = requests.get(f"{BASE_URL}/api/massagistas/{mid}").json()
        assert d["verified"] is False
        assert d["verification"]["status"] == "rejected"

    def test_revoke_an_already_verified(self, admin_h):
        mid = self._pick_verified(admin_h)
        r = requests.post(f"{BASE_URL}/api/admin/verification/{mid}/revoke", headers=admin_h)
        assert r.status_code == 200
        d = requests.get(f"{BASE_URL}/api/massagistas/{mid}").json()
        assert d["verified"] is False
        assert d["verification"]["status"] == "pending"
        # restore: approve back
        requests.post(
            f"{BASE_URL}/api/admin/verification/{mid}/approve",
            headers=admin_h,
            json={"id_check": True, "photo_check": True, "address_check": True, "notes": "restored"},
        )

    def test_approve_requires_admin(self, user_h):
        # Need a valid id but non-admin user must get 403
        any_id = requests.get(f"{BASE_URL}/api/massagistas").json()[0]["id"]
        r = requests.post(
            f"{BASE_URL}/api/admin/verification/{any_id}/approve",
            headers=user_h,
            json={"id_check": True, "photo_check": True, "address_check": True, "notes": ""},
        )
        assert r.status_code == 403

    def test_approve_404_for_unknown(self, admin_h):
        r = requests.post(
            f"{BASE_URL}/api/admin/verification/m_doesnotexist/approve",
            headers=admin_h,
            json={"id_check": True, "photo_check": True, "address_check": True},
        )
        assert r.status_code == 404
