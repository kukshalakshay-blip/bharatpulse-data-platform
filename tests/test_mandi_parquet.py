"""Tests for Mandi Silver Parquet transformation."""

import pandas as pd
import pyarrow.parquet as pq

from src.bharatpulse.transformations.mandi_silver import (
    transform_mandi_parquet,
)
from src.bharatpulse.transformations.mandi_silver import (
    prepare_mandi_silver,
    transform_mandi_outputs,
)


def valid_row():
    return {
        "State": "Uttarakhand",
        "District": "Dehradun",
        "Market": "Dehradun",
        "Commodity": "Potato",
        "Variety": "Local",
        "Grade": "FAQ",
        "Arrival_Date": "14/10/2026",
        "Min_x0020_Price": 2000,
        "Max_x0020_Price": 2500,
        "Modal_x0020_Price": 2200,
    }


def test_successful_parquet_transformation(tmp_path):
    input_path = tmp_path / "input.csv"
    output_path = tmp_path / "silver.parquet"

    pd.DataFrame([valid_row(), valid_row()]).to_csv(
        input_path,
        index=False,
    )

    result = transform_mandi_parquet(
        input_path,
        output_path,
    )

    assert result["status"] == "SUCCESS"
    assert result["format"] == "parquet"
    assert result["input_rows"] == 2
    assert result["output_rows"] == 2
    assert output_path.exists()

    output = pd.read_parquet(output_path)

    assert len(output) == 2

    assert list(output.columns) == [
        "state",
        "district",
        "market",
        "commodity",
        "variety",
        "grade",
        "arrival_date",
        "min_price",
        "max_price",
        "modal_price",
        "source_file",
        "processed_at_utc",
        "price_review_required",
    ]

    assert output["state"].iloc[0] == "Uttarakhand"
    assert output["modal_price"].iloc[0] == 2200
    assert output["price_review_required"].dtype == bool


def test_parquet_schema_is_preserved(tmp_path):
    input_path = tmp_path / "input.csv"
    output_path = tmp_path / "silver.parquet"

    pd.DataFrame([valid_row()]).to_csv(
        input_path,
        index=False,
    )

    transform_mandi_parquet(input_path, output_path)

    parquet_file = pq.ParquetFile(output_path)
    schema = parquet_file.schema_arrow

    assert str(schema.field("state").type) == "string"
    assert str(schema.field("arrival_date").type) == "timestamp[ns]"
    assert str(schema.field("price_review_required").type) == "bool"


def test_parquet_suspicious_prices_are_flagged(tmp_path):
    input_path = tmp_path / "input.csv"
    output_path = tmp_path / "silver.parquet"

    row = valid_row()
    row["Max_x0020_Price"] = 150_000
    row["Modal_x0020_Price"] = 100_000

    pd.DataFrame([row]).to_csv(
        input_path,
        index=False,
    )

    result = transform_mandi_parquet(input_path, output_path)

    output = pd.read_parquet(output_path)

    assert result["suspicious_prices"] == 1
    assert output["price_review_required"].iloc[0]


def test_missing_input_file_fails(tmp_path):
    input_path = tmp_path / "missing.csv"
    output_path = tmp_path / "silver.parquet"

    import pytest

    with pytest.raises(FileNotFoundError):
        transform_mandi_parquet(input_path, output_path)

def test_combined_outputs_use_one_preparation_pass(
    tmp_path,
    monkeypatch,
):
    """Generate both formats using one shared preparation pass."""

    input_path = tmp_path / "input.csv"
    csv_path = tmp_path / "silver.csv"
    parquet_path = tmp_path / "silver.parquet"

    pd.DataFrame([valid_row(), valid_row()]).to_csv(
        input_path,
        index=False,
    )

    call_count = 0

    original_prepare = prepare_mandi_silver

    def tracked_prepare(path):
        nonlocal call_count
        call_count += 1
        return original_prepare(path)

    monkeypatch.setattr(
        "src.bharatpulse.transformations.mandi_silver.prepare_mandi_silver",
        tracked_prepare,
    )

    result = transform_mandi_outputs(
        input_path,
        csv_path,
        parquet_path,
    )

    assert call_count == 1
    assert csv_path.exists()
    assert parquet_path.exists()
    assert result["status"] == "SUCCESS"

    csv_data = pd.read_csv(csv_path)
    parquet_data = pd.read_parquet(parquet_path)

    # Normalize calendar dates.
    csv_data["arrival_date"] = pd.to_datetime(
        csv_data["arrival_date"]
    )

    # Normalize UTC timestamps.
    csv_data["processed_at_utc"] = pd.to_datetime(
        csv_data["processed_at_utc"],
        utc=True,
    )

    pd.testing.assert_frame_equal(
        csv_data,
        parquet_data,
        check_dtype=False,
        check_exact=False,
    )

