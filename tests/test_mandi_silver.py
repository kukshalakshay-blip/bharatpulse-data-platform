import pandas as pd
import pytest

from src.bharatpulse.transformations.mandi_silver import (
    transform_mandi_csv,
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


def write_input_csv(path, rows):
    pd.DataFrame(rows).to_csv(path, index=False)


def test_successful_transformation(tmp_path):
    input_path = tmp_path / "input.csv"
    output_path = tmp_path / "silver.csv"

    write_input_csv(input_path, [valid_row(), valid_row()])

    result = transform_mandi_csv(input_path, output_path)

    assert result["status"] == "SUCCESS"
    assert result["input_rows"] == 2
    assert result["output_rows"] == 2
    assert output_path.exists()

    output = pd.read_csv(output_path)

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
    ]


def test_missing_input_file_fails(tmp_path):
    input_path = tmp_path / "missing.csv"
    output_path = tmp_path / "silver.csv"

    with pytest.raises(FileNotFoundError):
        transform_mandi_csv(input_path, output_path)


def test_missing_required_column_fails(tmp_path):
    input_path = tmp_path / "missing_column.csv"
    output_path = tmp_path / "silver.csv"

    row = valid_row()
    del row["Commodity"]

    write_input_csv(input_path, [row])

    with pytest.raises(ValueError, match="Missing required columns"):
        transform_mandi_csv(input_path, output_path)


def test_invalid_date_fails(tmp_path):
    input_path = tmp_path / "invalid_date.csv"
    output_path = tmp_path / "silver.csv"

    row = valid_row()
    row["Arrival_Date"] = "not-a-date"

    write_input_csv(input_path, [row])

    with pytest.raises(ValueError):
        transform_mandi_csv(input_path, output_path)


def test_negative_price_fails(tmp_path):
    input_path = tmp_path / "negative_price.csv"
    output_path = tmp_path / "silver.csv"

    row = valid_row()
    row["Min_x0020_Price"] = -100

    write_input_csv(input_path, [row])

    with pytest.raises(ValueError, match="Negative prices"):
        transform_mandi_csv(input_path, output_path)


def test_invalid_price_range_fails(tmp_path):
    input_path = tmp_path / "invalid_range.csv"
    output_path = tmp_path / "silver.csv"

    row = valid_row()
    row["Min_x0020_Price"] = 3000
    row["Max_x0020_Price"] = 2500
    row["Modal_x0020_Price"] = 2700

    write_input_csv(input_path, [row])

    with pytest.raises(ValueError, match="Minimum price exceeds maximum price"):
        transform_mandi_csv(input_path, output_path)


def test_original_input_is_preserved(tmp_path):
    input_path = tmp_path / "original.csv"
    output_path = tmp_path / "silver.csv"

    write_input_csv(input_path, [valid_row()])
    original_bytes = input_path.read_bytes()

    transform_mandi_csv(input_path, output_path)

    assert input_path.read_bytes() == original_bytes