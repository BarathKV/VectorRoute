import sqlite3
import os
import json

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
    for s in sessions:
        print(s)

    print("\n--- Ollama Calls ---")
    cursor.execute("SELECT * FROM ollama_calls")
    calls = cursor.fetchall()
    for c in calls:
        print(c)

    conn.close()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Check logs in the SQLite database.")
    parser.add_argument("--clear", action="store_true", help="Clear all logs from the database.")
    args = parser.parse_args()

    if args.clear:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("DELETE FROM ask_sessions");
        cursor.execute("DELETE FROM ollama_calls");
        conn.commit()
        conn.close()
    check_logs()
