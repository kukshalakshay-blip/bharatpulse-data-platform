import csv
import json
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path


EXPECTED_COLUMNS = [
    "State",
    "District",
    "Market",
    "Commodity",
    "Variety",
    "Grade",
    "Arrival_Date",
    "Min_x0020_Price",
    "Max_x0020_Price",
    "Modal_x0020_Price",
]

PRICE_COLUMNS = [
    "Min_x0020_Price",
    "Max_x0020_Price",
    "Modal_x0020_Price",
]

SUSPICIOUS_PRICE_THRESHOLD = 100_000


def validate_csv(file_path: Path) -> dict:
    """Validate a Mandi CSV and return a structured quality report."""

    file_path = Path(file_path)

    report = {
        "file_name": file_path.name,
        "file_size_bytes": 0,
        "row_count": 0,
        "columns": [],
        "missing_columns": [],
        "unexpected_columns": [],
        "missing_cells": 0,
        "duplicate_rows": 0,
        "invalid_dates": 0,
        "invalid_prices": 0,
        "invalid_price_ranges": 0,
        "suspicious_prices": 0,
        "distinct_valid_dates": 0,
        "earliest_date": None,
        "latest_date": None,
        "errors": [],
        "status": "FAIL",
    }

    if not file_path.exists():
        report["errors"].append(f"File not found: {file_path}")
        return report

    if not file_path.is_file():
        report["errors"].append(f"Path is not a file: {file_path}")
        return report

    report["file_size_bytes"] = file_path.stat().st_size

    if report["file_size_bytes"] == 0:
        report["errors"].append("The file is empty.")
        return report

    try:
        with file_path.open(
            "r",
            encoding="utf-8-sig",
            newline="",
        ) as csv_file:
            reader = csv.DictReader(csv_file)

            actual_columns = reader.fieldnames

            if not actual_columns:
                report["errors"].append("CSV headers are missing.")
                return report

            report["columns"] = actual_columns

            report["missing_columns"] = sorted(
                set(EXPECTED_COLUMNS) - set(actual_columns)
            )
            report["unexpected_columns"] = sorted(
                set(actual_columns) - set(EXPECTED_COLUMNS)
            )

            if report["missing_columns"]:
                report["errors"].append(
                    "One or more required columns are missing."
                )
                return report

            rows = list(reader)

    except (OSError, UnicodeError, csv.Error) as error:
        report["errors"].append(f"Could not read CSV: {error}")
        return report

    report["row_count"] = len(rows)

    if not rows:
        report["errors"].append("No data records were found.")
        return report

    seen_rows = set()
    date_counts = Counter()

    for row in rows:
        # DictReader uses the None key for extra fields.
        # Missing fields appear as None under their column names.
        if None in row:
            report["errors"].append(
                "At least one row contains more fields than the header."
            )

        for column in EXPECTED_COLUMNS:
            value = row.get(column)

            if value is None or not value.strip():
                report["missing_cells"] += 1

        date_value = (row.get("Arrival_Date") or "").strip()

        try:
            parsed_date = datetime.strptime(
                date_value,
                "%d/%m/%Y",
            )
            date_counts[parsed_date.date()] += 1
        except ValueError:
            report["invalid_dates"] += 1

        prices = {}

        for column in PRICE_COLUMNS:
            value = row.get(column)

            try:
                if value is None or not value.strip():
                    raise ValueError("Missing price")

                price = float(value)

                if not price >= 0 or price == float("inf"):
                    raise ValueError("Invalid price")

                if price != price:  # NaN is not equal to itself.
                    raise ValueError("Invalid price")

                prices[column] = price

            except (ValueError, TypeError):
                report["invalid_prices"] += 1

        if len(prices) == len(PRICE_COLUMNS):
            minimum = prices["Min_x0020_Price"]
            maximum = prices["Max_x0020_Price"]
            modal = prices["Modal_x0020_Price"]

            if minimum > maximum or not minimum <= modal <= maximum:
                report["invalid_price_ranges"] += 1

            if maximum > SUSPICIOUS_PRICE_THRESHOLD:
                report["suspicious_prices"] += 1

        row_signature = tuple(
            row.get(column) for column in actual_columns
        )

        if row_signature in seen_rows:
            report["duplicate_rows"] += 1
        else:
            seen_rows.add(row_signature)

    if date_counts:
        report["distinct_valid_dates"] = len(date_counts)
        report["earliest_date"] = str(min(date_counts))
        report["latest_date"] = str(max(date_counts))

    if any(row.get(None) is not None for row in rows):
        report["errors"].append(
            "At least one row contains extra fields."
        )

    if any(
        row.get(column) is None
        for row in rows
        for column in EXPECTED_COLUMNS
    ):
        report["errors"].append(
            "At least one row has fewer fields than expected."
        )

    failed_checks = (
        report["missing_cells"]
        + report["duplicate_rows"]
        + report["invalid_dates"]
        + report["invalid_prices"]
        + report["invalid_price_ranges"]
    )

    if not failed_checks and not report["errors"]:
        report["status"] = "PASS"

    return report


def print_report(report: dict) -> None:
    """Print the validation report in a readable format."""

    print("=" * 60)
    print("BHARATPULSE — MANDI DATA VALIDATION")
    print("=" * 60)

    print(f"\nFile: {report['file_name']}")
    print(f"File size: {report['file_size_bytes']:,} bytes")
    print(f"Data rows: {report['row_count']:,}")
    print(f"Columns found: {len(report['columns'])}")

    print("\nDATA QUALITY RESULTS")
    print("-" * 60)

    for field in [
        "missing_cells",
        "duplicate_rows",
        "invalid_dates",
        "invalid_prices",
        "invalid_price_ranges",
        "suspicious_prices",
        "distinct_valid_dates",
    ]:
        print(f"{field.replace('_', ' ').title()}: {report[field]:,}")

    print(f"Earliest date: {report['earliest_date']}")
    print(f"Latest date: {report['latest_date']}")

    if report["missing_columns"]:
        print(f"Missing columns: {report['missing_columns']}")

    if report["unexpected_columns"]:
        print(f"Unexpected columns: {report['unexpected_columns']}")

    if report["errors"]:
        print("\nERRORS")
        for error in report["errors"]:
            print(f"- {error}")

    print(f"\nRESULT: {report['status']}")


def main() -> int:
    """Run validation from the command line."""

    if len(sys.argv) not in (2, 3):
        print(
            'Usage: python validate_mandi_csv.py '
            '"path\\to\\your\\mandi_file.csv" [report.json]'
        )
        return 2

    file_path = Path(sys.argv[1])
    report = validate_csv(file_path)
    print_report(report)

    if len(sys.argv) == 3:
        report_path = Path(sys.argv[2])

        try:
            report_path.write_text(
                json.dumps(report, indent=2),
                encoding="utf-8",
            )
            print(f"\nJSON report saved to: {report_path}")
        except OSError as error:
            print(f"\nCould not save JSON report: {error}")
            return 2

    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())