# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.
#
# woven: Contract test for plane-4cr. Acceptance: the public GET /api/instances/ payload
# exposes `is_oidc_enabled` so the login UI knows whether to offer the SSO button.

import uuid

import pytest
from django.test import Client
from django.urls import reverse
from django.utils import timezone
from rest_framework import status

from plane.license.models import Instance

pytestmark = pytest.mark.contract


@pytest.fixture
def setup_instance(db):
    """Create a minimal, setup-complete Instance singleton (mirrors the auth contract tests)."""
    instance_id = uuid.uuid4() if not Instance.objects.exists() else Instance.objects.first().id
    instance, _ = Instance.objects.update_or_create(
        id=instance_id,
        defaults={
            "instance_name": "Test Instance",
            "instance_id": str(uuid.uuid4()),
            "current_version": "1.0.0",
            "domain": "http://localhost:8000",
            "last_checked_at": timezone.now(),
            "is_setup_done": True,
        },
    )
    return instance


@pytest.mark.django_db
def test_instance_endpoint_exposes_is_oidc_enabled(setup_instance):
    response = Client().get(reverse("instance"))

    assert response.status_code == status.HTTP_200_OK
    config = response.json()["config"]
    # advertised alongside the other providers so the login screen can show the SSO button
    assert "is_oidc_enabled" in config
    assert isinstance(config["is_oidc_enabled"], bool)
    # off by default until an admin configures OIDC credentials + endpoints
    assert config["is_oidc_enabled"] is False
