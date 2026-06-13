"""Media endpoints + female-seed + verified_only regression tests."""
import io
import os
import pytest
import requests
from PIL import Image

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://stupefied-gauss-5.preview.emergentagent.com").rstrip("/")
ADMIN_TOKEN = os.environ.get("ADMIN_TOKEN", "test_admin_token_1781314522749")
NONADMIN_TOKEN = os.environ.get("NONADMIN_TOKEN", "test_nonadmin_token_1781314522758")

FEMALE_FIRST_NAMES = {"Camila", "Mariana", "Larissa", "Beatriz", "Júlia",
                     "Isabela", "Clara", "Fernanda", "Letícia", "Patrícia",
                     "Tatiane", "Renata"}
MALE_FIRST_NAMES = {"Rafael", "Luís", "André", "Gustavo", "Diego"}


@pytest.fixture(scope="module")
def admin_h():
    return {"Authorization": f"Bearer {ADMIN_TOKEN}"}


@pytest.fixture(scope="module")
def user_h():
    return {"Authorization": f"Bearer {NONADMIN_TOKEN}"}


def _jpeg_bytes(size=(80, 80), color=(255, 0, 0)) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", size, color).save(buf, format="JPEG", quality=80)
    return buf.getvalue()


def _mp4_bytes() -> bytes:
    # Minimal-ish bytes labeled as mp4 — backend only checks Content-Type.
    return b"\x00\x00\x00\x18ftypmp42" + b"\x00" * 64


# --- Seed: female-only roster ---------------------------------------------
class TestFemaleSeed:
    def test_count_12(self):
        r = requests.get(f"{BASE_URL}/api/massagistas")
        assert r.status_code == 200
        data = r.json()
        assert len(data) == 12

    def test_all_female_no_male(self):
        data = requests.get(f"{BASE_URL}/api/massagistas").json()
        first_names = {m["name"].split()[0] for m in data}
        # All seeded names must be in FEMALE_FIRST_NAMES
        unknown = first_names - FEMALE_FIRST_NAMES
        assert not unknown, f"Unexpected first names (must be female): {unknown}"
        # And none of the old male names should appear
        leaks = first_names & MALE_FIRST_NAMES
        assert not leaks, f"Male names leaked into seed: {leaks}"

    def test_portrait_source_randomuser(self):
        data = requests.get(f"{BASE_URL}/api/massagistas").json()
        women_portraits = [m["main_image"] for m in data
                          if "randomuser.me/api/portraits/women/" in m["main_image"]]
        # All 12 main_images should be from randomuser women endpoint (until admin uploads)
        assert len(women_portraits) == 12, f"Expected 12 women portraits, got {len(women_portraits)}"


# --- Regression: verified_only=true ---------------------------------------
class TestVerifiedOnlyRegression:
    def test_verified_only_true_returns_8(self):
        r = requests.get(f"{BASE_URL}/api/massagistas", params={"verified_only": "true"})
        assert r.status_code == 200
        data = r.json()
        assert len(data) == 8
        assert all(m["verified"] for m in data)

    def test_no_filter_returns_12(self):
        r = requests.get(f"{BASE_URL}/api/massagistas")
        assert len(r.json()) == 12


# --- /api/files/{path} ----------------------------------------------------
class TestFileServing:
    def test_nonexistent_404(self):
        r = requests.get(f"{BASE_URL}/api/files/prime-encontros/nope/zzz.jpg")
        assert r.status_code == 404


# --- Photo upload auth ----------------------------------------------------
class TestPhotoUploadAuth:
    @pytest.fixture(scope="class")
    def mid(self):
        return requests.get(f"{BASE_URL}/api/massagistas").json()[0]["id"]

    def test_no_auth_401(self, mid):
        files = {"file": ("a.jpg", _jpeg_bytes(), "image/jpeg")}
        r = requests.post(f"{BASE_URL}/api/admin/massagistas/{mid}/photo", files=files)
        assert r.status_code == 401

    def test_non_admin_403(self, mid, user_h):
        files = {"file": ("a.jpg", _jpeg_bytes(), "image/jpeg")}
        r = requests.post(f"{BASE_URL}/api/admin/massagistas/{mid}/photo",
                          files=files, headers=user_h)
        assert r.status_code == 403

    def test_bad_content_type_400(self, mid, admin_h):
        files = {"file": ("a.txt", b"not an image", "text/plain")}
        r = requests.post(f"{BASE_URL}/api/admin/massagistas/{mid}/photo",
                          files=files, headers=admin_h)
        assert r.status_code == 400

    def test_unknown_massagista_404(self, admin_h):
        files = {"file": ("a.jpg", _jpeg_bytes(), "image/jpeg")}
        r = requests.post(f"{BASE_URL}/api/admin/massagistas/m_doesnotexist/photo",
                          files=files, headers=admin_h)
        assert r.status_code == 404


# --- Full photo lifecycle: upload → fetch → set-main → delete -------------
class TestPhotoLifecycle:
    def test_full_flow(self, admin_h):
        # Pick a stable massagista (last in list to avoid sort churn)
        all_m = requests.get(f"{BASE_URL}/api/massagistas").json()
        mid = all_m[-1]["id"]
        original_main = all_m[-1]["main_image"]

        # 1. UPLOAD
        files = {"file": ("test.jpg", _jpeg_bytes(color=(0, 200, 50)), "image/jpeg")}
        r = requests.post(f"{BASE_URL}/api/admin/massagistas/{mid}/photo",
                          files=files, headers=admin_h)
        assert r.status_code == 200, r.text
        body = r.json()
        assert "url" in body and "massagista" in body
        url = body["url"]
        assert url.startswith("/api/files/prime-encontros/massagistas/")
        assert url in body["massagista"]["gallery"]

        # 2. FETCH bytes back
        full = f"{BASE_URL}{url}"
        rf = requests.get(full)
        assert rf.status_code == 200
        assert rf.headers.get("Content-Type", "").startswith("image/jpeg")
        assert len(rf.content) > 100

        # 3. SET-MAIN to the uploaded url
        rs = requests.post(f"{BASE_URL}/api/admin/massagistas/{mid}/set-main",
                           headers=admin_h, json={"url": url})
        assert rs.status_code == 200, rs.text
        assert rs.json()["massagista"]["main_image"] == url

        # 3b. SET-MAIN with url NOT in gallery -> 400
        rs_bad = requests.post(f"{BASE_URL}/api/admin/massagistas/{mid}/set-main",
                               headers=admin_h, json={"url": "/api/files/bogus/x.jpg"})
        assert rs_bad.status_code == 400

        # 4. DELETE photo
        rd = requests.delete(f"{BASE_URL}/api/admin/massagistas/{mid}/photo",
                             headers=admin_h, json={"url": url})
        assert rd.status_code == 200, rd.text
        fresh = rd.json()["massagista"]
        assert url not in fresh["gallery"]
        # main_image should have fallen back (no longer the deleted url)
        assert fresh["main_image"] != url

        # 5. Fetching deleted file -> 404 (soft-deleted)
        rf2 = requests.get(full)
        assert rf2.status_code == 404

        # Restore original main if it was in gallery
        if original_main in fresh["gallery"]:
            requests.post(f"{BASE_URL}/api/admin/massagistas/{mid}/set-main",
                          headers=admin_h, json={"url": original_main})


# --- Video upload ---------------------------------------------------------
class TestVideoUpload:
    def test_bad_content_type_400(self, admin_h):
        mid = requests.get(f"{BASE_URL}/api/massagistas").json()[0]["id"]
        files = {"file": ("a.txt", b"not video", "text/plain")}
        r = requests.post(f"{BASE_URL}/api/admin/massagistas/{mid}/video",
                          files=files, headers=admin_h)
        assert r.status_code == 400

    def test_no_auth_401(self):
        mid = requests.get(f"{BASE_URL}/api/massagistas").json()[0]["id"]
        files = {"file": ("a.mp4", _mp4_bytes(), "video/mp4")}
        r = requests.post(f"{BASE_URL}/api/admin/massagistas/{mid}/video", files=files)
        assert r.status_code == 401

    def test_video_upload_replaces_url(self, admin_h):
        # Use last massagista to avoid sort movement
        mid = requests.get(f"{BASE_URL}/api/massagistas").json()[-1]["id"]
        files = {"file": ("v.mp4", _mp4_bytes(), "video/mp4")}
        r = requests.post(f"{BASE_URL}/api/admin/massagistas/{mid}/video",
                          files=files, headers=admin_h)
        assert r.status_code == 200, r.text
        body = r.json()
        new_url = body["url"]
        assert new_url.startswith("/api/files/prime-encontros/massagistas/")
        assert body["massagista"]["video_url"] == new_url
