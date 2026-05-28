import streamlit as st
import requests
import pandas as pd
import uuid
from datetime import datetime

API_URL = "http://localhost:8000"
CONSOLE_PASSWORD = "admin"

st.set_page_config(page_title="Elara Console", page_icon="🧠", layout="centered", initial_sidebar_state="collapsed")

st.markdown("""
    <style>
    .block-container { padding-top: 1.5rem; padding-bottom: 1rem; }
    </style>
""", unsafe_allow_html=True)

# --- SECURITY GATE ---
if "authenticated" not in st.session_state:
    st.session_state.authenticated = False

if not st.session_state.authenticated:
    st.title("🔒 Elara Console Secured")
    pwd = st.text_input("Enter Access Code:", type="password")
    if st.button("Unlock Dashboard", type="primary", use_container_width=True):
        if pwd == CONSOLE_PASSWORD:
            st.session_state.authenticated = True
            st.rerun()
        else:
            st.error("Access Denied.")
    st.stop()
# ---------------------

st.title("🧠 Elara Console")

def fetch_memories():
    try:
        response = requests.get(f"{API_URL}/api/memories", timeout=5)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException:
        return None

memories = fetch_memories()

if memories is None:
    st.error("🚨 **Backend Connection Lost.** Elara's core database is currently unreachable.")
    if st.button("🔄 Retry Connection", use_container_width=True):
        st.rerun()
elif "items" in memories:
    total_mems = len(memories["items"])
    
    col1, col2 = st.columns([1, 1])
    with col1:
        st.metric("Total Memories", total_mems)
    with col2:
        if st.button("🔄 Refresh Data", use_container_width=True):
            # Forcibly clear the browser cache so stuck empty rows disappear
            if "memory_editor" in st.session_state:
                del st.session_state["memory_editor"]
            st.rerun()
            
    if total_mems > 0:
        df = pd.DataFrame(memories["items"])
        
        if 'tags' not in df.columns:
            df['tags'] = ""
        df['tags'] = df['tags'].fillna("")
            
        df['created_at'] = pd.to_datetime(df['created_at'], errors='coerce')
        df['updated_at'] = pd.to_datetime(df['updated_at'], errors='coerce')
        df = df[['text', 'tags', 'created_at', 'updated_at', 'id']]

        st.caption("🔍 Search via the magnifying glass. ➕ Add new memories at the bottom.")

        # Bind the table to the "memory_editor" session key
        edited_df = st.data_editor(
            df,
            use_container_width=True,
            hide_index=True,
            num_rows="dynamic",
            key="memory_editor", 
            disabled=["created_at", "updated_at", "id"], 
            column_config={
                "text": st.column_config.TextColumn("Memory Log", width="large", required=True),
                "tags": st.column_config.TextColumn("Tags (e.g., lore, system)", width="medium"),
                "created_at": None, 
                "updated_at": None,
                "id": None 
            },
            height=450 
        )
        
        # --- SMART SAVE BUTTON LOGIC ---
        # Only show the button if the session state detects active modifications
        has_changes = False
        if "memory_editor" in st.session_state:
            changes = st.session_state["memory_editor"]
            if changes["edited_rows"] or changes["added_rows"] or changes["deleted_rows"]:
                has_changes = True

        if has_changes:
            if st.button("💾 Save All Changes", type="primary", use_container_width=True):
                with st.spinner("Syncing to database..."):
                    
                    # Safety check: Auto-delete any totally blank rows so they don't corrupt the JSON
                    edited_df['text'] = edited_df['text'].fillna("")
                    edited_df = edited_df[edited_df['text'].str.strip() != ""]
                    
                    edited_df['id'] = edited_df['id'].apply(lambda x: str(uuid.uuid4()).replace('-', '') if pd.isna(x) or str(x).strip() == "" else x)
                    
                    edited_df['created_at'] = edited_df['created_at'].fillna(pd.Timestamp.utcnow())
                    edited_df['updated_at'] = pd.Timestamp.utcnow()
                    
                    edited_df['created_at'] = pd.to_datetime(edited_df['created_at']).dt.strftime('%Y-%m-%dT%H:%M:%S.%f')
                    edited_df['updated_at'] = pd.to_datetime(edited_df['updated_at']).dt.strftime('%Y-%m-%dT%H:%M:%S.%f')
                    
                    new_data = {"items": edited_df.to_dict(orient="records")}
                    
                    try:
                        requests.post(f"{API_URL}/api/memories/write", json=new_data, timeout=5)
                        
                        # Wipe the session cache and reload the page so the button vanishes
                        del st.session_state["memory_editor"]
                        st.rerun()
                    except Exception as e:
                        st.error(f"❌ Failed to save: {e}")
    else:
        st.info("No memories logged yet.")
