# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.
#
# woven: Generic OIDC SSO provider (Open-EE, feature: OIDC/SAML SSO). Clean-room
# implementation modeled on the CE Gitea/Google OAuth adapters — it is NOT derived from
# Plane's Commercial/EE OIDC code. Wired through the same ~6 manual provider sites the
# other OAuth providers use; gated behind the `IS_OIDC_ENABLED` InstanceConfiguration key.

import os
from datetime import datetime, timedelta
from urllib.parse import urlencode, urlparse

import pytz
import requests

# Module imports
from plane.authentication.adapter.oauth import OauthAdapter
from plane.license.utils.instance_value import get_configuration_value
from plane.authentication.adapter.error import (
    AUTHENTICATION_ERROR_CODES,
    AuthenticationException,
)


class OIDCOAuthProvider(OauthAdapter):
    provider = "oidc"
    # Standard OpenID Connect scopes. `openid` selects the OIDC flow; `email`/`profile`
    # release the claims we map below (email, email_verified, sub, name, picture).
    scope = "openid email profile"

    def __init__(self, request, code=None, state=None, callback=None):
        (
            OIDC_CLIENT_ID,
            OIDC_CLIENT_SECRET,
            OIDC_URL_AUTHORIZATION,
            OIDC_URL_TOKEN,
            OIDC_URL_USERINFO,
            OIDC_URL_ENDPOINT,
        ) = get_configuration_value(
            [
                {
                    "key": "OIDC_CLIENT_ID",
                    "default": os.environ.get("OIDC_CLIENT_ID"),
                },
                {
                    "key": "OIDC_CLIENT_SECRET",
                    "default": os.environ.get("OIDC_CLIENT_SECRET"),
                },
                {
                    "key": "OIDC_URL_AUTHORIZATION",
                    "default": os.environ.get("OIDC_URL_AUTHORIZATION"),
                },
                {
                    "key": "OIDC_URL_TOKEN",
                    "default": os.environ.get("OIDC_URL_TOKEN"),
                },
                {
                    "key": "OIDC_URL_USERINFO",
                    "default": os.environ.get("OIDC_URL_USERINFO"),
                },
                # Optional: the issuer / discovery-document URL. When the three explicit
                # endpoints above are not all set, they are derived from this provider's
                # `.well-known/openid-configuration` document instead.
                {
                    "key": "OIDC_URL_ENDPOINT",
                    "default": os.environ.get("OIDC_URL_ENDPOINT"),
                },
            ]
        )

        if not (OIDC_CLIENT_ID and OIDC_CLIENT_SECRET):
            raise AuthenticationException(
                error_code=AUTHENTICATION_ERROR_CODES["OIDC_NOT_CONFIGURED"],
                error_message="OIDC_NOT_CONFIGURED",
            )

        # Resolve the three endpoints. Explicitly configured URLs always win; any that are
        # missing are filled from the discovery document (if an endpoint/issuer is set).
        authorization_url = OIDC_URL_AUTHORIZATION
        token_url = OIDC_URL_TOKEN
        userinfo_url = OIDC_URL_USERINFO

        if not (authorization_url and token_url and userinfo_url) and OIDC_URL_ENDPOINT:
            discovery = self._fetch_discovery_document(OIDC_URL_ENDPOINT)
            authorization_url = authorization_url or discovery.get("authorization_endpoint")
            token_url = token_url or discovery.get("token_endpoint")
            userinfo_url = userinfo_url or discovery.get("userinfo_endpoint")

        # A usable provider needs all three endpoints and each must be a real http(s) URL.
        # Bail out as "not configured" rather than leaking a malformed URL into the browser
        # redirect / a server-side fetch.
        if not (
            self._is_http_url(authorization_url)
            and self._is_http_url(token_url)
            and self._is_http_url(userinfo_url)
        ):
            raise AuthenticationException(
                error_code=AUTHENTICATION_ERROR_CODES["OIDC_NOT_CONFIGURED"],
                error_message="OIDC_NOT_CONFIGURED",
            )

        self.token_url = token_url
        self.userinfo_url = userinfo_url

        client_id = OIDC_CLIENT_ID
        client_secret = OIDC_CLIENT_SECRET

        redirect_uri = (
            f"{'https' if request.is_secure() else 'http'}://{request.get_host()}/auth/oidc/callback/"
        )
        url_params = {
            "client_id": client_id,
            "scope": self.scope,
            "redirect_uri": redirect_uri,
            "response_type": "code",
            "state": state,
        }
        auth_url = f"{authorization_url}?{urlencode(url_params)}"

        super().__init__(
            request,
            self.provider,
            client_id,
            self.scope,
            redirect_uri,
            auth_url,
            self.token_url,
            self.userinfo_url,
            client_secret,
            code,
            callback=callback,
        )

    @staticmethod
    def _is_http_url(value):
        """True only for a well-formed http(s) URL with a network location."""
        if not value:
            return False
        parsed = urlparse(value)
        return parsed.scheme in ("http", "https") and bool(parsed.netloc)

    def _fetch_discovery_document(self, endpoint):
        """Fetch and parse the OIDC discovery document.

        `endpoint` may be either the issuer base (e.g. ``https://idp.example``) or the full
        ``.well-known/openid-configuration`` URL. A missing/broken document means the
        provider cannot be used, so it surfaces as OIDC_NOT_CONFIGURED (this runs at
        construction time, i.e. before any token/userinfo exchange).
        """
        if not self._is_http_url(endpoint):
            raise AuthenticationException(
                error_code=AUTHENTICATION_ERROR_CODES["OIDC_NOT_CONFIGURED"],
                error_message="OIDC_NOT_CONFIGURED",
            )

        discovery_url = endpoint.rstrip("/")
        if not discovery_url.endswith("/.well-known/openid-configuration"):
            discovery_url = f"{discovery_url}/.well-known/openid-configuration"

        try:
            response = requests.get(
                discovery_url, headers={"Accept": "application/json"}, timeout=10
            )
            response.raise_for_status()
            return response.json()
        except requests.RequestException:
            raise AuthenticationException(
                error_code=AUTHENTICATION_ERROR_CODES["OIDC_NOT_CONFIGURED"],
                error_message="OIDC_NOT_CONFIGURED",
            )

    def set_token_data(self):
        data = {
            "code": self.code,
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "redirect_uri": self.redirect_uri,
            "grant_type": "authorization_code",
        }
        headers = {"Accept": "application/json"}
        token_response = self.get_user_token(data=data, headers=headers)
        super().set_token_data(
            {
                "access_token": token_response.get("access_token"),
                "refresh_token": token_response.get("refresh_token", None),
                # OIDC `expires_in` is a lifetime in seconds; add it to "now" to get the
                # absolute expiry (do NOT treat it as an epoch timestamp).
                "access_token_expired_at": (
                    datetime.now(tz=pytz.utc) + timedelta(seconds=token_response.get("expires_in"))
                    if token_response.get("expires_in")
                    else None
                ),
                "refresh_token_expired_at": (
                    datetime.fromtimestamp(token_response.get("refresh_token_expired_at"), tz=pytz.utc)
                    if token_response.get("refresh_token_expired_at")
                    else None
                ),
                "id_token": token_response.get("id_token", ""),
            }
        )

    @staticmethod
    def _is_email_verified(claim):
        """OIDC `email_verified` is a boolean, but some IdPs serialize it as a string.

        Fail closed: only an explicit, positive assertion counts as verified. Anything
        else — ``False``, ``"false"``, ``None``, a missing claim, numbers — is treated as
        unverified.
        """
        if claim is True:
            return True
        if isinstance(claim, str):
            return claim.strip().lower() == "true"
        return False

    def set_user_data(self):
        user_info_response = self.get_user_response()

        # Reject unverified emails. A generic OIDC provider is only as trustworthy as its
        # `email_verified` claim: without this guard, an attacker who controls (or can
        # freely register on) the configured IdP could assert a victim's address and take
        # over their existing Plane account (GHSA-7j95-vh8g-f365). Same fail-closed posture
        # as the Google/Gitea adapters.
        if not self._is_email_verified(user_info_response.get("email_verified")):
            raise AuthenticationException(
                error_code=AUTHENTICATION_ERROR_CODES["OAUTH_PROVIDER_UNVERIFIED_EMAIL"],
                error_message="OAUTH_PROVIDER_UNVERIFIED_EMAIL",
            )

        # `sub` is the stable, provider-assigned subject identifier and is REQUIRED by the
        # OIDC spec — it is what we persist as the account's provider id. A response without
        # it is malformed; refuse it rather than keying an account off ``"None"``.
        sub = user_info_response.get("sub")
        if not sub:
            raise AuthenticationException(
                error_code=AUTHENTICATION_ERROR_CODES["OIDC_OAUTH_PROVIDER_ERROR"],
                error_message="OIDC_OAUTH_PROVIDER_ERROR",
            )

        email = user_info_response.get("email")
        super().set_user_data(
            {
                "email": email,
                "user": {
                    "provider_id": str(sub),
                    "email": email,
                    "avatar": user_info_response.get("picture"),
                    # Prefer the granular name claims; fall back to the full `name`.
                    "first_name": user_info_response.get("given_name") or user_info_response.get("name") or "",
                    "last_name": user_info_response.get("family_name") or "",
                    "is_password_autoset": True,
                },
            }
        )
