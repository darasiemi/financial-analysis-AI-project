from __future__ import annotations

from tabulate import tabulate
import psycopg

from ingestion.processing.database import (
    get_postgres_connection_string,
    load_environment,
)


TABLE_ID = (
    "gtco_2023_gtco_2023_annual_report_p0008_table_02_0dfa571f014fa921"
)


def main() -> None:
    load_environment()

    connection_string = (
        get_postgres_connection_string()
    )

    with psycopg.connect(
        connection_string
    ) as conn:

        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT table_data
                FROM financial_analysis.report_tables
                WHERE table_id = %s
                """,
                (TABLE_ID,),
            )

            row = cur.fetchone()

    if row is None:
        raise ValueError(
            f"Table '{TABLE_ID}' not found."
        )

    table_data = row[0]

    if not isinstance(
        table_data,
        dict,
    ):
        raise TypeError(
            "table_data was expected to be a JSON object."
        )

    headers = table_data.get(
        "headers",
        [],
    )

    rows = table_data.get(
        "rows",
        [],
    )

    if not headers:
        raise ValueError(
            "No headers found in table_data."
        )

    if not rows:
        raise ValueError(
            "No rows found in table_data."
        )

    # Convert JSON row dictionaries back into ordered
    # lists using the stored header order.
    display_rows = [
        [
            row_data.get(
                header,
                "",
            )
            for header in headers
        ]
        for row_data in rows
    ]

    print(
        tabulate(
            display_rows,
            headers=headers,
            tablefmt="github",
        )
    )


if __name__ == "__main__":
    main()