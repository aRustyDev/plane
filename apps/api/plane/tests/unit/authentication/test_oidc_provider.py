# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.
#
# woven: Unit tests for the generic OIDC SSO provider (plane-07r). These are pure-Python
# unit tests — they mock the config lookup and the provider's HTTP calls, so no database
# or live IdP is required. Acceptance for plane-07r: token + userinfo parse correctly and
# an unverified email is rejected.

import datetime

import pytest
from django.test import RequestFactory

from plane.authentication.adapter.error import (
    AUTHENTICATION_ERROR_CODES,
    AuthenticationException,
)
from plane.authentication.provider.oauth import oidc as oidc_module
from plane.authentication.provider.oauth.oidc import OIDCOAuthProvider

pytestmark = pytest.mark.unit


# --- config the provider reads (order matches OIDCOAuthProvider.__init__) ----------------
CLIENT_ID = "oidc-client-id"
CLIENT_SECRET = "oidc-client-secret"
AUTHORIZATION_URL = "https://id.auth.woven/oauth/v2/authorize"
TOKEN_URL = "https://id.auth.woven/oauth/v2/token"
USERINFO_URL = "https://id.auth.woven/oidc/v1/userinfo"

# Fully-configured provider using the three explicit OIDC_URL_* endpoints (no discovery).
EXPLICIT_CONFIG = (
    CLIENT_ID,
    CLIENT_SECRET,
    AUTHORIZATION_URL,
    TOKEN_URL,
    USERINFO_URL,
    None,  # OIDC_URL_ENDPOINT (discovery) unused when explicit URLs are present
)


class FakeResponse:
    """Minimal stand-in for a `requests.Response`."""

    def __init__(self, json_data):
        self._json = json_data

    def raise_for_status(self):
        return None

    def json(self):
        return self._json


def _patch_config(monkeypatch, config):
    monkeypatch.setattr(oidc_module, "get_configuration_value", lambda keys: config)


def _make_provider(monkeypatch, config=EXPLICIT_CONFIG, code="auth-code", state="state-xyz"):
    _patch_config(monkeypatch, config)
    request = RequestFactory().get("/auth/oidc/")
    return OIDCOAuthProvider(request=request, code=code, state=state)


# --- construction / wiring ---------------------------------------------------------------


def test_provider_identity_and_scope(monkeypatch):
    provider = _make_provider(monkeypatch)
    assert provider.provider == "oidc"
    # OIDC flow must request the openid scope plus the claims we map.
    assert "openid" in provider.scope
    assert "email" in provider.scope


def test_authorize_url_and_redirect_built_from_config(monkeypatch):
    provider = _make_provider(monkeypatch)
    auth_url = provider.get_auth_url()
    assert auth_url.startswith(f"{AUTHORIZATION_URL}?")
    assert "response_type=code" in auth_url
    assert "state=state-xyz" in auth_url
    assert f"client_id={CLIENT_ID}" in auth_url
    # redirect_uri is derived from the request host and points at the oidc callback.
    assert provider.redirect_uri == "http://testserver/auth/oidc/callback/"
    assert "auth%2Foidc%2Fcallback" in auth_url


def test_error_code_maps_to_oidc(monkeypatch):
    # Exercises the `# woven:` branch added to OauthAdapter.authentication_error_code().
    provider = _make_provider(monkeypatch)
    assert provider.authentication_error_code() == "OIDC_OAUTH_PROVIDER_ERROR"


def test_missing_client_credentials_raises_not_configured(monkeypatch):
    config = (None, None, AUTHORIZATION_URL, TOKEN_URL, USERINFO_URL, None)
    _patch_config(monkeypatch, config)
    request = RequestFactory().get("/auth/oidc/")
    with pytest.raises(AuthenticationException) as exc:
        OIDCOAuthProvider(request=request)
    assert exc.value.error_code == AUTHENTICATION_ERROR_CODES["OIDC_NOT_CONFIGURED"]


def test_missing_endpoints_without_discovery_raises_not_configured(monkeypatch):
    # Credentials present but no endpoints and no discovery URL -> not usable.
    config = (CLIENT_ID, CLIENT_SECRET, None, None, None, None)
    _patch_config(monkeypatch, config)
    request = RequestFactory().get("/auth/oidc/")
    with pytest.raises(AuthenticationException) as exc:
        OIDCOAuthProvider(request=request)
    assert exc.value.error_code == AUTHENTICATION_ERROR_CODES["OIDC_NOT_CONFIGURED"]


def test_non_http_endpoint_rejected(monkeypatch):
    config = (CLIENT_ID, CLIENT_SECRET, "ftp://idp/authorize", TOKEN_URL, USERINFO_URL, None)
    _patch_config(monkeypatch, config)
    request = RequestFactory().get("/auth/oidc/")
    with pytest.raises(AuthenticationException) as exc:
        OIDCOAuthProvider(request=request)
    assert exc.value.error_code == AUTHENTICATION_ERROR_CODES["OIDC_NOT_CONFIGURED"]


# --- discovery ---------------------------------------------------------------------------


def test_endpoints_derived_from_discovery_document(monkeypatch):
    # No explicit URLs; only the issuer endpoint is configured -> discover the rest.
    config = (CLIENT_ID, CLIENT_SECRET, None, None, None, "https://id.auth.woven")
    discovery_doc = {
        "authorization_endpoint": AUTHORIZATION_URL,
        "token_endpoint": TOKEN_URL,
        "userinfo_endpoint": USERINFO_URL,
    }
    captured = {}

    def fake_get(url, headers=None, timeout=None):
        captured["url"] = url
        return FakeResponse(discovery_doc)

    _patch_config(monkeypatch, config)
    monkeypatch.setattr(oidc_module.requests, "get", fake_get)

    request = RequestFactory().get("/auth/oidc/")
    provider = OIDCOAuthProvider(request=request, state="s")

    # Issuer base gets the well-known suffix appended.
    assert captured["url"] == "https://id.auth.woven/.well-known/openid-configuration"
    assert provider.token_url == TOKEN_URL
    assert provider.userinfo_url == USERINFO_URL
    assert provider.get_auth_url().startswith(f"{AUTHORIZATION_URL}?")


def test_discovery_failure_raises_not_configured(monkeypatch):
    import requests as real_requests

    config = (CLIENT_ID, CLIENT_SECRET, None, None, None, "https://id.auth.woven")

    def boom(url, headers=None, timeout=None):
        raise real_requests.RequestException("unreachable")

    _patch_config(monkeypatch, config)
    monkeypatch.setattr(oidc_module.requests, "get", boom)

    request = RequestFactory().get("/auth/oidc/")
    with pytest.raises(AuthenticationException) as exc:
        OIDCOAuthProvider(request=request)
    assert exc.value.error_code == AUTHENTICATION_ERROR_CODES["OIDC_NOT_CONFIGURED"]


# --- token parse (acceptance) ------------------------------------------------------------


def test_set_token_data_parses_token_response(monkeypatch):
    provider = _make_provider(monkeypatch)

    token_json = {
        "access_token": "access-123",
        "refresh_token": "refresh-456",
        "expires_in": 3600,
        "id_token": "id-token-jwt",
    }
    captured = {}

    def fake_post(url, data=None, headers=None):
        captured["url"] = url
        captured["data"] = data
        return FakeResponse(token_json)

    # get_user_token lives on the base OauthAdapter (adapter/oauth.py).
    monkeypatch.setattr(
        "plane.authentication.adapter.oauth.requests.post", fake_post
    )

    provider.set_token_data()

    assert captured["url"] == TOKEN_URL
    assert captured["data"]["grant_type"] == "authorization_code"
    assert captured["data"]["code"] == "auth-code"
    assert provider.token_data["access_token"] == "access-123"
    assert provider.token_data["refresh_token"] == "refresh-456"
    assert provider.token_data["id_token"] == "id-token-jwt"
    # expires_in is a lifetime (seconds from now), not an epoch timestamp.
    expiry = provider.token_data["access_token_expired_at"]
    assert isinstance(expiry, datetime.datetime)
    assert expiry > datetime.datetime.now(tz=expiry.tzinfo)


def test_set_token_data_handles_missing_optional_fields(monkeypatch):
    provider = _make_provider(monkeypatch)
    monkeypatch.setattr(
        "plane.authentication.adapter.oauth.requests.post",
        lambda url, data=None, headers=None: FakeResponse({"access_token": "only-access"}),
    )
    provider.set_token_data()
    assert provider.token_data["access_token"] == "only-access"
    assert provider.token_data["refresh_token"] is None
    assert provider.token_data["access_token_expired_at"] is None
    assert provider.token_data["id_token"] == ""


# --- userinfo parse + verified-email guard (acceptance) ----------------------------------


def _patch_userinfo(monkeypatch, userinfo_json):
    monkeypatch.setattr(
        "plane.authentication.adapter.oauth.requests.get",
        lambda url, headers=None: FakeResponse(userinfo_json),
    )


def test_set_user_data_parses_verified_userinfo(monkeypatch):
    provider = _make_provider(monkeypatch)
    provider.token_data = {"access_token": "tok"}
    _patch_userinfo(
        monkeypatch,
        {
            "sub": "383249177292901445",
            "email": "asmith@dashboard152.com",
            "email_verified": True,
            "given_name": "Adam",
            "family_name": "Smith",
            "name": "Adam Smith",
            "picture": "https://id.auth.woven/avatar.png",
        },
    )

    provider.set_user_data()

    assert provider.user_data["email"] == "asmith@dashboard152.com"
    user = provider.user_data["user"]
    # sub -> provider_id (kept as a string).
    assert user["provider_id"] == "383249177292901445"
    assert user["email"] == "asmith@dashboard152.com"
    assert user["first_name"] == "Adam"
    assert user["last_name"] == "Smith"
    assert user["avatar"] == "https://id.auth.woven/avatar.png"
    assert user["is_password_autoset"] is True


def test_set_user_data_string_email_verified_is_accepted(monkeypatch):
    # Some IdPs serialize the boolean as a string; a positive assertion still counts.
    provider = _make_provider(monkeypatch)
    provider.token_data = {"access_token": "tok"}
    _patch_userinfo(
        monkeypatch,
        {"sub": "abc", "email": "user@example.com", "email_verified": "true"},
    )
    provider.set_user_data()
    assert provider.user_data["user"]["provider_id"] == "abc"


def test_set_user_data_falls_back_to_name_claim(monkeypatch):
    provider = _make_provider(monkeypatch)
    provider.token_data = {"access_token": "tok"}
    _patch_userinfo(
        monkeypatch,
        {"sub": "abc", "email": "user@example.com", "email_verified": True, "name": "Only Name"},
    )
    provider.set_user_data()
    assert provider.user_data["user"]["first_name"] == "Only Name"
    assert provider.user_data["user"]["last_name"] == ""


@pytest.mark.parametrize("email_verified", [False, "false", None, 0, "0", 1])
def test_set_user_data_rejects_unverified_email(monkeypatch, email_verified):
    provider = _make_provider(monkeypatch)
    provider.token_data = {"access_token": "tok"}
    userinfo = {"sub": "abc", "email": "victim@example.com"}
    if email_verified is not None:
        userinfo["email_verified"] = email_verified
    _patch_userinfo(monkeypatch, userinfo)

    with pytest.raises(AuthenticationException) as exc:
        provider.set_user_data()
    assert exc.value.error_code == AUTHENTICATION_ERROR_CODES["OAUTH_PROVIDER_UNVERIFIED_EMAIL"]


def test_set_user_data_missing_sub_raises_provider_error(monkeypatch):
    provider = _make_provider(monkeypatch)
    provider.token_data = {"access_token": "tok"}
    _patch_userinfo(
        monkeypatch,
        {"email": "user@example.com", "email_verified": True},  # no `sub`
    )
    with pytest.raises(AuthenticationException) as exc:
        provider.set_user_data()
    assert exc.value.error_code == AUTHENTICATION_ERROR_CODES["OIDC_OAUTH_PROVIDER_ERROR"]
