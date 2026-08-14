import psycopg

from ingestion.processing.database import (
    get_postgres_connection_string,
)
from monitoring.database import ensure_monitoring_schema


def test_monitoring_schema_can_be_created() -> None:
    ensure_monitoring_schema()


def test_postgres_connection() -> None:
    connection_string = get_postgres_connection_string()

    with psycopg.connect(connection_string) as connection:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1;")

            result = cursor.fetchone()

    assert result == (1,)
