from pathlib import Path
from datetime import datetime, timezone

import pandas as pd


SOURCE_TO_SILVER_COLUMNS = {
    "State": "state",
    "District": "district",
    "Market": "market",
    "Commodity": "commodity",
    "Variety": "variety",
    "Grade": "grade",
    "Arrival_Date": "arrival_date",
    "Min_x0020_Price": "min_price",
    "Max_x0020_Price": "max_price",
    "Modal_x0020_Price": "modal_price",
}

STRING_COLUMNS = [
    "state",
    "district",
    "market",
    "commodity",
    "variety",
    "grade",
]

PRICE_COLUMNS = [
    "min_price",
    "max_price",
    "modal_price",
]

SUSPICIOUS_PRICE_THRESHOLD = 100_000

EXPECTED_SILVER_COLUMNS = [
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


def transform_mandi_csv(
    input_path: str | Path,
    output_path: str | Path,
) -> dict:
    """
    Transform the raw Mandi CSV into a standardized Silver CSV.

    The raw source is never modified.

    Adds data lineage and a flag for prices requiring review.

    Returns a summary of the transformation.
    """

    input_path = Path(input_path)
    output_path = Path(output_path)

    if not input_path.is_file():
        raise FileNotFoundError(
            f"Input CSV not found: {input_path}"
        )

    # Read the raw source without modifying it.
    df = pd.read_csv(input_path)
    input_rows = len(df)

    expected_source_columns = list(SOURCE_TO_SILVER_COLUMNS)

    missing_columns = [
        column
        for column in expected_source_columns
        if column not in df.columns
    ]

    if missing_columns:
        raise ValueError(
            f"Missing required columns: {missing_columns}"
        )

    # Select expected columns and rename them.
    # Unexpected source columns are deliberately excluded.
    df = df[expected_source_columns].rename(
        columns=SOURCE_TO_SILVER_COLUMNS
    )

    # Standardize text columns.
    for column in STRING_COLUMNS:
        df[column] = (
            df[column]
            .astype("string")
            .str.strip()
        )

    # Convert dates explicitly.
    df["arrival_date"] = pd.to_datetime(
        df["arrival_date"],
        format="%d/%m/%Y",
        errors="raise",
    )

    # Convert prices to numeric types.
    for column in PRICE_COLUMNS:
        df[column] = pd.to_numeric(
            df[column],
            errors="raise",
        )

    # Fail rather than silently writing invalid business values.
    if df[PRICE_COLUMNS].isna().any().any():
        raise ValueError(
            "Missing price values detected during transformation."
        )

    if (df[PRICE_COLUMNS] < 0).any().any():
        raise ValueError(
            "Negative prices detected during transformation."
        )

    if (df["min_price"] > df["max_price"]).any():
        raise ValueError(
            "Minimum price exceeds maximum price."
        )

    if (
        (df["modal_price"] < df["min_price"])
        | (df["modal_price"] > df["max_price"])
    ).any():
        raise ValueError(
            "Modal price falls outside the minimum/maximum range."
        )

    # Add data lineage.
    df["source_file"] = input_path.name

    df["processed_at_utc"] = (
        datetime.now(timezone.utc).isoformat()
    )

    # Flag unusually high prices for review.
    # A flag does not automatically mean a price is incorrect.
    df["price_review_required"] = (
        df["max_price"] > SUSPICIOUS_PRICE_THRESHOLD
    )

    # Enforce the Silver schema and column order.
    if list(df.columns) != EXPECTED_SILVER_COLUMNS:
        raise ValueError(
            f"Unexpected Silver schema: {list(df.columns)}"
        )

    # Create the output directory if necessary.
    output_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    # Write the Silver output.
    df.to_csv(
        output_path,
        index=False,
        date_format="%Y-%m-%d",
    )

    # Return a processing summary.
    return {
        "input_file": input_path.name,
        "output_file": str(output_path),
        "input_rows": input_rows,
        "output_rows": len(df),
        "output_columns": list(df.columns),
        "suspicious_prices": int(
            df["price_review_required"].sum()
        ),
        "status": "SUCCESS",
    }