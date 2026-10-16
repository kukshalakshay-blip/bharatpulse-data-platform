import csv

from src.bharatpulse.validation.validate_mandi_csv import (
    EXPECTED_COLUMNS,
    validate_csv,
)


def write_csv(path, rows, columns=None):
    """Create a small CSV fixture for testing."""

    columns = columns or EXPECTED_COLUMNS

    with path.open(
        "w",
        encoding="utf-8",
        newline="",
    ) as csv_file:
        writer = csv.DictWriter(
            csv_file,
            fieldnames=columns,
        )
        writer.writeheader()
        writer.writerows(rows)


def valid_row():
    """Return one valid example Mandi record."""

    return {
        "State": "Uttarakhand",
        "District": "Dehradun",
        "Market": "Dehradun",
        "Commodity": "Potato",
        "Variety": "Local",
        "Grade": "FAQ",
        "Arrival_Date": "14/10/2026",
        "Min_x0020_Price": "2000",
        "Max_x0020_Price": "2500",
        "Modal_x0020_Price": "2200",
    }


def test_valid_csv_passes(tmp_path):
    csv_path = tmp_path / "valid.csv"
    write_csv(csv_path, [valid_row()])

    report = validate_csv(csv_path)

    assert report["status"] == "PASS"
    assert report["row_count"] == 1
    assert report["invalid_dates"] == 0
    assert report["invalid_prices"] == 0


def test_missing_required_column_fails(tmp_path):
    csv_path = tmp_path / "missing_column.csv"

    columns = [
        column
        for column in EXPECTED_COLUMNS
        if column != "Commodity"
    ]

    row = valid_row()
    row.pop("Commodity")

    write_csv(csv_path, [row], columns)

    report = validate_csv(csv_path)

    assert report["status"] == "FAIL"
    assert "Commodity" in report["missing_columns"]


def test_invalid_date_is_detected(tmp_path):
    csv_path = tmp_path / "invalid_date.csv"
    row = valid_row()
    row["Arrival_Date"] = "not-a-date"

    write_csv(csv_path, [row])

    report = validate_csv(csv_path)

    assert report["status"] == "FAIL"
    assert report["invalid_dates"] == 1


def test_negative_price_is_detected(tmp_path):
    csv_path = tmp_path / "negative_price.csv"
    row = valid_row()
    row["Min_x0020_Price"] = "-100"

    write_csv(csv_path, [row])

    report = validate_csv(csv_path)

    assert report["status"] == "FAIL"
    assert report["invalid_prices"] == 1


def test_duplicate_records_are_detected(tmp_path):
    csv_path = tmp_path / "duplicates.csv"
    row = valid_row()

    write_csv(csv_path, [row, row])

    report = validate_csv(csv_path)

    assert report["status"] == "FAIL"
    assert report["duplicate_rows"] == 1


def test_missing_file_fails(tmp_path):
    csv_path = tmp_path / "does_not_exist.csv"

    report = validate_csv(csv_path)

    assert report["status"] == "FAIL"
    assert any("File not found" in error for error in report["errors"])