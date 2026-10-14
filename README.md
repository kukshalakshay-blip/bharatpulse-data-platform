# BharatPulse

An India-focused food-price intelligence and supply-chain risk data platform.

## Objective

Build an end-to-end data engineering platform that ingests public data,
validates and transforms it, stores reliable analytical tables, and supports
investigation of commodity-price movements and regional market patterns.

## Planned Technology Stack

- Python
- SQL
- Azure Data Lake Storage Gen2
- Azure Databricks
- Apache Spark and PySpark
- Delta Lake
- Azure Data Factory
- Azure Key Vault
- Power BI
- Git and GitHub

## Architecture

The platform will progressively implement a medallion-style architecture:

- Bronze: Raw ingested data
- Silver: Validated and standardized data
- Gold: Analytics-ready datasets

## Project Status

Initial development and environment setup.

## Data Integrity

Publicly observed data and simulated test data will be identified separately.
Analytical findings will be limited to what the available evidence supports.
