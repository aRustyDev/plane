# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.
#
# woven: Unit tests for the OIDC SSO views (plane-1f2). DB-free — Instance, base_host and
# the provider config lookup are mocked. Acceptance: GET /auth/oidc/ 302s to the IdP
# authorize URL; callback maps errors (bad state / missing code) to a redirect.

import pytest
from django.test import RequestFactory

from plane.authentication.adapter.error import AUTHENTICATION_ERROR_CODES
from plane.authentication.provider.oauth import oidc as oidc_provider
from plane.authentication.views.app import oidc as oidc_app
from plane.authentication.views.space import oidc as oidc_space

pytestmark = pytest.mark.unit


AUTHORIZATION_URL = "https://id.auth.woven/oauth/v2/authorize"
TOKEN_URL = "https://id.auth.woven/oauth/v2/token"
USERINFO_URL = "https://id.auth.woven/oidc/v1/userinfo"
# (CLIENT_ID, CLIENT_SECRET, URL_AUTHORIZATION, URL_TOKEN, URL_USERINFO, URL_ENDPOINT)
EXPLICIT_CONFIG = ("client-id", "client-secret", AUTHORIZATION_URL, TOKEN_URL, USERINFO_URL, None)

OIDC_ERR = AUTHENTICATION_ERROR_CODES["OIDC_OAUTH_PROVIDER_ERROR"]
NOT_CONFIGURED = AUTHENTICATION_ERROR_CODES["INSTANCE_NOT_CONFIGURED"]


class _Instance:
    def __init__(self, setup_done):
        self.is_setup_done = setup_done


def _instance_model(first_value):
    class _Manager:
        def first(self):
            return first_value

    class _Model:
        objects = _Manager()

    return _Model


def _request(module, path, query=""):
    """RequestFactory request with a dict session and base_host stubbed on `module`."""
    request = RequestFactory().get(f"{path}?{query}" if query else path)
    request.session = {}
    return request


@pytest.fixture(autouse=True)
def _stub_base_host(monkeypatch):
    # base_host() reads settings; pin it so error redirects have a stable base URL and so
    # the space view's (fixed, un-shadowed) base_host() calls resolve to a callable.
    for module in (oidc_app, oidc_space):
        monkeypatch.setattr(module, "base_host", lambda request, **kwargs: "http://testserver")


# --- app: initiate -----------------------------------------------------------------------


def test_app_initiate_redirects_to_authorize(monkeypatch):
    monkeypatch.setattr(oidc_app, "Instance", _instance_model(_Instance(setup_done=True)))
    monkeypatch.setattr(oidc_provider, "get_configuration_value", lambda keys: EXPLICIT_CONFIG)

    request = _request(oidc_app, "/auth/oidc/")
    response = oidc_app.OIDCOauthInitiateEndpoint().get(request)

    assert response.status_code == 302
    assert response.url.startswith(f"{AUTHORIZATION_URL}?")
    assert "response_type=code" in response.url
    assert "client_id=client-id" in response.url
    # a CSRF state was generated and stashed on the session, and echoed in the redirect
    assert request.session["state"]
    assert f"state={request.session['state']}" in response.url


def test_app_initiate_instance_not_configured(monkeypatch):
    monkeypatch.setattr(oidc_app, "Instance", _instance_model(None))

    request = _request(oidc_app, "/auth/oidc/")
    response = oidc_app.OIDCOauthInitiateEndpoint().get(request)

    assert response.status_code == 302
    assert f"error_code={NOT_CONFIGURED}" in response.url
    assert "INSTANCE_NOT_CONFIGURED" in response.url


def test_app_initiate_provider_not_configured_is_mapped(monkeypatch):
    # Instance is set up, but OIDC has no client credentials -> provider raises, view
    # redirects with the error rather than 500ing.
    monkeypatch.setattr(oidc_app, "Instance", _instance_model(_Instance(setup_done=True)))
    monkeypatch.setattr(
        oidc_provider, "get_configuration_value", lambda keys: (None, None, None, None, None, None)
    )

    request = _request(oidc_app, "/auth/oidc/")
    response = oidc_app.OIDCOauthInitiateEndpoint().get(request)

    assert response.status_code == 302
    assert f"error_code={AUTHENTICATION_ERROR_CODES['OIDC_NOT_CONFIGURED']}" in response.url


# --- app: callback error mapping ---------------------------------------------------------


def test_app_callback_state_mismatch_maps_error():
    request = _request(oidc_app, "/auth/oidc/callback/", "code=abc&state=attacker")
    request.session = {"state": "expected", "next_path": None}

    response = oidc_app.OIDCCallbackEndpoint().get(request)

    assert response.status_code == 302
    assert f"error_code={OIDC_ERR}" in response.url
    assert "OIDC_OAUTH_PROVIDER_ERROR" in response.url


def test_app_callback_missing_code_maps_error():
    request = _request(oidc_app, "/auth/oidc/callback/", "state=s")
    request.session = {"state": "s"}

    response = oidc_app.OIDCCallbackEndpoint().get(request)

    assert response.status_code == 302
    assert f"error_code={OIDC_ERR}" in response.url


# --- space: parity + shadow-bug regression ----------------------------------------------


def test_space_initiate_redirects_to_authorize(monkeypatch):
    monkeypatch.setattr(oidc_space, "Instance", _instance_model(_Instance(setup_done=True)))
    monkeypatch.setattr(oidc_provider, "get_configuration_value", lambda keys: EXPLICIT_CONFIG)

    request = _request(oidc_space, "/auth/spaces/oidc/")
    response = oidc_space.OIDCOauthInitiateSpaceEndpoint().get(request)

    assert response.status_code == 302
    assert response.url.startswith(f"{AUTHORIZATION_URL}?")


def test_space_callback_state_mismatch_maps_error():
    # Regression guard: the CE google/github/gitlab space callbacks shadow base_host with a
    # session string and then call it as a function, which would raise here instead of
    # producing a clean error redirect. Our view drops that shadow.
    request = _request(oidc_space, "/auth/spaces/oidc/callback/", "code=abc&state=attacker")
    request.session = {"state": "expected", "host": "http://testserver/spaces/", "next_path": None}

    response = oidc_space.OIDCCallbackSpaceEndpoint().get(request)

    assert response.status_code == 302
    assert f"error_code={OIDC_ERR}" in response.url
