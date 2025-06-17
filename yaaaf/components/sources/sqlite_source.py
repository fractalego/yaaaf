import sqlite3
import pandas as pd

from yaaaf.components.sources.base_source import BaseSource


class SqliteSource(BaseSource):
    def __init__(self, name: str, db_path: str):
        super().__init__(name)
        self.db_path = db_path

    def get_data(self, query: str) -> pd.DataFrame:
        conn = sqlite3.connect(self.db_path)
        try:
            return pd.read_sql_query(query, conn)
        except (ValueError, pd.errors.DatabaseError) as e:
            return pd.DataFrame.from_dict(
                {
                    "Errors": [f"Error in executing SQL query: {e}"],
                    "Results": ["There are no results"],
                }
            )

    def get_description(self) -> str:
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        tables = cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table';"
        ).fetchall()
        markdown_schema: str = ""
        for table_name in tables:
            table_name = table_name[0].replace(" ", "_")
            table = pd.read_sql_query(f"SELECT * FROM {table_name} LIMIT 1", conn)
            table_columns = [item.replace(" ", "_") for item in table.columns.tolist()]
            markdown_schema += f"# Columns for the table called {table_name} are:\n{table_columns}\n\n\n"
        cursor.close()
        conn.close()
        return markdown_schema

    def ingest(
        self, df: pd.DataFrame, table_name: str, if_exists: str = "replace"
    ) -> None:
        conn = sqlite3.connect(self.db_path)
        df.columns = [col.replace(" ", "_") for col in df.columns]
        df.to_sql(table_name, conn, if_exists=if_exists, index=False)
        conn.close()
