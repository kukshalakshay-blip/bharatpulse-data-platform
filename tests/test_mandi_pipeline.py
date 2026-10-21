"""Tests for the Mandi Bronze-to-Silver pipeline."""

from pathlib import Path
from unittest.mock import patch

import pytest
from azure.core.exceptions import ResourceExistsError

from pipelines.run_mandi_pipeline import run_mandi_pipeline


@patch("pipelines.run_mandi_pipeline.transform_mandi_csv")
@patch("pipelines.run_mandi_pipeline.upload_file_to_bronze")
def test_pipeline_runs_bronze_then_silver(
    mock_upload,
    mock_transform,
    tmp_path: Path,
) -> None:
    """Verify that successful Bronze ingestion is followed by Silver."""
    source = tmp_path / "mandi.csv"
    source.write_text("sample", encoding="utf-8")

    silver_output = tmp_path / "silver" / "mandi_silver.csv"

    mock_upload.return_value = {
        "status": "SUCCESS",
        "destination": "bharatpulse/bronze/food_prices/mandi.csv",
    }

    mock_transform.return_value = {
        "status": "SUCCESS",
        "input_rows": 10,
        "output_rows": 10,
    }

    result = run_mandi_pipeline(source, silver_output)

    mock_upload.assert_called_once_with(
        local_file_path=source,
        overwrite=False,
    )
    mock_transform.assert_called_once_with(
        input_path=source,
        output_path=silver_output,
    )

    assert result["status"] == "SUCCESS"
    assert result["bronze"]["status"] == "SUCCESS"
    assert result["silver"]["output_rows"] == 10


@patch("pipelines.run_mandi_pipeline.transform_mandi_csv")
@patch("pipelines.run_mandi_pipeline.upload_file_to_bronze")
def test_existing_bronze_object_stops_pipeline(
    mock_upload,
    mock_transform,
    tmp_path: Path,
) -> None:
    """Do not transform data when Bronze ingestion detects a duplicate."""
    source = tmp_path / "mandi.csv"
    source.write_text("sample", encoding="utf-8")

    mock_upload.side_effect = ResourceExistsError(
        message="Blob already exists"
    )

    with pytest.raises(RuntimeError, match="already exists"):
        run_mandi_pipeline(
            source,
            tmp_path / "silver.csv",
        )

    mock_transform.assert_not_called()


def test_missing_input_stops_pipeline(tmp_path: Path) -> None:
    """Reject a missing input before accessing Azure."""
    with patch(
        "pipelines.run_mandi_pipeline.upload_file_to_bronze"
    ) as mock_upload:
        with pytest.raises(FileNotFoundError):
            run_mandi_pipeline(
                tmp_path / "missing.csv",
                tmp_path / "silver.csv",
            )

        mock_upload.assert_not_called()