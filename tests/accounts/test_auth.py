"""Tests for /api/v1/auth — login, refresh, logout, /me.

JWT claims are checked against accounts/serializers.py:LoginSerializer
(role, email, full_name embedded in the access token).
"""
import pytest
from rest_framework_simplejwt.tokens import RefreshToken, AccessToken

from apps.accounts.models import CustomUser

pytestmark = pytest.mark.django_db

LOGIN_URL = "/api/v1/auth/login"
REFRESH_URL = "/api/v1/auth/refresh"
LOGOUT_URL = "/api/v1/auth/logout"
ME_URL = "/api/v1/auth/me"


# ---------------------------------------------------------------------------
# Login
# ---------------------------------------------------------------------------
def test_login_returns_access_refresh_and_user(api, admin_user):
    resp = api.post(LOGIN_URL, {"email": admin_user.email, "password": "Test12345!"},
                    format="json")
    assert resp.status_code == 200, resp.data
    body = resp.json()
    assert {"access", "refresh", "user"} <= set(body.keys())
    assert body["user"]["email"] == admin_user.email
    assert body["user"]["role"] == "ADMIN"


def test_login_access_token_contains_role_email_full_name_claims(api, admin_user):
    """LoginSerializer.get_token adds role/email/full_name to the JWT payload
    (apps/accounts/serializers.py)."""
    resp = api.post(LOGIN_URL, {"email": admin_user.email, "password": "Test12345!"},
                    format="json")
    assert resp.status_code == 200
    access = AccessToken(resp.json()["access"])
    assert access["role"] == "ADMIN"
    assert access["email"] == admin_user.email
    assert access["full_name"] == admin_user.full_name


@pytest.mark.parametrize("role", ["ADMIN", "MANAGER", "CONTROLLER", "MAINTENANCE", "OPERATOR"])
def test_login_works_for_every_role(api, make_user, role):
    user = make_user(role)
    resp = api.post(LOGIN_URL, {"email": user.email, "password": "Test12345!"}, format="json")
    assert resp.status_code == 200
    assert resp.json()["user"]["role"] == role


def test_login_wrong_password_401(api, admin_user):
    resp = api.post(LOGIN_URL, {"email": admin_user.email, "password": "wrong"}, format="json")
    assert resp.status_code == 401


def test_login_unknown_email_401(api):
    resp = api.post(LOGIN_URL, {"email": "nobody@isbm.local", "password": "Test12345!"}, format="json")
    assert resp.status_code == 401


def test_login_inactive_user_401(api, admin_user):
    admin_user.is_active = False
    admin_user.save()
    resp = api.post(LOGIN_URL, {"email": admin_user.email, "password": "Test12345!"}, format="json")
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# Refresh
# ---------------------------------------------------------------------------
def test_refresh_returns_new_access(api, admin_user):
    login = api.post(LOGIN_URL, {"email": admin_user.email, "password": "Test12345!"},
                     format="json")
    refresh = login.json()["refresh"]

    resp = api.post(REFRESH_URL, {"refresh": refresh}, format="json")
    assert resp.status_code == 200
    assert "access" in resp.json()


def test_refresh_with_garbage_token_401(api):
    resp = api.post(REFRESH_URL, {"refresh": "not-a-token"}, format="json")
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# Logout
# ---------------------------------------------------------------------------
def test_logout_returns_205(api, admin_user):
    login = api.post(LOGIN_URL, {"email": admin_user.email, "password": "Test12345!"},
                     format="json")
    # Auth + body required by the view.
    api.credentials(HTTP_AUTHORIZATION=f"Bearer {login.json()['access']}")
    resp = api.post(LOGOUT_URL, {"refresh": login.json()["refresh"]}, format="json")
    assert resp.status_code == 205


def test_logout_unauthenticated_401(api):
    resp = api.post(LOGOUT_URL, {"refresh": "anything"}, format="json")
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# /me
# ---------------------------------------------------------------------------
def test_me_get_returns_self(controller_client, controller_user):
    resp = controller_client.get(ME_URL)
    assert resp.status_code == 200
    body = resp.json()
    assert body["email"] == controller_user.email
    assert body["role"] == "CONTROLLER"


def test_me_patch_updates_allowed_fields(controller_client, controller_user):
    resp = controller_client.patch(ME_URL, {
        "phone": "+216 71 000 000",
        "shift": "NIGHT",
        "is_on_duty": False,
    }, format="json")
    assert resp.status_code == 200
    controller_user.refresh_from_db()
    assert controller_user.phone == "+216 71 000 000"
    assert controller_user.shift == "NIGHT"
    assert controller_user.is_on_duty is False


def test_me_patch_role_is_read_only(controller_client):
    """MeSerializer.read_only_fields includes role (serializers.py:48-52)."""
    resp = controller_client.patch(ME_URL, {"role": "ADMIN"}, format="json")
    assert resp.status_code == 200
    # role must NOT have changed
    me = controller_client.get(ME_URL).json()
    assert me["role"] == "CONTROLLER"


def test_me_patch_email_is_read_only(controller_client, controller_user):
    original = controller_user.email
    resp = controller_client.patch(ME_URL, {"email": "hijack@isbm.local"}, format="json")
    assert resp.status_code == 200
    controller_user.refresh_from_db()
    assert controller_user.email == original  # ignored


def test_me_unauthenticated_401(api):
    assert api.get(ME_URL).status_code == 401
