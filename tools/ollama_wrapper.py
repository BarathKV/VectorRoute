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

class OllamaLogger:
    def __init__(self, db_path: str = LOG_DB_PATH):
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Table for ask sessions
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS ask_sessions (
                ask_id TEXT PRIMARY KEY,
                user_input TEXT,
                start_time TIMESTAMP,
                parameters TEXT
            )
        ''')
        
        # Table for individual ollama calls
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS ollama_calls (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ask_id TEXT,
                model TEXT,
                messages TEXT,
                tools TEXT,
                response TEXT,
                timestamp TIMESTAMP,
                FOREIGN KEY (ask_id) REFERENCES ask_sessions (ask_id)
            )
        ''')
        conn.commit()
        conn.close()

    def log_ask_session(self, ask_id: str, user_input: str, parameters: Dict[str, Any]):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute(
            "INSERT OR REPLACE INTO ask_sessions (ask_id, user_input, start_time, parameters) VALUES (?, ?, ?, ?)",
            (ask_id, user_input, datetime.now().isoformat(), json.dumps(parameters))
        )
        conn.commit()
        conn.close()

    def log_call(self, ask_id: Optional[str], model: str, messages: List[Dict], tools: Optional[List], response: Any):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Convert response to dict if it's an ollama.ChatResponse or similar
        resp_data = response
        if not isinstance(response, (dict, str)):
            try:
                resp_data = dict(response)
            except:
                resp_data = str(response)

        cursor.execute(
            "INSERT INTO ollama_calls (ask_id, model, messages, tools, response, timestamp) VALUES (?, ?, ?, ?, ?, ?)",
            (
                ask_id,
                model,
                json.dumps(messages),
                json.dumps(tools) if tools else None,
                json.dumps(resp_data),
                datetime.now().isoformat()
            )
        )
        conn.commit()
        conn.close()

logger = OllamaLogger()

def chat_wrapper(model: str, messages: List[Dict], tools: Optional[List] = None, **kwargs):
    """Wrapper for ollama.chat that logs the request and response."""
    ask_id = current_ask_id.get()
    
    # Call the original ollama.chat
    response = ollama.chat(model=model, messages=messages, tools=tools, **kwargs)
    
    # Log the interaction
    logger.log_call(ask_id, model, messages, tools, response)
    
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
