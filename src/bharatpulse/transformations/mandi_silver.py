"""Transform raw Mandi data into standardized Silver datasets."""

from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

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


def prepare_mandi_silver(
    input_path: str | Path,
) -> tuple[pd.DataFrame, dict]:
    """Read, validate, standardize and enrich raw Mandi data."""

    input_path = Path(input_path)

    if not input_path.is_file():
        raise FileNotFoundError(
            f"Input CSV not found: {input_path}"
        )

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

    # Select and standardize source columns.
    df = df[expected_source_columns].rename(
        columns=SOURCE_TO_SILVER_COLUMNS
    )

    # Standardize string columns.
    for column in STRING_COLUMNS:
        df[column] = (
            df[column]
            .astype("string")
            .str.strip()
        )

    # Parse dates.
    df["arrival_date"] = pd.to_datetime(
        df["arrival_date"],
        format="%d/%m/%Y",
        errors="raise",
    )

    # Convert price columns to numeric values.
    for column in PRICE_COLUMNS:
        df[column] = pd.to_numeric(
            df[column],
            errors="raise",
        )

    # Validate business rules.
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

    df["processed_at_utc"] = pd.Timestamp.now(
        tz="UTC"
    )

    # Flag unusually high prices.
    df["price_review_required"] = (
        df["max_price"] > SUSPICIOUS_PRICE_THRESHOLD
    )

    # Enforce the Silver schema.
    if list(df.columns) != EXPECTED_SILVER_COLUMNS:
        raise ValueError(
            f"Unexpected Silver schema: {list(df.columns)}"
        )

    metadata = {
        "input_file": input_path.name,
        "input_rows": input_rows,
        "output_rows": len(df),
        "output_columns": list(df.columns),
        "suspicious_prices": int(
            df["price_review_required"].sum()
        ),
    }

    return df, metadata

def write_silver_csv(
    df: pd.DataFrame,
    output_path: Path,
) -> None:
    """Write Silver CSV while preserving date and timestamp semantics."""

    csv_df = df.copy()

    # Store calendar dates without a time component.
    csv_df["arrival_date"] = (
        csv_df["arrival_date"].dt.strftime("%Y-%m-%d")
    )

    # Preserve the complete UTC processing timestamp.
    csv_df.to_csv(
        output_path,
        index=False,
    )

def transform_mandi_csv(
    input_path: str | Path,
    output_path: str | Path,
) -> dict:
    """Transform raw Mandi CSV into standardized Silver CSV."""

    output_path = Path(output_path)

    df, metadata = prepare_mandi_silver(input_path)

    output_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    write_silver_csv(df, output_path)

    return {
        **metadata,
        "output_file": str(output_path),
        "status": "SUCCESS",
    }


def transform_mandi_parquet(
    input_path: str | Path,
    output_path: str | Path,
    *,
    compression: Literal["snappy", "gzip", "brotli", "lz4", "zstd"] = "snappy",
) -> dict:
    """Transform raw Mandi CSV into standardized Silver Parquet."""

    output_path = Path(output_path)

    df, metadata = prepare_mandi_silver(input_path)

    output_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    df.to_parquet(
        output_path,
        engine="pyarrow",
        compression=compression,
        index=False,
    )

    return {
        **metadata,
        "output_file": str(output_path),
        "format": "parquet",
        "compression": compression,
        "status": "SUCCESS",
    }

def transform_mandi_outputs(
    input_path: str | Path,
    csv_output_path: str | Path,
    parquet_output_path: str | Path,
    *,
    compression: Literal["snappy", "gzip", "brotli", "lz4", "zstd"] = "snappy",
) -> dict:
    """Generate CSV and Parquet from the same prepared DataFrame."""

    csv_output_path = Path(csv_output_path)
    parquet_output_path = Path(parquet_output_path)

    df, metadata = prepare_mandi_silver(input_path)

    # Create output directories.
    csv_output_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    parquet_output_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    # Write CSV.
    write_silver_csv(df, csv_output_path)

    # Write Parquet.
    df.to_parquet(
        parquet_output_path,
        engine="pyarrow",
        compression=compression,
        index=False,
    )

    return {
        **metadata,
        "csv": {
            "output_file": str(csv_output_path),
            "status": "SUCCESS",
        },
        "parquet": {
            "output_file": str(parquet_output_path),
            "compression": compression,
            "status": "SUCCESS",
        },
        "status": "SUCCESS",
    }