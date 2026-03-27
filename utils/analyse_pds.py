import argparse
import os
import sys
from typing import List
import numpy as np

try:
    import pandas as pd
except Exception:
    print("ERROR: pandas is required. Install with `pip install pandas pyarrow` for parquet support.")
    raise

# Fields to analyze
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
    df = df.copy()
    df.columns = [c.strip() for c in df.columns]
    return df

def to_datetime_safe(series: pd.Series):
    try:
        return pd.to_datetime(series)
    except Exception:
        return series

def pair_and_diff(df_classical: pd.DataFrame, df_custom: pd.DataFrame) -> pd.DataFrame:
    # Identify key columns
    ask_col = infer_column(df_classical, ['ask_id', 'askId', 'ask id']) or infer_column(df_custom, ['ask_id', 'askId', 'ask id'])
    if not ask_col:
        raise RuntimeError('Could not find ask_id column in either input')

    user_col = infer_column(df_classical, ['user_input', 'user_query', 'user']) or infer_column(df_custom, ['user_input', 'user_query', 'user'])
    id_col = infer_column(df_classical, ['id', 'call_id']) or infer_column(df_custom, ['id', 'call_id'])
    ts_col = infer_column(df_classical, ['timestamp', 'created_at', 'start_time']) or infer_column(df_custom, ['timestamp', 'created_at', 'start_time'])

    if ts_col:
        df_classical[ts_col] = to_datetime_safe(df_classical[ts_col])
        df_custom[ts_col] = to_datetime_safe(df_custom[ts_col])

    rows = []
    # Intersection of IDs
    ask_ids = set(df_classical[ask_col].dropna().unique()) & set(df_custom[ask_col].dropna().unique())

    for ask in sorted(ask_ids):
        ga = df_classical[df_classical[ask_col] == ask]
        gb = df_custom[df_custom[ask_col] == ask]

        if ts_col:
            try:
                ga = ga.sort_values(by=ts_col)
                gb = gb.sort_values(by=ts_col)
            except Exception:
                pass

        n = min(len(ga), len(gb))
        if n == 0: continue

        user_val = None
        if user_col and user_col in ga.columns and not ga[user_col].isnull().all():
            user_val = ga[user_col].iloc[0]

        for i in range(n):
            ra = ga.iloc[i] # Classical
            rb = gb.iloc[i] # Custom

            row = {
                'ask_id': ask,
                'user_query': user_val,
                'call_id_classical': ra[id_col] if id_col in ga.columns else None,
                'call_id_custom': rb[id_col] if id_col in gb.columns else None,
            }

            for f in NUM_FIELDS:
                v_class = pd.to_numeric(ra[f]) if f in ga.columns else np.nan
                v_cust = pd.to_numeric(rb[f]) if f in gb.columns else np.nan

                diff = v_cust - v_class
                
                # Percentage Difference: (Custom - Classical) / Classical
                if pd.notna(v_class) and pd.notna(v_cust) and v_class != 0:
                    pct_diff = (diff / v_class) * 100
                else:
                    pct_diff = None

                row[f'classical_{f}'] = v_class
                row[f'custom_{f}'] = v_cust
                row[f'diff_{f}'] = diff
                row[f'pct_change_{f}'] = pct_diff

            rows.append(row)

    return pd.DataFrame(rows)

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
        raise ValueError(f"Unsupported extension: {ext}")

def main(path_classical: str, path_custom: str, out: str):
    df_a = pd.read_csv(path_classical)
    df_b = pd.read_csv(path_custom)

    df_a = standardize_df(df_a)
    df_b = standardize_df(df_b)

    result = pair_and_diff(df_a, df_b)
    save_df(result, out)
    
    print(f"--- Comparison Summary ---")
    print(f"Classical: {path_classical}")
    print(f"Custom:    {path_custom}")
    print(f"Total Paired Calls: {len(result)}")
    if not result.empty:
        avg_speedup = result['pct_change_total_duration'].mean()
        print(f"Avg Total Duration Change: {avg_speedup:.2f}%")

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Compare Classical vs Custom Ollama performance.')
    parser.add_argument('--classical', required=True, help='Path to Classical CSV')
    parser.add_argument('--custom', required=True, help='Path to Custom CSV')
    parser.add_argument('--out', '-o', required=True, help='Output path')
    args = parser.parse_args()
    
    try:
        main(args.classical, args.custom, args.out)
    except Exception as e:
        print(f"ERROR: {e}")
        sys.exit(1)