# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

import os
from unittest.mock import Mock, patch
import pytest
from plane.settings.storage import S3Storage


@pytest.mark.unit
class TestS3StorageSignedURLExpiration:
    """Test the configurable signed URL expiration in S3Storage"""

    @patch.dict(os.environ, {}, clear=True)
    @patch("plane.settings.storage.boto3")
    def test_default_expiration_without_env_variable(self, mock_boto3):
        """Test that default expiration is 3600 seconds when env variable is not set"""
        # Mock the boto3 client
        mock_boto3.client.return_value = Mock()

        # Create S3Storage instance without SIGNED_URL_EXPIRATION env variable
        storage = S3Storage()

        # Assert default expiration is 3600
        assert storage.signed_url_expiration == 3600

    @patch.dict(os.environ, {"SIGNED_URL_EXPIRATION": "30"}, clear=True)
    @patch("plane.settings.storage.boto3")
    def test_custom_expiration_with_env_variable(self, mock_boto3):
        """Test that expiration is read from SIGNED_URL_EXPIRATION env variable"""
        # Mock the boto3 client
        mock_boto3.client.return_value = Mock()

        # Create S3Storage instance with SIGNED_URL_EXPIRATION=30
        storage = S3Storage()

        # Assert expiration is 30
        assert storage.signed_url_expiration == 30

    @patch.dict(os.environ, {"SIGNED_URL_EXPIRATION": "300"}, clear=True)
    @patch("plane.settings.storage.boto3")
    def test_custom_expiration_multiple_values(self, mock_boto3):
        """Test that expiration works with different custom values"""
        # Mock the boto3 client
        mock_boto3.client.return_value = Mock()

        # Create S3Storage instance with SIGNED_URL_EXPIRATION=300
        storage = S3Storage()

        # Assert expiration is 300
        assert storage.signed_url_expiration == 300

    @patch.dict(
        os.environ,
        {
            "AWS_ACCESS_KEY_ID": "test-key",
            "AWS_SECRET_ACCESS_KEY": "test-secret",
            "AWS_S3_BUCKET_NAME": "test-bucket",
            "AWS_REGION": "us-east-1",
        },
        clear=True,
    )
    @patch("plane.settings.storage.boto3")
    def test_generate_presigned_post_uses_default_expiration(self, mock_boto3):
        """Test that generate_presigned_post uses the configured default expiration"""
        # Mock the boto3 client and its response
        mock_s3_client = Mock()
        mock_s3_client.generate_presigned_post.return_value = {
            "url": "https://test-url.com",
            "fields": {},
        }
        mock_boto3.client.return_value = mock_s3_client

        # Create S3Storage instance
        storage = S3Storage()

        # Call generate_presigned_post without explicit expiration
        storage.generate_presigned_post("test-object", "image/png", 1024)

        # Assert that the boto3 method was called with the default expiration (3600)
        mock_s3_client.generate_presigned_post.assert_called_once()
        call_kwargs = mock_s3_client.generate_presigned_post.call_args[1]
        assert call_kwargs["ExpiresIn"] == 3600

    @patch.dict(
        os.environ,
        {
            "AWS_ACCESS_KEY_ID": "test-key",
            "AWS_SECRET_ACCESS_KEY": "test-secret",
            "AWS_S3_BUCKET_NAME": "test-bucket",
            "AWS_REGION": "us-east-1",
            "SIGNED_URL_EXPIRATION": "60",
        },
        clear=True,
    )
    @patch("plane.settings.storage.boto3")
    def test_generate_presigned_post_uses_custom_expiration(self, mock_boto3):
        """Test that generate_presigned_post uses custom expiration from env variable"""
        # Mock the boto3 client and its response
        mock_s3_client = Mock()
        mock_s3_client.generate_presigned_post.return_value = {
            "url": "https://test-url.com",
            "fields": {},
        }
        mock_boto3.client.return_value = mock_s3_client

        # Create S3Storage instance with SIGNED_URL_EXPIRATION=60
        storage = S3Storage()

        # Call generate_presigned_post without explicit expiration
        storage.generate_presigned_post("test-object", "image/png", 1024)

        # Assert that the boto3 method was called with custom expiration (60)
        mock_s3_client.generate_presigned_post.assert_called_once()
        call_kwargs = mock_s3_client.generate_presigned_post.call_args[1]
        assert call_kwargs["ExpiresIn"] == 60

    @patch.dict(
        os.environ,
        {
            "AWS_ACCESS_KEY_ID": "test-key",
            "AWS_SECRET_ACCESS_KEY": "test-secret",
            "AWS_S3_BUCKET_NAME": "test-bucket",
            "AWS_REGION": "us-east-1",
        },
        clear=True,
    )
    @patch("plane.settings.storage.boto3")
    def test_generate_presigned_url_uses_default_expiration(self, mock_boto3):
        """Test that generate_presigned_url uses the configured default expiration"""
        # Mock the boto3 client and its response
        mock_s3_client = Mock()
        mock_s3_client.generate_presigned_url.return_value = "https://test-url.com"
        mock_boto3.client.return_value = mock_s3_client

        # Create S3Storage instance
        storage = S3Storage()

        # Call generate_presigned_url without explicit expiration
        storage.generate_presigned_url("test-object")

        # Assert that the boto3 method was called with the default expiration (3600)
        mock_s3_client.generate_presigned_url.assert_called_once()
        call_kwargs = mock_s3_client.generate_presigned_url.call_args[1]
        assert call_kwargs["ExpiresIn"] == 3600

    @patch.dict(
        os.environ,
        {
            "AWS_ACCESS_KEY_ID": "test-key",
            "AWS_SECRET_ACCESS_KEY": "test-secret",
            "AWS_S3_BUCKET_NAME": "test-bucket",
            "AWS_REGION": "us-east-1",
            "SIGNED_URL_EXPIRATION": "30",
        },
        clear=True,
    )
    @patch("plane.settings.storage.boto3")
    def test_generate_presigned_url_uses_custom_expiration(self, mock_boto3):
        """Test that generate_presigned_url uses custom expiration from env variable"""
        # Mock the boto3 client and its response
        mock_s3_client = Mock()
        mock_s3_client.generate_presigned_url.return_value = "https://test-url.com"
        mock_boto3.client.return_value = mock_s3_client

        # Create S3Storage instance with SIGNED_URL_EXPIRATION=30
        storage = S3Storage()

        # Call generate_presigned_url without explicit expiration
        storage.generate_presigned_url("test-object")

        # Assert that the boto3 method was called with custom expiration (30)
        mock_s3_client.generate_presigned_url.assert_called_once()
        call_kwargs = mock_s3_client.generate_presigned_url.call_args[1]
        assert call_kwargs["ExpiresIn"] == 30

    @patch.dict(
        os.environ,
        {
            "AWS_ACCESS_KEY_ID": "test-key",
            "AWS_SECRET_ACCESS_KEY": "test-secret",
            "AWS_S3_BUCKET_NAME": "test-bucket",
            "AWS_REGION": "us-east-1",
            "SIGNED_URL_EXPIRATION": "30",
        },
        clear=True,
    )
    @patch("plane.settings.storage.boto3")
    def test_explicit_expiration_overrides_default(self, mock_boto3):
        """Test that explicit expiration parameter overrides the default"""
        # Mock the boto3 client and its response
        mock_s3_client = Mock()
        mock_s3_client.generate_presigned_url.return_value = "https://test-url.com"
        mock_boto3.client.return_value = mock_s3_client

        # Create S3Storage instance with SIGNED_URL_EXPIRATION=30
        storage = S3Storage()

        # Call generate_presigned_url with explicit expiration=120
        storage.generate_presigned_url("test-object", expiration=120)

        # Assert that the boto3 method was called with explicit expiration (120)
        mock_s3_client.generate_presigned_url.assert_called_once()
        call_kwargs = mock_s3_client.generate_presigned_url.call_args[1]
        assert call_kwargs["ExpiresIn"] == 120


S3_ENV = {
    "AWS_ACCESS_KEY_ID": "test-key",
    "AWS_SECRET_ACCESS_KEY": "test-secret",
    "AWS_S3_BUCKET_NAME": "test-bucket",
    "AWS_REGION": "us-east-1",
}


@pytest.mark.unit
class TestS3StorageUploadMethod:
    """Test AWS_S3_UPLOAD_METHOD dispatch and the presigned PUT flavour.

    Presigned PUT exists for object stores that do not implement presigned POST — Cloudflare R2
    answers a presigned POST with 501 NotImplemented, so browser uploads can never land there
    while server-side flows keep working.
    """

    @patch.dict(os.environ, S3_ENV, clear=True)
    @patch("plane.settings.storage.boto3")
    def test_upload_method_defaults_to_post(self, mock_boto3):
        """Default must stay POST — that is what S3 and MinIO implement"""
        mock_boto3.client.return_value = Mock()
        assert S3Storage().upload_method == "post"

    @patch.dict(os.environ, {**S3_ENV, "AWS_S3_UPLOAD_METHOD": "PUT"}, clear=True)
    @patch("plane.settings.storage.boto3")
    def test_upload_method_is_case_insensitive(self, mock_boto3):
        mock_boto3.client.return_value = Mock()
        assert S3Storage().upload_method == "put"

    @patch.dict(os.environ, {**S3_ENV, "AWS_S3_UPLOAD_METHOD": "sftp"}, clear=True)
    @patch("plane.settings.storage.boto3")
    def test_unknown_upload_method_falls_back_to_post(self, mock_boto3):
        """An unrecognised value must not silently disable uploads"""
        mock_boto3.client.return_value = Mock()
        assert S3Storage().upload_method == "post"

    @patch.dict(os.environ, S3_ENV, clear=True)
    @patch("plane.settings.storage.boto3")
    def test_generate_presigned_upload_dispatches_to_post_by_default(self, mock_boto3):
        mock_s3_client = Mock()
        mock_s3_client.generate_presigned_post.return_value = {"url": "https://s3", "fields": {}}
        mock_boto3.client.return_value = mock_s3_client

        response = S3Storage().generate_presigned_upload("test-object", "image/png", 1024)

        mock_s3_client.generate_presigned_post.assert_called_once()
        mock_s3_client.generate_presigned_url.assert_not_called()
        assert response["method"] == "POST"

    @patch.dict(os.environ, {**S3_ENV, "AWS_S3_UPLOAD_METHOD": "put"}, clear=True)
    @patch("plane.settings.storage.boto3")
    def test_generate_presigned_upload_dispatches_to_put(self, mock_boto3):
        mock_s3_client = Mock()
        mock_s3_client.generate_presigned_url.return_value = "https://r2/test-object?sig"
        mock_boto3.client.return_value = mock_s3_client

        response = S3Storage().generate_presigned_upload("test-object", "image/png", 1024)

        mock_s3_client.generate_presigned_post.assert_not_called()
        assert response["method"] == "PUT"
        assert response["url"] == "https://r2/test-object?sig"
        # `fields` stays present-but-empty so the response shape is stable for clients
        assert response["fields"] == {}

    @patch.dict(os.environ, {**S3_ENV, "AWS_S3_UPLOAD_METHOD": "put"}, clear=True)
    @patch("plane.settings.storage.boto3")
    def test_presigned_put_signs_content_type_and_length(self, mock_boto3):
        """Content-Type and Content-Length must be SIGNED.

        This is what replaces the POST policy's conditions: both land in SignedHeaders, so the
        store rejects a mismatch with 403 rather than accepting a differently-sized or
        differently-typed object. It is stricter than content-length-range, which permitted
        anything in [1, file_size].
        """
        mock_s3_client = Mock()
        mock_s3_client.generate_presigned_url.return_value = "https://r2/test-object?sig"
        mock_boto3.client.return_value = mock_s3_client

        response = S3Storage().generate_presigned_put("test-object", "image/png", 1024)

        call_kwargs = mock_s3_client.generate_presigned_url.call_args[1]
        assert mock_s3_client.generate_presigned_url.call_args[0][0] == "put_object"
        assert call_kwargs["Params"]["ContentType"] == "image/png"
        assert call_kwargs["Params"]["ContentLength"] == 1024
        assert call_kwargs["Params"]["Key"] == "test-object"
        assert call_kwargs["Params"]["Bucket"] == "test-bucket"
        assert response["headers"]["Content-Type"] == "image/png"
        assert response["headers"]["Content-Length"] == "1024"

    @patch.dict(os.environ, {**S3_ENV, "AWS_S3_UPLOAD_METHOD": "put"}, clear=True)
    @patch("plane.settings.storage.boto3")
    def test_presigned_put_uses_default_expiration(self, mock_boto3):
        mock_s3_client = Mock()
        mock_s3_client.generate_presigned_url.return_value = "https://r2/test-object?sig"
        mock_boto3.client.return_value = mock_s3_client

        S3Storage().generate_presigned_put("test-object", "image/png", 1024)

        assert mock_s3_client.generate_presigned_url.call_args[1]["ExpiresIn"] == 3600

    @patch.dict(os.environ, {**S3_ENV, "AWS_S3_UPLOAD_METHOD": "put"}, clear=True)
    @patch("plane.settings.storage.boto3")
    def test_presigned_put_rejects_filename_template(self, mock_boto3):
        """`${filename}` is a POST-policy feature and cannot be expressed as a PUT.

        No caller uses it, but failing loudly beats uploading to a key containing the literal
        string "${filename}".
        """
        mock_boto3.client.return_value = Mock()

        with pytest.raises(ValueError):
            S3Storage().generate_presigned_put("${filename}", "image/png", 1024)
