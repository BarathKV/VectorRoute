"""convert_db_pd.py

Read ollama sqlite DB into pandas DataFrame and save to disk.

Usage examples:
  python convert_db_pd.py --out output.parquet
  python convert_db_pd.py --db path/to/ollama_logs.db --out data.csv

Supported output formats: csv, parquet, json, pkl
If the DB contains `ollama_calls` and `ask_sessions`, they will be merged on `ask_id`.
"""
import argparse
import os
import sqlite3
import sys
from typing import Optional

try:
    import pandas as pd
except Exception as e:
    print("ERROR: pandas is required. Install with `pip install pandas pyarrow` for parquet support.")
    raise


def default_db_path() -> str:
    # Default to repo-root/io/ollama_logs.db
    root = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(root, "io", "ollama_logs.db")


def list_tables(conn: sqlite3.Connection):
    cur = conn.cursor()
    cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
    return [r[0] for r in cur.fetchall()]


def read_table(conn: sqlite3.Connection, table: str) -> pd.DataFrame:
    return pd.read_sql_query(f"SELECT * FROM {table}", conn)


def merge_tables(calls: pd.DataFrame, sessions: pd.DataFrame) -> pd.DataFrame:
    if 'ask_id' in calls.columns and 'ask_id' in sessions.columns:
        return calls.merge(sessions, on='ask_id', how='left', suffixes=("", "_session"))
    return calls


def save_df(df: pd.DataFrame, out_path: str):
    ext = os.path.splitext(out_path)[1].lower().lstrip('.')
    if ext == 'csv':
        df.to_csv(out_path, index=False)
    elif ext in ('parquet', 'pq'):
        # parquet requires pyarrow or fastparquet
        df.to_parquet(out_path, index=False)
    elif ext in ('pkl', 'pickle'):
        df.to_pickle(out_path)
    elif ext == 'json':
        df.to_json(out_path, orient='records', lines=True)
    else:
        raise ValueError(f"Unsupported output extension: {ext}. Use csv, parquet, pkl, or json")


def main(db: str, out: str):
    if not os.path.exists(db):
        raise FileNotFoundError(f"DB not found: {db}")

    conn = sqlite3.connect(db)
    try:
        tables = list_tables(conn)

        if 'ollama_calls' in tables:
            df_calls = read_table(conn, 'ollama_calls')
        else:
            # If no standard table, try to pick the first table
            if not tables:
                raise RuntimeError("No tables found in DB")
            df_calls = read_table(conn, tables[0])

        if 'ask_sessions' in tables:
            df_sessions = read_table(conn, 'ask_sessions')
            df = merge_tables(df_calls, df_sessions)
        else:
            df = df_calls

        # Attempt to deserialize JSON columns if present
        for col in ['messages', 'tools', 'context']:
            if col in df.columns:
                try:
                    df[col] = df[col].apply(lambda v: pd.io.json.loads(v) if isinstance(v, str) else v)
                except Exception:
                    pass

        save_df(df, out)
        print(f"Saved DataFrame with {len(df)} rows to {out}")
    finally:
        conn.close()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Convert ollama sqlite DB to pandas DataFrame and save to file')
    parser.add_argument('--db', '-d', default=default_db_path(), help='Path to sqlite DB (default: repo io/ollama_logs.db)')
    parser.add_argument('--out', '-o', required=True, help='Output file path (csv, parquet, json, pkl)')
    args = parser.parse_args()
    try:
        main(args.db, args.out)
    except Exception as e:
        print(f"ERROR: {e}")
        sys.exit(1)
