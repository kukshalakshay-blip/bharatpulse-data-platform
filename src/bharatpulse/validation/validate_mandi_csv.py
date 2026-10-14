import csv 
import sys 
from collections import Counter
from datetime import datetime
from pathlib import Path

EXPECTED_COLUMNS =[
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

PRICE_COLUMNS=[
    "Min_x0020_Price",
    "Max_x0020_Price",
    "Modal_x0020_Price",
]

def validate_csv(file_path:Path)-> None:
    "validate the structure and basic quality of a mandi CSV"

    if not file_path.exists():
        print(f"Error: File not found :{file_path}")
        sys.exit()

    if not file_path.is_file():
        print(f"ERROR:Path is not a file :{file_path}")

        sys.exit()


    print("=" *60)
    print("bharat - mandi data validation")
    print("="*60)

    print(f"\nfile:{file_path.name}")
    print(f"file size  : {file_path.stat().st_size}")

    if file_path.stat().st_size==0:
        print("Fail:the file is empty")

        sys.exit()

    try:
        with file_path.open(
            "r",
            encoding="utf-8-sig",
            newline=""
        )as csv_file:
            reader=csv.DictReader(csv_file)
            actual_columns=reader.fieldnames

            if not actual_columns:

                print("fail:csv headers are missing.")
                sys.exit(1)

                print(f"\nColumns found: {len(actual_columns)}")
            print("Column names:", actual_columns)

            missing_columns = set(EXPECTED_COLUMNS) - set(actual_columns)
            unexpected_columns = set(actual_columns) - set(EXPECTED_COLUMNS)

            if missing_columns:
                print("\nFAIL: Required columns are missing:")
                for column in sorted(missing_columns):
                    print(f"  - {column}")

                sys.exit(1)

            if unexpected_columns:
                print("\nWARNING: Unexpected columns found:")
                for column in sorted(unexpected_columns):
                    print(f"  - {column}")

            rows = list(reader)

    except (OSError, UnicodeError, csv.Error) as error:
        print(f"\nFAIL: Could not read the CSV: {error}")
        sys.exit(1)

    print(f"\nData rows: {len(rows):,}")

    if not rows:
        print("FAIL: No data records were found.")
        sys.exit(1)

    missing_cells = 0
    invalid_dates = 0
    invalid_prices = 0
    invalid_price_ranges = 0
    suspicious_prices = 0

    seen_rows = set()
    duplicate_rows = 0
    date_counts = Counter()

    for row_number, row in enumerate(rows, start=2):
        # Check missing values in the required columns.
        for column in EXPECTED_COLUMNS:
            if not (row.get(column) or "").strip():
                missing_cells += 1

        # Check arrival date format: DD/MM/YYYY.
        date_value = (row.get("Arrival_Date") or "").strip()

        try:
            parsed_date = datetime.strptime(date_value, "%d/%m/%Y")
            date_counts[parsed_date.date()] += 1
        except ValueError:
            invalid_dates += 1

        # Check whether prices are numeric and non-negative.
        prices = {}

        for column in PRICE_COLUMNS:
            value = (row.get(column) or "").strip()

            try:
                price = float(value)

                if price < 0:
                    invalid_prices += 1
                else:
                    prices[column] = price

            except ValueError:
                invalid_prices += 1

        # Check logical consistency of minimum, modal, and maximum prices.
        if len(prices) == len(PRICE_COLUMNS):
            minimum = prices["Min_x0020_Price"]
            maximum = prices["Max_x0020_Price"]
            modal = prices["Modal_x0020_Price"]

            if minimum > maximum or not minimum <= modal <= maximum:
                invalid_price_ranges += 1

            # Flag for review; do not automatically reject.
            if maximum > 100_000:
                suspicious_prices += 1

        # Detect exact duplicate records.
        row_signature = tuple(
            (row.get(column) or "").strip()
            for column in actual_columns
        )

        if row_signature in seen_rows:
            duplicate_rows += 1
        else:
            seen_rows.add(row_signature)

    print("\n" + "-" * 60)
    print("DATA QUALITY RESULTS")
    print("-" * 60)

    print(f"Missing required values: {missing_cells:,}")
    print(f"Duplicate records: {duplicate_rows:,}")
    print(f"Invalid dates: {invalid_dates:,}")
    print(f"Invalid or negative prices: {invalid_prices:,}")
    print(f"Inconsistent price ranges: {invalid_price_ranges:,}")
    print(f"Prices flagged for review: {suspicious_prices:,}")

    print(f"\nDistinct valid dates: {len(date_counts):,}")

    if date_counts:
        earliest_date = min(date_counts)
        latest_date = max(date_counts)

        print(f"Earliest date: {earliest_date}")
        print(f"Latest date: {latest_date}")

    print("\n" + "-" * 60)

    # Warnings require investigation but do not automatically fail
    # this initial validation.
    failed_checks = (
        missing_cells
        + duplicate_rows
        + invalid_dates
        + invalid_prices
        + invalid_price_ranges
    )

    if failed_checks:
        print("RESULT: FAIL — Investigate the data quality issues.")
        sys.exit(1)

    print("RESULT: PASS — All configured validation checks passed.")
    print(
        "Note: A passing result does not establish source completeness "
        "or confirm the business meaning of every value."
    )


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print(
            'Usage: python validate_mandi_csv.py '
            '"path\\to\\your\\mandi_file.csv"'
        )
        sys.exit(1)

    validate_csv(Path(sys.argv[1]))





            


            