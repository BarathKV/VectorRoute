import json
import sqlite3
import os
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional
import ollama
from contextvars import ContextVar

# Context variable to store the current ask_id across the call stack
current_ask_id: ContextVar[Optional[str]] = ContextVar("current_ask_id", default=None)

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOG_DB_PATH = os.path.join(BASE_DIR, "io", "ollama_logs.db")


def make_serializable(obj):
    """Recursively convert Ollama return objects/messages to serializable dicts."""
    if isinstance(obj, dict):
        return {k: make_serializable(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [make_serializable(i) for i in obj]
    elif hasattr(obj, "model_dump"):  # For Pydantic-based Ollama objects
        return make_serializable(obj.model_dump())
    elif hasattr(obj, "__dict__"):
        return make_serializable(vars(obj))
    elif hasattr(obj, "message"):  # Handle ChatResponse directly if needed
        return make_serializable(dict(obj))
    else:
        try:
            json.dumps(obj)
            return obj
        except TypeError:
            return str(obj)


class OllamaLogger:
    def __init__(self, db_path: str = LOG_DB_PATH):
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        # Table for ask sessions
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS ask_sessions (
                ask_id TEXT PRIMARY KEY,
                user_input TEXT,
                start_time TIMESTAMP,
                parameters TEXT
            )
        """
        )

        # Table for individual ollama calls with separate columns for response fields
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS ollama_calls (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ask_id TEXT,
                model TEXT,
                created_at TEXT,
                done INTEGER,
                done_reason TEXT,
                total_duration INTEGER,
                load_duration INTEGER,
                prompt_eval_count INTEGER,
                prompt_eval_duration INTEGER,
                eval_count INTEGER,
                eval_duration INTEGER,
                reponse_message TEXT,
                messages TEXT,
                tools TEXT,
                timestamp TIMESTAMP,
                FOREIGN KEY (ask_id) REFERENCES ask_sessions (ask_id)
                )
        """
        )
        conn.commit()
        conn.close()

    def log_ask_session(self, ask_id: str, user_input: str, parameters: Dict[str, Any]):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute(
            "INSERT OR REPLACE INTO ask_sessions (ask_id, user_input, start_time, parameters) VALUES (?, ?, ?, ?)",
            (ask_id, user_input, datetime.now().isoformat(), json.dumps(parameters)),
        )
        conn.commit()
        conn.close()

    def log_call(
        self,
        ask_id: Optional[str],
        model: str,
        messages: List[Dict],
        tools: Optional[List],
        response: Any,
    ):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        print(f"\n\nLOGGER DEBUG: Logging call for ask_id: {ask_id}, model: {model}")

        # Robust serialization for input structures
        serializable_messages = make_serializable(messages)
        # serializable_tools = make_serializable(tools) if tools else None
        serializable_tools = []
        try:
            serializable_tools = [
                t.get("function", {}).get("name")
                for t in tools
                if isinstance(t, dict) and isinstance(t.get("function"), dict) and t.get("function", {}).get("name") is not None
            ]
        except Exception:
            serializable_tools = None

        # Extract response as dict and pull specific fields
        serializable_response = response.dict()

        print(f"\n\nLOGGER DEBUG: Serializable response: {serializable_response}")

        # Fields matching the ollama_calls table
        created_at = None
        done = None
        done_reason = None
        total_duration = None
        load_duration = None
        prompt_eval_count = None
        prompt_eval_duration = None
        eval_count = None
        eval_duration = None

        if isinstance(serializable_response, dict):
            created_at = serializable_response.get("created_at")
            done = (
                1
                if serializable_response.get("done")
                else 0 if "done" in serializable_response else None
            )
            done_reason = serializable_response.get("done_reason")
            total_duration = serializable_response.get("total_duration")
            load_duration = serializable_response.get("load_duration")
            prompt_eval_count = serializable_response.get("prompt_eval_count")
            prompt_eval_duration = serializable_response.get("prompt_eval_duration")
            eval_count = serializable_response.get("eval_count")
            eval_duration = serializable_response.get("eval_duration")
            response_message = serializable_response.get("message")

        # Insert only the columns defined in the table schema
        cursor.execute(
            """
                INSERT INTO ollama_calls (ask_id, model, created_at, done, done_reason, total_duration, load_duration, prompt_eval_count, prompt_eval_duration, eval_count, eval_duration, messages, tools, timestamp, reponse_message) 
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                ask_id,
                model,
                created_at,
                done,
                done_reason,
                int(total_duration) if total_duration is not None else None,
                int(load_duration) if load_duration is not None else None,
                int(prompt_eval_count) if prompt_eval_count is not None else None,
                int(prompt_eval_duration) if prompt_eval_duration is not None else None,
                int(eval_count) if eval_count is not None else None,
                int(eval_duration) if eval_duration is not None else None,
                json.dumps(serializable_messages),
                json.dumps(serializable_tools),
                datetime.now().isoformat(),
                json.dumps(response_message) if response_message is not None else None,
            ),
        )
        conn.commit()
        conn.close()


logger = OllamaLogger()


def chat_wrapper(
    model: str, messages: List[Dict], tools: Optional[List] = None, **kwargs
) -> ollama.ChatResponse:
    """Wrapper for ollama.chat that logs the request and response."""
    ask_id = current_ask_id.get()
    print(f"DEBUG: chat_wrapper called with ask_id: {ask_id}")

    # Call the original ollama.chat
    response = ollama.chat(model=model, messages=messages, tools=tools, **kwargs)

    print(f"RESPONSE DEBUG: Received response {response.dict().keys()}")

    # Log the interaction
    try:
        logger.log_call(ask_id, model, messages, tools, response)
        print(f"DEBUG: Logged ollama call for ask_id: {ask_id}")
    except Exception as e:
        print(f"DEBUG: Failed to log ollama call: {e}")

    return response


# Context manager to set the ask_id
class AskSession:
    def __init__(self, user_input: str, **parameters):
        self.ask_id = str(uuid.uuid4())
        self.user_input = user_input
        self.parameters = parameters
        self.token = None

    def __enter__(self):
        self.token = current_ask_id.set(self.ask_id)
        logger.log_ask_session(self.ask_id, self.user_input, self.parameters)
        return self.ask_id

    def __exit__(self, exc_type, exc_val, exc_tb):
        current_ask_id.reset(self.token)
