import psycopg

from ingestion.processing.database import (
    get_postgres_connection_string,
    load_environment,
)


def get_table(
    table_id: str,
) -> dict:
    """
    Retrieve the original structured JSON for an extracted table.

    Args:
        table_id:
            Source ID of a table returned by retrieval.

    Returns:
        Structured financial table and metadata.
    """

    try:
        load_environment()

        connection_string = get_postgres_connection_string()

        with psycopg.connect(connection_string) as connection:

            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT
                        table_id,
                        report_id,
                        ticker,
                        report_year,
                        pdf_page_number,
                        table_index,
                        table_title,
                        table_data
                    FROM financial_analysis.report_tables
                    WHERE table_id = %s
                    """,
                    (table_id,),
                )

                row = cursor.fetchone()

        if row is None:
            return {
                "success": False,
                "found": False,
                "error": (f"Table '{table_id}' " "was not found."),
            }

        (
            table_id,
            report_id,
            ticker,
            report_year,
            page_number,
            table_index,
            table_title,
            table_data,
        ) = row

        return {
            "success": True,
            "found": True,
            "table_id": table_id,
            "report_id": report_id,
            "ticker": ticker,
            "report_year": report_year,
            "pdf_page_number": (page_number),
            "table_index": table_index,
            "table_title": table_title,
            "table_data": table_data,
        }

    except Exception as exc:
        return {
            "success": False,
            "found": False,
            "error_type": (type(exc).__name__),
            "error": str(exc),
        }
