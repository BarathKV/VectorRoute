import streamlit as st
from agent.agent import Agent
from typing import List
import ollama

from tools.file_tracker import FileTracker


st.set_page_config(page_title="VectorRoute Agent UI")


def init_session_state():
    if "agent" not in st.session_state:
        st.session_state.agent = None
    if "messages" not in st.session_state:
        st.session_state.messages = []
    if "model" not in st.session_state:
        st.session_state.model = "llama3.2:3b"
    if "tool_registry" not in st.session_state:
        st.session_state.tool_registry = {}


def create_agent(model: str) -> Agent:
    return Agent(model=model)


def load_tools_into_session():
    try:
        st.session_state.tool_registry = FileTracker.get_tool_registry()
    except Exception as e:
        st.session_state.tool_registry = {}
        st.error(f"Failed to load tool registry: {e}")


def fetch_available_models() -> List[str]:
    try:
        raw = ollama.list()
        models = raw.get("models", [])
        for model in models:
            print(f"Model: {model}")
    except Exception:
        return []

    # Normalize possible return shapes into an iterable of items
    items = []
    if raw is None:
        return []
    if isinstance(raw, (list, tuple)):
        items = list(raw)
    else:
        # try common attributes
        for attr in ("models", "tags", "results", "data"):
            if hasattr(raw, attr):
                items = list(getattr(raw, attr) or [])
                break
        else:
            try:
                items = list(raw)
            except Exception:
                items = [raw]

    names = []
    for it in items:
        if isinstance(it, str):
            names.append(it)
            continue
        if isinstance(it, dict):
            for key in ("name", "model", "tag", "ref", "id", "label"):
                if key in it and it[key]:
                    names.append(it[key])
                    break
            else:
                names.append(str(it))
            continue
        # pydantic model or object
        for key in ("name", "model", "tag", "ref", "id", "label"):
            val = getattr(it, key, None)
            if val:
                names.append(val)
                break
        else:
            names.append(str(it))

    # dedupe while preserving order
    seen = set()
    out = []
    for n in names:
        if n not in seen:
            seen.add(n)
            out.append(n)
    return out


def main():
    init_session_state()

    st.sidebar.title("Agent Settings")
    models = fetch_available_models()
    refresh_models = st.sidebar.button("Refresh models")
    if refresh_models:
        models = fetch_available_models()

    if models:
        try:
            default_index = models.index(st.session_state.model) if st.session_state.model in models else 0
        except Exception:
            default_index = 0
        model_input = st.sidebar.selectbox("Ollama model", options=models, index=default_index)
    else:
        model_input = st.sidebar.text_input("Ollama model", value=st.session_state.model)

    if st.sidebar.button("Start / Restart Agent"):
        st.session_state.model = model_input.strip() or st.session_state.model
        with st.spinner("Initializing agent..."):
            st.session_state.agent = create_agent(model=st.session_state.model)
        st.success(f"Agent initialized with model {st.session_state.model}")

    # Move Available Tools to the sidebar
    st.sidebar.subheader("Available Tools")
    if st.sidebar.button("Refresh tools"):
        load_tools_into_session()

    tools = list(st.session_state.get("tool_registry", {}).keys())
    if not tools:
        st.sidebar.write("No tools loaded.")
    else:
        for name in sorted(tools):
            st.sidebar.write(f"- {name}")

    st.title("VectorRoute — Agent Chat UI")

    # Chat UI
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    if prompt := st.chat_input("What is up?"):
        # Add user message to chat history
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        # Generate and display assistant response
        with st.chat_message("assistant"):
            if st.session_state.agent is None:
                response = "Please start the agent in the sidebar first."
                st.warning(response)
            else:
                with st.spinner("Thinking..."):
                    try:
                        final_message, tools_used = st.session_state.agent.ask(prompt)
                        # The agent.ask returns a message dict or object
                        if isinstance(final_message, dict):
                            response = final_message.get("content", str(final_message))
                        else:
                            response = getattr(final_message, "content", str(final_message))
                        
                        if tools_used:
                            st.caption(f"Tools used: {', '.join(tools_used)}")
                    except Exception as e:
                        response = f"Error invoking agent: {e}"
                st.markdown(response)

        # Add assistant response to chat history
        st.session_state.messages.append({"role": "assistant", "content": response})


if __name__ == "__main__":
    main()
