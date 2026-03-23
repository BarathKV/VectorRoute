import sqlite3
import os
import json

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
    cursor.execute("SELECT id, ask_id, model, timestamp FROM ollama_calls")
    calls = cursor.fetchall()
    for c in calls:
        print(c)

    conn.close()

if __name__ == "__main__":
    check_logs()
