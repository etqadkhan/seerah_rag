"""
Seerah Q&A - Main Streamlit Application

A RAG-powered Q&A application for learning about the Seerah (biography)
of Prophet Muhammad ﷺ using Yasir Qadhi's comprehensive lecture series.

Features:
- User authentication (register/login)
- Conversation history with memory
- Source citations with video timestamps
- Multiple chat sessions per user

Run with: streamlit run app.py
"""

import streamlit as st
from pathlib import Path
import sys

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from config.settings import GEMINI_API_KEY
from core.auth_manager import AuthManager, require_auth
from core.chat_memory import ChatMemory, SessionManager
from core.retriever import SeerahRetriever, format_sources_for_display


# ============================================================================
# Page Configuration
# ============================================================================

st.set_page_config(
    page_title="Seerah Q&A",
    page_icon="🕌",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for better styling
st.markdown("""
<style>
    /* Main container styling */
    .main .block-container {
        padding-top: 2rem;
        padding-bottom: 2rem;
    }
    
    /* Chat message styling */
    .stChatMessage {
        padding: 1rem;
        border-radius: 0.5rem;
    }
    
    /* Source citation styling */
    .source-citation {
        background-color: #f0f2f6;
        padding: 0.5rem 1rem;
        border-radius: 0.25rem;
        margin-top: 0.5rem;
        font-size: 0.85rem;
    }
    
    /* Sidebar styling */
    .css-1d391kg {
        padding-top: 1rem;
    }
    
    /* Session button styling */
    .session-button {
        width: 100%;
        text-align: left;
        padding: 0.5rem;
        margin-bottom: 0.25rem;
    }
    
    /* Header styling */
    .app-header {
        text-align: center;
        padding: 1rem 0;
        border-bottom: 1px solid #e0e0e0;
        margin-bottom: 1rem;
    }
    
    /* Footer styling */
    .app-footer {
        text-align: center;
        color: #666;
        font-size: 0.8rem;
        padding: 1rem 0;
        border-top: 1px solid #e0e0e0;
        margin-top: 2rem;
    }
</style>
""", unsafe_allow_html=True)


# ============================================================================
# Initialize Components
# ============================================================================

@st.cache_resource
def get_auth_manager():
    """Get cached AuthManager instance."""
    return AuthManager()


@st.cache_resource
def get_retriever():
    """Get cached SeerahRetriever instance."""
    return SeerahRetriever()


def init_session_state():
    """Initialize all session state variables."""
    AuthManager.init_session_state()
    
    if 'messages' not in st.session_state:
        st.session_state.messages = []
    
    if 'current_session_id' not in st.session_state:
        st.session_state.current_session_id = None


# ============================================================================
# Sidebar Components
# ============================================================================

def render_sidebar():
    """Render the sidebar with session management."""
    with st.sidebar:
        # User info and logout
        st.markdown(f"### 👤 {st.session_state.username}")
        
        if st.button("🚪 Logout", use_container_width=True):
            AuthManager.logout_user()
            st.rerun()
        
        st.markdown("---")
        
        # New chat button
        if st.button("➕ New Chat", use_container_width=True, type="primary"):
            create_new_session()
        
        st.markdown("---")
        st.markdown("### 📜 Chat History")
        
        # List user's sessions
        user_id = st.session_state.user_id
        session_manager = SessionManager(user_id)
        sessions = session_manager.get_all_sessions(limit=20)
        
        for session in sessions:
            # Highlight current session
            is_current = session.id == st.session_state.current_session_id
            
            col1, col2 = st.columns([5, 1])
            
            with col1:
                button_type = "primary" if is_current else "secondary"
                if st.button(
                    f"💬 {session.title[:30]}...",
                    key=f"session_{session.id}",
                    use_container_width=True,
                    type=button_type
                ):
                    switch_session(session.id)
            
            with col2:
                if st.button("🗑️", key=f"delete_{session.id}"):
                    if session_manager.delete_session(session.id):
                        if st.session_state.current_session_id == session.id:
                            st.session_state.current_session_id = None
                            st.session_state.messages = []
                        st.rerun()
        
        # Info section
        st.markdown("---")
        st.markdown("### ℹ️ About")
        st.markdown(
            "This Q&A uses **Yasir Qadhi's Seerah** lecture series "
            "(104 videos) as its knowledge base."
        )
        
        # Check knowledge base status
        retriever = get_retriever()
        if retriever.is_ready():
            st.success("✅ Knowledge base ready")
        else:
            st.warning("⚠️ Knowledge base not initialized. Run the setup first.")


def create_new_session():
    """Create a new chat session."""
    user_id = st.session_state.user_id
    session_manager = SessionManager(user_id)
    session = session_manager.create_session("New Chat")
    st.session_state.current_session_id = session.id
    st.session_state.messages = []
    st.rerun()


def switch_session(session_id: int):
    """Switch to a different chat session."""
    if st.session_state.current_session_id != session_id:
        st.session_state.current_session_id = session_id
        # Load messages for this session
        memory = ChatMemory(session_id)
        st.session_state.messages = memory.format_messages_for_display()
        st.rerun()


def ensure_session_exists():
    """Ensure user has at least one session."""
    if st.session_state.current_session_id is None:
        user_id = st.session_state.user_id
        session_manager = SessionManager(user_id)
        
        # Get existing or create new
        sessions = session_manager.get_all_sessions(limit=1)
        if sessions:
            st.session_state.current_session_id = sessions[0].id
            memory = ChatMemory(sessions[0].id)
            st.session_state.messages = memory.format_messages_for_display()
        else:
            session = session_manager.create_session("New Chat")
            st.session_state.current_session_id = session.id
            st.session_state.messages = []


# ============================================================================
# Chat Interface
# ============================================================================

def render_chat_interface():
    """Render the main chat interface."""
    st.markdown("## 🕌 Seerah Q&A")
    st.markdown(
        "*Ask questions about the life of Prophet Muhammad ﷺ*"
    )
    
    # Check if knowledge base is ready
    retriever = get_retriever()
    if not retriever.is_ready():
        st.warning(
            "⚠️ **Knowledge base not initialized!**\n\n"
            "Please run the data pipeline first:\n"
            "```bash\n"
            "python -m data_pipeline.transcript_fetcher\n"
            "python -m data_pipeline.knowledge_base\n"
            "```"
        )
        return
    
    # Display chat messages
    for message in st.session_state.messages:
        with st.chat_message(message['role']):
            st.markdown(message['content'])
            
            # Show sources for assistant messages
            if message['role'] == 'assistant' and message.get('sources'):
                with st.expander("📚 View Sources"):
                    for source in message['sources']:
                        st.markdown(
                            f"- [{source['title']}]({source['youtube_link']}) "
                            f"(Lecture {source['playlist_index']})"
                        )
    
    # Chat input
    if prompt := st.chat_input("Ask about the Seerah..."):
        process_user_query(prompt)


def process_user_query(query: str):
    """Process a user's query and generate response."""
    session_id = st.session_state.current_session_id
    
    # Display user message
    st.session_state.messages.append({
        'role': 'user',
        'content': query,
        'sources': None
    })
    
    with st.chat_message("user"):
        st.markdown(query)
    
    # Generate response
    with st.chat_message("assistant"):
        with st.spinner("Thinking..."):
            try:
                retriever = get_retriever()
                response = retriever.query_with_memory(
                    query=query,
                    session_id=session_id
                )
                
                # Display response
                st.markdown(response.answer)
                
                # Display sources
                if response.sources:
                    with st.expander("📚 View Sources"):
                        for source in response.sources:
                            st.markdown(
                                f"- [{source.title}]({source.youtube_link}) "
                                f"(Lecture {source.playlist_index})"
                            )
                
                # Update session state
                st.session_state.messages.append({
                    'role': 'assistant',
                    'content': response.answer,
                    'sources': [s.to_dict() for s in response.sources]
                })
                
                # Auto-title session if this is the first message
                if len(st.session_state.messages) == 2:  # First Q&A pair
                    user_id = st.session_state.user_id
                    session_manager = SessionManager(user_id)
                    session_manager.auto_title_session(session_id, query)
                
            except Exception as e:
                error_msg = f"Sorry, I encountered an error: {str(e)}"
                st.error(error_msg)
                st.session_state.messages.append({
                    'role': 'assistant',
                    'content': error_msg,
                    'sources': None
                })


# ============================================================================
# Main Application
# ============================================================================

def main():
    """Main application entry point."""
    # Check for API key
    if not GEMINI_API_KEY:
        st.error(
            "⚠️ **GEMINI_API_KEY not set!**\n\n"
            "Please set your Gemini API key in the `.env` file or environment variables.\n\n"
            "Get your API key from: https://makersuite.google.com/app/apikey"
        )
        return
    
    # Initialize session state
    init_session_state()
    
    # Get auth manager
    auth_manager = get_auth_manager()
    
    # Check authentication
    if not require_auth(auth_manager):
        return  # Auth page is shown by require_auth
    
    # Ensure user has a session
    ensure_session_exists()
    
    # Render main interface
    render_sidebar()
    render_chat_interface()
    
    # Footer
    st.markdown("---")
    st.markdown(
        "<div class='app-footer'>"
        "Built with ❤️ using Streamlit & Gemini | "
        "Knowledge from Yasir Qadhi's Seerah Series"
        "</div>",
        unsafe_allow_html=True
    )


if __name__ == "__main__":
    main()
