"""Tests for the Mandi Bronze-to-Silver pipeline."""

from pathlib import Path
from unittest.mock import patch

import pytest
from azure.core.exceptions import ResourceExistsError

from pipelines.run_mandi_pipeline import run_mandi_pipeline


@patch("pipelines.run_mandi_pipeline.transform_mandi_outputs")
@patch("pipelines.run_mandi_pipeline.upload_file_to_bronze")
@patch("pipelines.run_mandi_pipeline.verify_existing_bronze_file")
def test_pipeline_uploads_missing_bronze_then_transforms(
    mock_verify,
    mock_upload,
    mock_transform,
    tmp_path: Path,
) -> None:
    """Upload missing Bronze data and generate both Silver formats."""
    source = tmp_path / "mandi.csv"
    source.write_text("sample", encoding="utf-8")

    silver = tmp_path / "silver.csv"
    parquet = tmp_path / "silver.parquet"

    mock_verify.return_value = None
    mock_upload.return_value = {"status": "SUCCESS"}
    mock_transform.return_value = {"status": "SUCCESS"}

    result = run_mandi_pipeline(
        source,
        silver,
        parquet,
    )

    mock_verify.assert_called_once_with(source)

    mock_upload.assert_called_once_with(
        local_file_path=source,
        overwrite=False,
    )

    mock_transform.assert_called_once_with(
        input_path=source,
        csv_output_path=silver,
        parquet_output_path=parquet,
    )

    assert result["status"] == "SUCCESS"


@patch("pipelines.run_mandi_pipeline.transform_mandi_outputs")
@patch("pipelines.run_mandi_pipeline.upload_file_to_bronze")
@patch("pipelines.run_mandi_pipeline.verify_existing_bronze_file")
def test_pipeline_reuses_verified_bronze_object(
    mock_verify,
    mock_upload,
    mock_transform,
    tmp_path: Path,
) -> None:
    """Reuse matching Bronze data and generate both Silver formats."""
    source = tmp_path / "mandi.csv"
    source.write_text("sample", encoding="utf-8")

    silver = tmp_path / "silver.csv"
    parquet = tmp_path / "silver.parquet"

    mock_verify.return_value = {
        "status": "VERIFIED_EXISTING",
        "sha256": "matching-checksum",
    }

    mock_transform.return_value = {"status": "SUCCESS"}

    result = run_mandi_pipeline(
        source,
        silver,
        parquet,
    )

    mock_verify.assert_called_once_with(source)
    mock_upload.assert_not_called()

    mock_transform.assert_called_once_with(
        input_path=source,
        csv_output_path=silver,
        parquet_output_path=parquet,
    )

    assert result["bronze"]["status"] == "VERIFIED_EXISTING"
    assert result["status"] == "SUCCESS"


@patch("pipelines.run_mandi_pipeline.transform_mandi_outputs")
@patch("pipelines.run_mandi_pipeline.upload_file_to_bronze")
@patch("pipelines.run_mandi_pipeline.verify_existing_bronze_file")
def test_bronze_conflict_stops_pipeline(
    mock_verify,
    mock_upload,
    mock_transform,
    tmp_path: Path,
) -> None:
    """Stop when existing Bronze content differs."""
    source = tmp_path / "mandi.csv"
    source.write_text("sample", encoding="utf-8")

    mock_verify.side_effect = RuntimeError(
        "Bronze content conflict"
    )

    with pytest.raises(RuntimeError, match="Bronze content conflict"):
        run_mandi_pipeline(
            source,
            tmp_path / "silver.csv",
            tmp_path / "silver.parquet",
        )

    mock_upload.assert_not_called()
    mock_transform.assert_not_called()


@patch("pipelines.run_mandi_pipeline.transform_mandi_outputs")
@patch("pipelines.run_mandi_pipeline.upload_file_to_bronze")
@patch("pipelines.run_mandi_pipeline.verify_existing_bronze_file")
def test_pipeline_recovers_from_upload_race(
    mock_verify,
    mock_upload,
    mock_transform,
    tmp_path: Path,
) -> None:
    """Verify and reuse data uploaded by another process."""
    source = tmp_path / "mandi.csv"
    source.write_text("sample", encoding="utf-8")

    silver = tmp_path / "silver.csv"
    parquet = tmp_path / "silver.parquet"

    mock_verify.side_effect = [
        None,
        {
            "status": "VERIFIED_EXISTING",
            "sha256": "matching-checksum",
        },
    ]

    mock_upload.side_effect = ResourceExistsError(
        message="Blob already exists"
    )

    mock_transform.return_value = {"status": "SUCCESS"}

    result = run_mandi_pipeline(
        source,
        silver,
        parquet,
    )

    assert mock_verify.call_count == 2
    mock_upload.assert_called_once()

    mock_transform.assert_called_once_with(
        input_path=source,
        csv_output_path=silver,
        parquet_output_path=parquet,
    )

    assert result["status"] == "SUCCESS"


@patch("pipelines.run_mandi_pipeline.transform_mandi_outputs")
@patch("pipelines.run_mandi_pipeline.upload_file_to_bronze")
@patch("pipelines.run_mandi_pipeline.verify_existing_bronze_file")
def test_upload_race_without_existing_object_stops_pipeline(
    mock_verify,
    mock_upload,
    mock_transform,
    tmp_path: Path,
) -> None:
    """Stop if the object disappears during a race condition."""
    source = tmp_path / "mandi.csv"
    source.write_text("sample", encoding="utf-8")

    mock_verify.side_effect = [None, None]

    mock_upload.side_effect = ResourceExistsError(
        message="Blob already exists"
    )

    with pytest.raises(
        RuntimeError,
        match="disappeared during the upload",
    ):
        run_mandi_pipeline(
            source,
            tmp_path / "silver.csv",
            tmp_path / "silver.parquet",
        )

    mock_transform.assert_not_called()


def test_missing_input_stops_pipeline(tmp_path: Path) -> None:
    """Reject missing source data before accessing Azure."""
    source = tmp_path / "missing.csv"

    with (
        patch(
            "pipelines.run_mandi_pipeline.verify_existing_bronze_file"
        ) as mock_verify,
        patch(
            "pipelines.run_mandi_pipeline.upload_file_to_bronze"
        ) as mock_upload,
        patch(
            "pipelines.run_mandi_pipeline.transform_mandi_outputs"
        ) as mock_transform,
    ):
        with pytest.raises(FileNotFoundError):
            run_mandi_pipeline(
                source,
                tmp_path / "silver.csv",
                tmp_path / "silver.parquet",
            )

    mock_verify.assert_not_called()
    mock_upload.assert_not_called()
    mock_transform.assert_not_called()