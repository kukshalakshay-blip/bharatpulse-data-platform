"""Utilities for ingesting files into Azure Data Lake Storage Gen2."""

from __future__ import annotations

import hashlib
import logging
from pathlib import Path
from typing import Any

from azure.core.exceptions import ResourceExistsError
from azure.identity import DefaultAzureCredential
from azure.storage.blob import BlobServiceClient
from azure.core.exceptions import ResourceExistsError, ResourceNotFoundError


STORAGE_ACCOUNT_NAME = "stbharatpulseakshay01"
FILESYSTEM_NAME = "bharatpulse"
BRONZE_DIRECTORY = "bronze/food_prices"

logger = logging.getLogger(__name__)


def calculate_sha256(file_path: Path) -> str:
    """Calculate a file's SHA-256 checksum without loading it all into memory."""
    checksum = hashlib.sha256()

    with file_path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            checksum.update(chunk)

    return checksum.hexdigest()

def verify_existing_bronze_file(
    local_file_path: str | Path,
    destination_filename: str | None = None,
) -> dict[str, Any] | None:
    """
    Verify an existing Bronze object against a local file.

    Returns None if the object does not exist.
    Returns metadata if the existing object's content matches.
    Raises RuntimeError if the existing object's content differs.
    """
    source_path = Path(local_file_path)

    if not source_path.is_file():
        raise FileNotFoundError(
            f"Source file does not exist: {source_path}"
        )

    filename = destination_filename or source_path.name

    if not filename or Path(filename).name != filename:
        raise ValueError(
            "destination_filename must be a filename, not a path."
        )

    blob_name = f"{BRONZE_DIRECTORY}/{filename}"
    account_url = (
        f"https://{STORAGE_ACCOUNT_NAME}.blob.core.windows.net"
    )

    local_sha256 = calculate_sha256(source_path)
    credential = DefaultAzureCredential()

    try:
        with BlobServiceClient(
            account_url=account_url,
            credential=credential,
        ) as service:
            blob = service.get_blob_client(
                container=FILESYSTEM_NAME,
                blob=blob_name,
            )

            try:
                downloader = blob.download_blob()
            except ResourceNotFoundError:
                logger.info(
                    "Bronze object does not exist: %s",
                    blob_name,
                )
                return None

            remote_sha256 = hashlib.sha256()

            for chunk in downloader.chunks():
                remote_sha256.update(chunk)

            remote_sha256_hex = remote_sha256.hexdigest()

            if local_sha256 != remote_sha256_hex:
                raise RuntimeError(
                    "Bronze content conflict: the existing object "
                    f"does not match the local source: {blob_name}"
                )

            properties = blob.get_blob_properties()

            result = {
                "status": "VERIFIED_EXISTING",
                "source_file": str(source_path.resolve()),
                "destination": f"{FILESYSTEM_NAME}/{blob_name}",
                "size_bytes": properties.size,
                "sha256": remote_sha256_hex,
                "etag": properties.etag,
                "overwrite": False,
            }

            logger.info(
                "Existing Bronze object verified: %s",
                blob_name,
            )

            return result

    finally:
        credential.close()

def upload_file_to_bronze(
    local_file_path: str | Path,
    destination_filename: str | None = None,
    *,
    overwrite: bool = False,
) -> dict[str, Any]:
    """
    Upload a local file to the Bronze layer using Microsoft Entra ID.

    Existing objects are not overwritten unless overwrite=True.
    The SHA-256 checksum is verified against the uploaded object's content.

    Note: overwrite=True is intended for controlled corrections, not
    routine replacement of raw historical data.
    """
    source_path = Path(local_file_path)

    if not source_path.is_file():
        raise FileNotFoundError(f"Source file does not exist: {source_path}")

    filename = destination_filename or source_path.name

    if not filename or Path(filename).name != filename:
        raise ValueError("destination_filename must be a filename, not a path.")

    blob_name = f"{BRONZE_DIRECTORY}/{filename}"
    local_sha256 = calculate_sha256(source_path)
    account_url = f"https://{STORAGE_ACCOUNT_NAME}.blob.core.windows.net"

    credential = DefaultAzureCredential()

    try:
        with BlobServiceClient(
            account_url=account_url,
            credential=credential,
        ) as service:
            blob = service.get_blob_client(
                container=FILESYSTEM_NAME,
                blob=blob_name,
            )

            try:
                with source_path.open("rb") as file:
                    blob.upload_blob(file, overwrite=overwrite)
            except ResourceExistsError:
                logger.warning("Bronze object already exists: %s", blob_name)
                raise

            azure_sha256 = hashlib.sha256()

            downloader = blob.download_blob()
            for chunk in downloader.chunks():
                azure_sha256.update(chunk)

            remote_sha256 = azure_sha256.hexdigest()

            if local_sha256 != remote_sha256:
                logger.error("Checksum mismatch for %s", blob_name)
                raise RuntimeError(
                    f"SHA-256 mismatch after upload: {blob_name}"
                )

            properties = blob.get_blob_properties()

            result = {
                "status": "SUCCESS",
                "source_file": str(source_path.resolve()),
                "destination": f"{FILESYSTEM_NAME}/{blob_name}",
                "size_bytes": properties.size,
                "sha256": local_sha256,
                "etag": properties.etag,
                "overwrite": overwrite,
            }

            logger.info("Bronze upload verified: %s", blob_name)
            return result

    finally:
        credential.close()