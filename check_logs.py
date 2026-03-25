import sqlite3
import os
import json
from datetime import datetime

import argparse

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "io", "ollama_logs.db")

def check_logs():
    if not os.path.exists(DB_PATH):
        print(f"Database not found at {DB_PATH}")
        return

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    print("--- Ask Sessions ---")
    cursor.execute("SELECT * FROM ask_sessions")
    sessions = cursor.fetchall()
    print(f"Total ask_sessions: {len(sessions)}")
    # for s in sessions:
    #     print(s)

    print("\n--- Ollama Calls ---")
    cursor.execute("SELECT * FROM ollama_calls")
    calls = cursor.fetchall()
    print(f"Total ollama_calls: {len(calls)}")
    # for c in calls:
    #     print(c)

    conn.close()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Check logs in the SQLite database.")
    parser.add_argument("--clear", action="store_true", help="Clear all logs from the database.")
    parser.add_argument("--populate", action="store_true", help="Populate DB with sample sessions and calls.")
    args = parser.parse_args()

    if args.clear:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("DELETE FROM ask_sessions");
        cursor.execute("DELETE FROM ollama_calls");
        conn.commit()
        conn.close()
    if args.populate:
        # Create sample ask_sessions and ollama_calls
        def _ensure_tables():
            conn = sqlite3.connect(DB_PATH)
            cursor = conn.cursor()
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS ask_sessions (
                    ask_id TEXT PRIMARY KEY,
                    user_input TEXT,
                    start_time TIMESTAMP,
                    parameters TEXT
                )
            ''')
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS ollama_calls (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    ask_id TEXT,
                    model TEXT,
                    messages TEXT,
                    tools TEXT,
                    response_text TEXT,
                    created_at TEXT,
                    done INTEGER,
                    context TEXT,
                    total_duration INTEGER,
                    load_duration INTEGER,
                    prompt_eval_count INTEGER,
                    prompt_eval_duration INTEGER,
                    eval_count INTEGER,
                    eval_duration INTEGER,
                    timestamp TIMESTAMP,
                    FOREIGN KEY (ask_id) REFERENCES ask_sessions (ask_id)
                )
            ''')
            conn.commit()
            conn.close()

        def _ensure_table_columns(table_name: str, columns: dict):
            """Ensure the given columns exist on `table_name`, adding them if missing."""
            conn = sqlite3.connect(DB_PATH)
            cursor = conn.cursor()
            cursor.execute(f"PRAGMA table_info({table_name})")
            existing = {row[1] for row in cursor.fetchall()}  # name is at index 1
            for col, col_type in columns.items():
                if col not in existing:
                    try:
                        cursor.execute(f"ALTER TABLE {table_name} ADD COLUMN {col} {col_type}")
                    except Exception:
                        # best-effort: ignore if alter fails for any reason
                        pass
            conn.commit()
            conn.close()

        def populate_ask_sessions(num_sessions: int = 100):
            """Insert `num_sessions` rows into `ask_sessions` with predictable ask_ids."""
            _ensure_tables()
            conn = sqlite3.connect(DB_PATH)
            cursor = conn.cursor()
            for i in range(num_sessions):
                ask_id = f"seed-session-{i:04d}"
                user_input = f"seed user input {i}"
                start_time = datetime.now().isoformat()
                parameters = json.dumps({"seed": True, "index": i})
                cursor.execute(
                    "INSERT OR REPLACE INTO ask_sessions (ask_id, user_input, start_time, parameters) VALUES (?, ?, ?, ?)",
                    (ask_id, user_input, start_time, parameters),
                )
            conn.commit()
            conn.close()

        def populate_ollama_calls(total_calls: int = 200):
            """Insert `total_calls` rows into `ollama_calls` such that every two rows share the same ask_id.

            If there are not enough sessions present, this will create the required sessions.
            """
            if total_calls % 2 != 0:
                raise ValueError("total_calls must be an even number")

            pairs_needed = total_calls // 2
            _ensure_tables()
            # Ensure required columns exist in ollama_calls to avoid INSERT failures
            required_columns = {
                "response_text": "TEXT",
                "created_at": "TEXT",
                "done": "INTEGER",
                "context": "TEXT",
                "total_duration": "INTEGER",
                "load_duration": "INTEGER",
                "prompt_eval_count": "INTEGER",
                "prompt_eval_duration": "INTEGER",
                "eval_count": "INTEGER",
                "eval_duration": "INTEGER",
                "timestamp": "TEXT",
            }
            _ensure_table_columns("ollama_calls", required_columns)
            conn = sqlite3.connect(DB_PATH)
            cursor = conn.cursor()

            cursor.execute("SELECT ask_id FROM ask_sessions ORDER BY ask_id")
            existing = [r[0] for r in cursor.fetchall()]

            if len(existing) < pairs_needed:
                # create the missing sessions
                populate_ask_sessions(pairs_needed)
                cursor.execute("SELECT ask_id FROM ask_sessions ORDER BY ask_id")
                existing = [r[0] for r in cursor.fetchall()]

            chosen = existing[:pairs_needed]

            for ask_id in chosen:
                for j in range(2):
                    model = "seed-model"
                    messages = json.dumps([{"role": "user", "content": f"call {j} for {ask_id}"}])
                    tools = None
                    response_text = f"seed response for {ask_id} ({j})"
                    created_at = datetime.now().isoformat()
                    done = 1
                    context = json.dumps({"seed": True})
                    cursor.execute(
                        "INSERT INTO ollama_calls (ask_id, model, messages, tools, response_text, created_at, done, context, total_duration, load_duration, prompt_eval_count, prompt_eval_duration, eval_count, eval_duration, timestamp) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                        (
                            ask_id,
                            model,
                            messages,
                            json.dumps(tools) if tools is not None else None,
                            response_text,
                            created_at,
                            done,
                            context,
                            None,
                            None,
                            None,
                            None,
                            None,
                            None,
                            datetime.now().isoformat(),
                        ),
                    )

            conn.commit()
            conn.close()

        # Default behaviour: create 100 sessions and 200 calls (2 calls per session)
        populate_ask_sessions(100)
        populate_ollama_calls(200)
        print(f"Populated {DB_PATH} with 100 ask_sessions and 200 ollama_calls")
    check_logs()
