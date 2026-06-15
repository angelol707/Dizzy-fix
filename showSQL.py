import argparse
import getpass
import sys
from typing import Optional
import mysql.connector
import pandas as pd


def run_query(query: str, host: str, port: int, user: str, password: str, database: Optional[str]):
    """Execute a SQL query against MySQL and return the result as a pandas DataFrame."""
    connection = mysql.connector.connect(
        host=host,
        port=port,
        user=user,
        password=password,
        database=database,
    )
    try:
        return pd.read_sql(query, connection)
    finally:
        connection.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Run a MySQL query and visualize the result using pandas."
    )
    parser.add_argument("sql", nargs="?", help="The SQL statement to execute.")
    parser.add_argument(
        "--host",
        default="localhost",
        help="MySQL host (default: localhost).",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=3306,
        help="MySQL port (default: 3306).",
    )
    parser.add_argument(
        "--user",
        default="root",
        help="MySQL user name (default: root).",
    )
    parser.add_argument(
        "--password",
        help="MySQL password. If omitted, prompts securely when running interactively.",
    )
    parser.add_argument(
        "--database",
        default="Cybersickness",
        help="MySQL database name. If omitted, the connection is established without a default database.",
    )
    parser.add_argument(
        "--head",
        type=int,
        default=25,
        help="Print only the first N rows of the result (default: 25).",
    )
    parser.add_argument(
        "--max-columns",
        type=int,
        default=20,
        help="Maximum number of columns to display in the console output (default: 20).",
    )
    parser.add_argument(
        "--csv",
        help="Write query results to a CSV file.",
    )
    args = parser.parse_args()

    sql = args.sql
    if sql is None:
        if sys.stdin.isatty():
            sql = input("Enter SQL statement: ").strip()
            if not sql:
                parser.error("No SQL provided.")
        else:
            sql = sys.stdin.read().strip()
            if not sql:
                parser.error("No SQL provided on stdin.")

    password = args.password
    if password is None and sys.stdin.isatty():
        password = getpass.getpass("MySQL password: ")

    df = run_query(sql, args.host, args.port, args.user, password or "", args.database)

    if df.empty:
        print("Query returned no rows.")
    else:
        with pd.option_context(
            "display.max_rows", args.head,
            "display.max_columns", args.max_columns,
            "display.width", None,
        ):
            print(df.head(args.head))

    if args.csv:
        df.to_csv(args.csv, index=False)
        print(f"Wrote {len(df)} rows to {args.csv}")
