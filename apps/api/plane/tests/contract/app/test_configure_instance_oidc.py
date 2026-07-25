# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.
#
# woven: Contract test for plane-4cr — `configure_instance` seeds the OIDC config catalog so
# the admin form has rows to edit and the public InstanceEndpoint can read IS_OIDC_ENABLED.
#
# Note: IS_OIDC_ENABLED comes from the core.py catalog entry (env default "0"), NOT from a
# derived-from-credentials branch. configure_instance's IS_*_ENABLED derivation loop is dead
# code in this base (its existence-guard is tripped by the flags declared in core.py) — see
# plane-7fn.3. The admin form (plane-5kc) / the IS_OIDC_ENABLED env var control the flag.

import pytest
from django.core.management import call_command

from plane.license.models import InstanceConfiguration

pytestmark = pytest.mark.contract

OIDC_KEYS = [
    "IS_OIDC_ENABLED",
    "OIDC_CLIENT_ID",
    "OIDC_CLIENT_SECRET",
    "OIDC_URL_AUTHORIZATION",
    "OIDC_URL_TOKEN",
    "OIDC_URL_USERINFO",
    "OIDC_URL_ENDPOINT",
]


@pytest.mark.django_db
def test_configure_instance_seeds_oidc_config(monkeypatch):
    monkeypatch.setenv("SECRET_KEY", "test-secret-key")

    call_command("configure_instance")

    # every OIDC config key is registered in InstanceConfiguration
    for key in OIDC_KEYS:
        assert InstanceConfiguration.objects.filter(key=key).exists(), key
    # only the client secret is stored encrypted
    assert InstanceConfiguration.objects.get(key="OIDC_CLIENT_SECRET").is_encrypted is True
    assert InstanceConfiguration.objects.get(key="OIDC_CLIENT_ID").is_encrypted is False
    # the flag is seeded off by default (until an admin enables OIDC)
    assert InstanceConfiguration.objects.get(key="IS_OIDC_ENABLED").value == "0"
    assert InstanceConfiguration.objects.get(key="IS_OIDC_ENABLED").category == "OIDC"
