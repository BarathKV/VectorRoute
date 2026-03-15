import streamlit as st
from agent.agent import Agent
from typing import List, Dict
import ollama
from tools.tool_registry import update_tool_registry
import time


st.set_page_config(page_title="VectorRoute Agent UI")


def init_session_state():
    if "agent" not in st.session_state:
        st.session_state.agent = None
    if "history" not in st.session_state:
        st.session_state.history = []
    if "model" not in st.session_state:
        st.session_state.model = "llama3.2:3b"
    if "tool_registry" not in st.session_state:
        st.session_state.tool_registry = {}


def create_agent(model: str) -> Agent:
    return Agent(model=model)


def add_message(role: str, content: str, tools: List[str] = None):
    st.session_state.history.append({"role": role, "content": content, "tools": tools or []})


def render_history(container):
    for entry in st.session_state.history:
        role = entry.get("role", "user")
        content = entry.get("content", "")
        tools = entry.get("tools", [])

        if role == "user":
            container.markdown(f"**You:** {content}")
        else:
            container.markdown(f"**Agent:** {content}")
            if tools:
                container.markdown(f"- **Tools used:** {', '.join(tools)}")


def load_tools_into_session():
    try:
        st.session_state.tool_registry = update_tool_registry()
    except Exception as e:
        st.session_state.tool_registry = {}
        st.error(f"Failed to load tool registry: {e}")


def fetch_available_models() -> List[str]:
    try:
        raw = ollama.list()
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
    if "messages" not in st.session_state:
        st.session_state.messages = []

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
            with st.spinner("Thinking..."):
                try:
                    response, tools_used = st.session_state.agent.run_better(prompt)
                    print(type(response))
                    print(f"\n\nFull agent response: {dict(response)}")
                    response = dict(response)['content']
                    print(f"\n\nAgent response: {response}, Tools used: {tools_used}")
                except Exception as e:
                    response = f"Error invoking agent: {e}"
                st.markdown(response)

        # Add assistant response to chat history
        st.session_state.messages.append({"role": "assistant", "content": response})


    # # Two-column layout: main chat area + right-side tools panel
    # col_main, col_tools = st.columns([3, 1])

    # with col_main:
    #     if st.session_state.agent is None:
    #         st.info("Agent not initialized. Use the sidebar to start the agent.")
    #     else:
    #         with st.form(key="chat_form", clear_on_submit=True):
    #             user_input = st.text_input("Your message", key="input_text")
    #             submitted = st.form_submit_button("Send")

    #         if submitted and user_input:
    #             add_message("user", user_input)
    #             with st.spinner("Agent thinking..."):
    #                 try:
    #                     response, tools_used = st.session_state.agent.run_better(user_input)
    #                     print(f"Agent response: {response}, Tools used: {tools_used}")
    #                 except Exception as e:
    #                     add_message("agent", f"Error invoking agent: {e}")
    #                 else:
    #                     # response may be a dict-like message per agent.run_better
    #                     content = ""
    #                     if isinstance(response, dict):
    #                         content = response.get("content", str(response))
    #                     else:
    #                         content = str(response)

    #                     add_message("agent", content, tools_used)

    #         render_history(col_main)


if __name__ == "__main__":
    main()
