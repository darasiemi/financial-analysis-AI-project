import json

import psycopg
from tabulate import tabulate

from ingestion.processing.database import (
    get_postgres_connection_string,
    load_environment,
)

TABLE_ID = (
    "gtco_2023_gtco_2023_annual_report_p0008_table_01_235a65a8eb578fda"
)


def main() -> None:
    # Load .env
    load_environment()

    # Build PostgreSQL connection string from environment variables
    conn = psycopg.connect(
        get_postgres_connection_string()
    )

    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT raw_table_json
            FROM financial_analysis.report_tables
            WHERE table_id = %s
            """,
            (TABLE_ID,),
        )

        row = cur.fetchone()

    conn.close()

    if row is None:
        raise ValueError(
            f"Table '{TABLE_ID}' not found."
        )

    raw_table_json = row[0]

    # Handle both TEXT and JSONB columns.
    if isinstance(raw_table_json, str):
        table = json.loads(raw_table_json)
    else:
        table = raw_table_json

    print(
        tabulate(
            table[1:],
            headers=table[0],
            tablefmt="github",
        )
    )


if __name__ == "__main__":
    main()