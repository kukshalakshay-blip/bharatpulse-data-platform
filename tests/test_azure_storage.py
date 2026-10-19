"""Tests for Azure Bronze ingestion utilities."""

import hashlib
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from azure.core.exceptions import ResourceExistsError

from src.bharatpulse.ingestion.azure_storage import (
    calculate_sha256,
    upload_file_to_bronze,
)


def test_calculate_sha256(tmp_path: Path) -> None:
    """Verify that SHA-256 calculation is correct."""
    file_path = tmp_path / "sample.csv"
    file_path.write_bytes(b"state,price\nDelhi,100\n")

    expected = hashlib.sha256(file_path.read_bytes()).hexdigest()

    assert calculate_sha256(file_path) == expected


def test_missing_file_raises_error(tmp_path: Path) -> None:
    """Reject a source file that does not exist."""
    missing_file = tmp_path / "missing.csv"

    with pytest.raises(FileNotFoundError):
        upload_file_to_bronze(missing_file)


def test_invalid_destination_filename_raises_error(
    tmp_path: Path,
) -> None:
    """Reject destination paths instead of plain filenames."""
    source_file = tmp_path / "sample.csv"
    source_file.write_text("state,price\nDelhi,100\n", encoding="utf-8")

    with pytest.raises(ValueError, match="must be a filename"):
        upload_file_to_bronze(
            source_file,
            destination_filename="../sample.csv",
        )


@patch(
    "src.bharatpulse.ingestion.azure_storage.BlobServiceClient"
)
@patch(
    "src.bharatpulse.ingestion.azure_storage.DefaultAzureCredential"
)
def test_successful_upload(
    mock_credential_class: MagicMock,
    mock_service_class: MagicMock,
    tmp_path: Path,
) -> None:
    """Verify upload metadata and remote checksum verification."""
    source_file = tmp_path / "sample.csv"
    content = b"state,price\nDelhi,100\n"
    source_file.write_bytes(content)

    expected_sha256 = hashlib.sha256(content).hexdigest()

    mock_service = mock_service_class.return_value.__enter__.return_value
    mock_blob = mock_service.get_blob_client.return_value
    mock_blob.download_blob.return_value.chunks.return_value = [content]
    mock_blob.get_blob_properties.return_value.size = len(content)
    mock_blob.get_blob_properties.return_value.etag = '"test-etag"'

    result = upload_file_to_bronze(source_file)

    mock_blob.upload_blob.assert_called_once()
    assert result["status"] == "SUCCESS"
    assert result["size_bytes"] == len(content)
    assert result["sha256"] == expected_sha256
    assert result["destination"].endswith(
        "bronze/food_prices/sample.csv"
    )
    mock_credential_class.return_value.close.assert_called_once()


@patch(
    "src.bharatpulse.ingestion.azure_storage.BlobServiceClient"
)
@patch(
    "src.bharatpulse.ingestion.azure_storage.DefaultAzureCredential"
)
def test_existing_blob_is_not_overwritten(
    mock_credential_class: MagicMock,
    mock_service_class: MagicMock,
    tmp_path: Path,
) -> None:
    """Propagate an existing-object error without overwriting data."""
    source_file = tmp_path / "sample.csv"
    source_file.write_text("state,price\nDelhi,100\n", encoding="utf-8")

    mock_service = mock_service_class.return_value.__enter__.return_value
    mock_blob = mock_service.get_blob_client.return_value
    mock_blob.upload_blob.side_effect = ResourceExistsError(
        message="Blob already exists"
    )

    with pytest.raises(ResourceExistsError):
        upload_file_to_bronze(source_file)

    mock_blob.upload_blob.assert_called_once()
    mock_blob.download_blob.assert_not_called()
    mock_credential_class.return_value.close.assert_called_once()


@patch(
    "src.bharatpulse.ingestion.azure_storage.BlobServiceClient"
)
@patch(
    "src.bharatpulse.ingestion.azure_storage.DefaultAzureCredential"
)
def test_checksum_mismatch_raises_error(
    mock_credential_class: MagicMock,
    mock_service_class: MagicMock,
    tmp_path: Path,
) -> None:
    """Reject an upload when remote content differs from local content."""
    source_file = tmp_path / "sample.csv"
    source_file.write_bytes(b"state,price\nDelhi,100\n")

    mock_service = mock_service_class.return_value.__enter__.return_value
    mock_blob = mock_service.get_blob_client.return_value
    mock_blob.download_blob.return_value.chunks.return_value = [
        b"state,price\nDelhi,999\n"
    ]

    with pytest.raises(RuntimeError, match="SHA-256 mismatch"):
        upload_file_to_bronze(source_file)

    mock_credential_class.return_value.close.assert_called_once()