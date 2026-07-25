# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.
#
# woven: Unit tests for the OIDC entries in the instance-config catalog (plane-4cr). DB-free —
# asserts the config-variable declarations only. The public /api/instances/ `is_oidc_enabled`
# flag is covered by the contract test (test_instance_oidc.py).

import pytest

from plane.utils.instance_config_variables import instance_config_variables

pytestmark = pytest.mark.unit

# key -> expected is_encrypted (only the client secret is encrypted)
OIDC_KEYS = {
    "IS_OIDC_ENABLED": False,
    "OIDC_CLIENT_ID": False,
    "OIDC_CLIENT_SECRET": True,
    "OIDC_URL_AUTHORIZATION": False,
    "OIDC_URL_TOKEN": False,
    "OIDC_URL_USERINFO": False,
    "OIDC_URL_ENDPOINT": False,
}


def _by_key():
    return {entry["key"]: entry for entry in instance_config_variables}


def test_all_oidc_config_variables_registered():
    catalog = _by_key()
    for key in OIDC_KEYS:
        assert key in catalog, f"{key} missing from instance_config_variables"


def test_oidc_config_variables_use_oidc_category():
    catalog = _by_key()
    for key in OIDC_KEYS:
        assert catalog[key]["category"] == "OIDC", key


def test_only_oidc_client_secret_is_encrypted():
    catalog = _by_key()
    for key, expected_encrypted in OIDC_KEYS.items():
        assert catalog[key]["is_encrypted"] is expected_encrypted, key


def test_oidc_keys_declared_exactly_once():
    keys = [entry["key"] for entry in instance_config_variables]
    for key in OIDC_KEYS:
        assert keys.count(key) == 1, f"{key} declared {keys.count(key)} times"
