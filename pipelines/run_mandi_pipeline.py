"""Orchestrate Bronze ingestion and Silver transformation for Mandi data."""

from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path
from typing import Any

from azure.core.exceptions import ResourceExistsError

from src.bharatpulse.ingestion.azure_storage import upload_file_to_bronze
from src.bharatpulse.transformations.mandi_silver import transform_mandi_csv


logger = logging.getLogger(__name__)


def run_mandi_pipeline(
    input_path: str | Path,
    silver_output_path: str | Path,
) -> dict[str, Any]:
    """
    Run Bronze ingestion followed by Silver transformation.

    The source CSV is preserved. Existing Bronze objects are never
    overwritten by this pipeline.
    """
    source_path = Path(input_path)
    silver_path = Path(silver_output_path)

    if not source_path.is_file():
        raise FileNotFoundError(f"Input CSV not found: {source_path}")

    logger.info("Starting Mandi pipeline for %s", source_path.name)

    # Stage 1: Upload the raw source to Bronze.
    try:
        bronze_result = upload_file_to_bronze(
            local_file_path=source_path,
            overwrite=False,
        )
    except ResourceExistsError:
        logger.info(
            "Bronze object already exists. Verifying existing content."
        )

        # The ingestion function deliberately refuses overwrites.
        # Do not upload again or replace existing raw data.
        # A separate verification function will be added before
        # enabling automatic reuse of existing Bronze objects.
        raise RuntimeError(
            "Bronze object already exists. Pipeline stopped safely; "
            "verify its checksum before rerunning."
        )

    # Stage 2: Transform the local source into Silver.
    silver_result = transform_mandi_csv(
        input_path=source_path,
        output_path=silver_path,
    )

    result = {
        "pipeline": "mandi_prices",
        "status": "SUCCESS",
        "bronze": bronze_result,
        "silver": silver_result,
    }

    logger.info(
        "Mandi pipeline completed successfully: %s",
        source_path.name,
    )

    return result


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run the BharatPulse Mandi Bronze-to-Silver pipeline."
    )

    parser.add_argument(
        "--input",
        required=True,
        help="Path to the original Mandi CSV.",
    )

    parser.add_argument(
        "--silver-output",
        default="data/silver/mandi_prices_silver.csv",
        help="Destination path for the Silver CSV.",
    )

    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Logging verbosity.",
    )

    args = parser.parse_args()

    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    result = run_mandi_pipeline(
        input_path=args.input,
        silver_output_path=args.silver_output,
    )

    print(json.dumps(result, indent=2, default=str))


if __name__ == "__main__":
    main()