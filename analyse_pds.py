"""analyse_pds.py

Compare two CSV exports (from convert_db_pd.py) and produce a dataframe of per-call differences.

The script expects two CSV files and will:
- Read both files into pandas
- For each `ask_id` present in both files, order calls by `timestamp` and pair them in order
- If one side has more calls for an `ask_id`, the extras are ignored
- For each paired call produce a row with: `ask_id`, `user_query`, `call_id_a`, `call_id_b`, and differences for the numeric fields

Numeric difference columns produced (a - b):
- total_duration
- load_duration
- prompt_eval_count
- prompt_eval_duration
- eval_count
- eval_duration

Usage:
  python analyse_pds.py --a file_a.csv --b file_b.csv --out diffs.csv

Supports output formats: csv, parquet, json, pkl
"""
import argparse
import os
import sys
from typing import List

try:
    import pandas as pd
except Exception:
    print("ERROR: pandas is required. Install with `pip install pandas pyarrow` for parquet support.")
    raise


NUM_FIELDS = [
    'total_duration',
    'load_duration',
    'prompt_eval_count',
    'prompt_eval_duration',
    'eval_count',
    'eval_duration',
]


def infer_column(df: pd.DataFrame, candidates: List[str]) -> str:
    for c in candidates:
        if c in df.columns:
            return c
    return None


def standardize_df(df: pd.DataFrame) -> pd.DataFrame:
    # Keep original columns; but ensure lowercase column names for matching
    df = df.copy()
    df.columns = [c.strip() for c in df.columns]
    return df


def to_datetime_safe(series: pd.Series):
    try:
        return pd.to_datetime(series)
    except Exception:
        return series


def pair_and_diff(df_a: pd.DataFrame, df_b: pd.DataFrame) -> pd.DataFrame:
    # Identify columns
    ask_col = infer_column(df_a, ['ask_id', 'askId', 'ask id']) or infer_column(df_b, ['ask_id', 'askId', 'ask id'])
    if not ask_col:
        raise RuntimeError('Could not find ask_id column in either input')

    user_col = infer_column(df_a, ['user_input', 'user_query', 'user']) or infer_column(df_b, ['user_input', 'user_query', 'user'])

    id_col = infer_column(df_a, ['id', 'call_id']) or infer_column(df_b, ['id', 'call_id'])

    ts_col = infer_column(df_a, ['timestamp', 'created_at', 'start_time']) or infer_column(df_b, ['timestamp', 'created_at', 'start_time'])

    # Ensure timestamp parsing
    if ts_col:
        df_a[ts_col] = to_datetime_safe(df_a[ts_col])
        df_b[ts_col] = to_datetime_safe(df_b[ts_col])

    rows = []

    ask_ids = set(df_a[ask_col].dropna().unique()) & set(df_b[ask_col].dropna().unique())

    for ask in sorted(ask_ids):
        ga = df_a[df_a[ask_col] == ask]
        gb = df_b[df_b[ask_col] == ask]

        if ts_col:
            try:
                ga = ga.sort_values(by=ts_col)
                gb = gb.sort_values(by=ts_col)
            except Exception:
                pass

        na = len(ga)
        nb = len(gb)
        n = min(na, nb)
        if n == 0:
            continue

        # Resolve user query value
        user_val = None
        if user_col and user_col in ga.columns and not ga[user_col].isnull().all():
            user_val = ga[user_col].iloc[0]
        elif user_col and user_col in gb.columns and not gb[user_col].isnull().all():
            user_val = gb[user_col].iloc[0]

        # Iterate paired calls
        for i in range(n):
            ra = ga.iloc[i]
            rb = gb.iloc[i]

            call_id_a = ra[id_col] if id_col in ga.columns else None
            call_id_b = rb[id_col] if id_col in gb.columns else None

            row = {
                'ask_id': ask,
                'user_query': user_val,
                'call_id_a': call_id_a,
                'call_id_b': call_id_b,
            }

            for f in NUM_FIELDS:
                va = ra[f] if f in ga.columns else None
                vb = rb[f] if f in gb.columns else None

                # Try to coerce numeric
                try:
                    va_num = pd.to_numeric(va)
                except Exception:
                    va_num = None
                try:
                    vb_num = pd.to_numeric(vb)
                except Exception:
                    vb_num = None

                diff = None
                if pd.notna(va_num) and pd.notna(vb_num):
                    diff = va_num - vb_num

                row[f'diff_{f}'] = diff
                row[f'a_{f}'] = va_num if pd.notna(va_num) else None
                row[f'b_{f}'] = vb_num if pd.notna(vb_num) else None

            rows.append(row)

    out_df = pd.DataFrame(rows)
    return out_df


def save_df(df: pd.DataFrame, out_path: str):
    ext = os.path.splitext(out_path)[1].lower().lstrip('.')
    if ext == 'csv':
        df.to_csv(out_path, index=False)
    elif ext in ('parquet', 'pq'):
        df.to_parquet(out_path, index=False)
    elif ext in ('pkl', 'pickle'):
        df.to_pickle(out_path)
    elif ext == 'json':
        df.to_json(out_path, orient='records', lines=True)
    else:
        raise ValueError(f"Unsupported output extension: {ext}. Use csv, parquet, pkl, or json")


def main(path_a: str, path_b: str, out: str):
    if not os.path.exists(path_a):
        raise FileNotFoundError(path_a)
    if not os.path.exists(path_b):
        raise FileNotFoundError(path_b)

    df_a = pd.read_csv(path_a)
    df_b = pd.read_csv(path_b)

    df_a = standardize_df(df_a)
    df_b = standardize_df(df_b)

    result = pair_and_diff(df_a, df_b)

    save_df(result, out)
    print(f"Saved {len(result)} diff rows to {out}")


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Compare two CSVs of ollama calls and produce per-call differences')
    parser.add_argument('--a', required=True, help='First CSV file path')
    parser.add_argument('--b', required=True, help='Second CSV file path')
    parser.add_argument('--out', '-o', required=True, help='Output file path (csv, parquet, json, pkl)')
    args = parser.parse_args()
    try:
        main(args.a, args.b, args.out)
    except Exception as e:
        print(f"ERROR: {e}")
        sys.exit(1)
