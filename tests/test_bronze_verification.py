"""Tests for verification of existing Bronze objects."""

import hashlib
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from azure.core.exceptions import ResourceNotFoundError

from src.bharatpulse.ingestion.azure_storage import (
    verify_existing_bronze_file,
)


@patch(
    "src.bharatpulse.ingestion.azure_storage.BlobServiceClient"
)
@patch(
    "src.bharatpulse.ingestion.azure_storage.DefaultAzureCredential"
)
def test_existing_matching_blob_is_verified(
    mock_credential_class: MagicMock,
    mock_service_class: MagicMock,
    tmp_path: Path,
) -> None:
    """Reuse an existing Bronze object when its checksum matches."""
    source = tmp_path / "mandi.csv"
    content = b"state,price\nDelhi,100\n"
    source.write_bytes(content)

    service = mock_service_class.return_value.__enter__.return_value
    blob = service.get_blob_client.return_value

    blob.download_blob.return_value.chunks.return_value = [content]
    blob.get_blob_properties.return_value.size = len(content)
    blob.get_blob_properties.return_value.etag = '"test-etag"'

    result = verify_existing_bronze_file(source)

    assert result is not None
    assert result["status"] == "VERIFIED_EXISTING"
    assert result["sha256"] == hashlib.sha256(content).hexdigest()
    assert result["overwrite"] is False

    blob.upload_blob.assert_not_called()
    mock_credential_class.return_value.close.assert_called_once()


@patch(
    "src.bharatpulse.ingestion.azure_storage.BlobServiceClient"
)
@patch(
    "src.bharatpulse.ingestion.azure_storage.DefaultAzureCredential"
)
def test_existing_different_blob_raises_conflict(
    mock_credential_class: MagicMock,
    mock_service_class: MagicMock,
    tmp_path: Path,
) -> None:
    """Reject existing Bronze content that differs from the local file."""
    source = tmp_path / "mandi.csv"
    source.write_bytes(b"state,price\nDelhi,100\n")

    service = mock_service_class.return_value.__enter__.return_value
    blob = service.get_blob_client.return_value
    blob.download_blob.return_value.chunks.return_value = [
        b"state,price\nDelhi,999\n"
    ]

    with pytest.raises(RuntimeError, match="Bronze content conflict"):
        verify_existing_bronze_file(source)

    blob.upload_blob.assert_not_called()
    mock_credential_class.return_value.close.assert_called_once()


@patch(
    "src.bharatpulse.ingestion.azure_storage.BlobServiceClient"
)
@patch(
    "src.bharatpulse.ingestion.azure_storage.DefaultAzureCredential"
)
def test_missing_bronze_object_returns_none(
    mock_credential_class: MagicMock,
    mock_service_class: MagicMock,
    tmp_path: Path,
) -> None:
    """Return None when the remote Bronze object does not exist."""
    source = tmp_path / "mandi.csv"
    source.write_bytes(b"state,price\nDelhi,100\n")

    service = mock_service_class.return_value.__enter__.return_value
    blob = service.get_blob_client.return_value

    blob.download_blob.side_effect = ResourceNotFoundError(
        message="Blob not found"
    )

    result = verify_existing_bronze_file(source)

    assert result is None
    blob.upload_blob.assert_not_called()
    mock_credential_class.return_value.close.assert_called_once()


def test_missing_local_file_fails_before_azure_access(
    tmp_path: Path,
) -> None:
    """Reject missing local input without creating Azure clients."""
    missing_file = tmp_path / "missing.csv"

    with patch(
        "src.bharatpulse.ingestion.azure_storage.BlobServiceClient"
    ) as mock_service_class:
        with pytest.raises(FileNotFoundError):
            verify_existing_bronze_file(missing_file)

        mock_service_class.assert_not_called()