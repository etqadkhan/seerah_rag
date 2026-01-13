"""
Seerah Q&A - Main Streamlit Application

A beautifully designed RAG-powered Q&A application for learning about the Seerah
(biography) of Prophet Muhammad ﷺ using Yasir Qadhi's comprehensive lecture series.

Features:
- Beautiful dark theme with Islamic aesthetic
- User authentication (register/login) - limited to 5 users
- Conversation history with memory
- Source citations from lecture series
- Multiple chat sessions per user

Run with: streamlit run app.py
"""

import streamlit as st
import streamlit.components.v1 as components
from pathlib import Path
import sys

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from config.settings import GEMINI_API_KEY
from core.auth_manager import AuthManager
from core.chat_memory import ChatMemory, SessionManager
from core.retriever import SeerahRetriever


# ============================================================================
# Page Configuration & Custom CSS
# ============================================================================

st.set_page_config(
    page_title="Seerah Q&A",
    page_icon="🕌",
    layout="wide",
    initial_sidebar_state="expanded"
)


def get_custom_css() -> str:
    """Return custom CSS for the application theme."""
    return """
<style>
    /* Import custom fonts */
    @import url('https://fonts.googleapis.com/css2?family=Playfair+Display:wght@400;500;600;700&family=Amiri:wght@400;700&family=Inter:wght@300;400;500;600&display=swap');
    
    /* Root variables - Green and Gold Theme */
    :root {
        --bg-primary: #0a1a0a;
        --bg-secondary: #1a2a1a;
        --bg-tertiary: #253525;
        --accent-gold: #d4af37;
        --accent-gold-light: #f4d03f;
        --accent-gold-dark: #b8860b;
        --accent-green: #22c55e;
        --accent-green-light: #4ade80;
        --accent-green-dark: #16a34a;
        --text-primary: #f5f5f5;
        --text-secondary: #b0c0b0;
        --text-muted: #708070;
        --border-color: #2a3a2a;
        --success-color: #22c55e;
        --error-color: #f87171;
    }
    
    /* Global styles - Dark green background - solid, no light colors */
    .stApp {
        background: var(--bg-primary) !important;
        background-color: var(--bg-primary) !important;
        background-image: none !important;
    }
    
    /* Ensure body and html also have dark background */
    body, html {
        background: var(--bg-primary) !important;
        background-color: var(--bg-primary) !important;
    }
    
    /* Override any white or light backgrounds in main containers */
    [data-testid="stAppViewContainer"],
    [data-testid="stAppViewContainer"] > div,
    [data-testid="stAppViewContainer"] > div > div,
    .main,
    .main > div,
    .block-container {
        background: var(--bg-primary) !important;
        background-color: var(--bg-primary) !important;
    }
    
    /* Hide Streamlit branding */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}
    
    /* Main container */
    .main .block-container {
        padding-top: 2rem;
        padding-bottom: 3rem;
        max-width: 1200px;
    }
    
    /* Typography - Ensure all text is visible */
    h1, h2, h3, h4, h5, h6 {
        font-family: 'Playfair Display', serif !important;
        color: var(--text-primary) !important;
    }
    
    p, span, div, label, small {
        font-family: 'Inter', sans-serif;
    }
    
    /* Override Streamlit default text colors - be specific */
    .stMarkdown, .stMarkdown p, .stMarkdown span, .stMarkdown div,
    .stMarkdown li, .stMarkdown ul, .stMarkdown ol {
        color: var(--text-primary) !important;
    }
    
    /* Labels and form text */
    label, .stTextInput label, .stTextArea label, .stSelectbox label,
    .stCheckbox label, .stRadio label {
        color: var(--text-primary) !important;
        font-weight: 500 !important;
    }
    
    /* Preserve gold accents for headers, green for accents */
    .app-title, .arabic-text, .ornament {
        color: var(--accent-gold) !important;
    }
    
    .app-subtitle {
        color: var(--text-secondary) !important;
    }
    
    /* General text color for main content */
    .main p, .main span:not(.ornament):not(.app-title):not(.arabic-text),
    .main div:not([class*="gold"]):not([class*="accent"]) {
        color: var(--text-primary) !important;
    }
    
    /* Ensure all button text is visible - but primary buttons get black */
    button, .stButton button, [role="button"] {
        color: var(--text-primary) !important;
    }
    
    /* Override for primary buttons specifically */
    .stButton > button:not([kind="secondary"]),
    form button[type="submit"],
    .stForm button[type="submit"] {
        color: #000000 !important;
        -webkit-text-fill-color: #000000 !important;
    }
    
    /* Form submit buttons - override white backgrounds */
    form button[type="submit"],
    .stForm button[type="submit"],
    button[type="submit"],
    [data-baseweb="button"][type="submit"] {
        background: linear-gradient(135deg, var(--accent-green-dark) 0%, var(--accent-green) 100%) !important;
        background-color: var(--accent-green) !important;
        color: #000000 !important;
        border: none !important;
    }
    
    form button[type="submit"]:hover,
    .stForm button[type="submit"]:hover,
    button[type="submit"]:hover,
    [data-baseweb="button"][type="submit"]:hover {
        background: linear-gradient(135deg, var(--accent-green) 0%, var(--accent-green-light) 100%) !important;
        background-color: var(--accent-green-light) !important;
        color: #000000 !important;
    }
    
    /* Override any white button backgrounds - most aggressive */
    button[style*="background-color: rgb(255"],
    button[style*="background-color: white"],
    button[style*="background-color: #fff"],
    .stButton button[style*="background-color: rgb(255"],
    .stButton button[style*="background-color: white"],
    button[style*="background: rgb(255"],
    button[style*="background: white"],
    .stButton button[style*="background: rgb(255"],
    .stButton button[style*="background: white"] {
        background: linear-gradient(135deg, var(--accent-green-dark) 0%, var(--accent-green) 100%) !important;
        background-color: var(--accent-green) !important;
        color: #000000 !important;
        -webkit-text-fill-color: #000000 !important;
    }
    
    /* Force green background on all submit buttons */
    button[type="submit"],
    form button,
    .stForm button,
    .stButton > button:not([kind="secondary"]) {
        background: linear-gradient(135deg, var(--accent-green-dark) 0%, var(--accent-green) 100%) !important;
        background-color: var(--accent-green) !important;
        color: #000000 !important;
        -webkit-text-fill-color: #000000 !important;
    }
    
    /* Override BaseWeb button component */
    [data-baseweb="button"]:not([kind="secondary"]) {
        background-color: var(--accent-green) !important;
        color: #000000 !important;
    }
    
    [data-baseweb="button"]:not([kind="secondary"]):hover {
        background-color: var(--accent-green-light) !important;
        color: #000000 !important;
    }
    
    /* Target button text nodes directly */
    .stButton > button:not([kind="secondary"]) span,
    button[type="submit"] span,
    [data-baseweb="button"]:not([kind="secondary"]) span {
        color: #000000 !important;
        -webkit-text-fill-color: #000000 !important;
    }
    
    /* Ultra-specific override for form submit buttons */
    form button[type="submit"],
    .stForm button[type="submit"],
    form .stButton > button,
    .stForm .stButton > button,
    [data-testid="stForm"] button[type="submit"],
    [data-testid="stForm"] .stButton > button {
        background: linear-gradient(135deg, #16a34a 0%, #22c55e 100%) !important;
        background-color: #22c55e !important;
        background-image: linear-gradient(135deg, #16a34a 0%, #22c55e 100%) !important;
        color: #000000 !important;
        -webkit-text-fill-color: #000000 !important;
        border: none !important;
    }
    
    form button[type="submit"] *,
    .stForm button[type="submit"] *,
    form .stButton > button *,
    .stForm .stButton > button *,
    [data-testid="stForm"] button[type="submit"] *,
    [data-testid="stForm"] .stButton > button * {
        color: #000000 !important;
        -webkit-text-fill-color: #000000 !important;
    }
    
    /* Target buttons by their text content using attribute selectors */
    button:has-text("Sign In"),
    button:has-text("Create Account") {
        background: linear-gradient(135deg, #16a34a 0%, #22c55e 100%) !important;
        background-color: #22c55e !important;
        color: #000000 !important;
    }
    
    /* Most aggressive - target all buttons in forms and override */
    form button:not([kind="secondary"]),
    [data-testid="stForm"] button:not([kind="secondary"]),
    form .stButton button:not([kind="secondary"]),
    [data-testid="stForm"] .stButton button:not([kind="secondary"]) {
        background: linear-gradient(135deg, #16a34a 0%, #22c55e 100%) !important;
        background-color: #22c55e !important;
        background-image: linear-gradient(135deg, #16a34a 0%, #22c55e 100%) !important;
        color: #000000 !important;
        -webkit-text-fill-color: #000000 !important;
    }
    
    /* Target buttons by their computed background - most specific */
    button[style*="background"]:not([kind="secondary"]) {
        background: linear-gradient(135deg, #16a34a 0%, #22c55e 100%) !important;
        background-color: #22c55e !important;
        color: #000000 !important;
    }
    
    /* Override form submit buttons specifically - highest priority */
    form button[type="submit"]:not([kind="secondary"]),
    [data-testid="stForm"] button[type="submit"]:not([kind="secondary"]),
    form .stButton > button:not([kind="secondary"]),
    [data-testid="stForm"] .stButton > button:not([kind="secondary"]) {
        background: linear-gradient(135deg, #16a34a 0%, #22c55e 100%) !important;
        background-color: #22c55e !important;
        background-image: linear-gradient(135deg, #16a34a 0%, #22c55e 100%) !important;
        color: #000000 !important;
        -webkit-text-fill-color: #000000 !important;
        border: none !important;
    }
    
    form button[type="submit"]:not([kind="secondary"]) *,
    [data-testid="stForm"] button[type="submit"]:not([kind="secondary"]) *,
    form .stButton > button:not([kind="secondary"]) *,
    [data-testid="stForm"] .stButton > button:not([kind="secondary"]) * {
        color: #000000 !important;
        -webkit-text-fill-color: #000000 !important;
    }
    
    /* Header styling - Green and Gold gradient */
    .app-header {
        text-align: center;
        padding: 2rem 0;
        margin-bottom: 2rem;
        border-bottom: 1px solid var(--border-color);
        background: linear-gradient(180deg, rgba(34, 197, 94, 0.1) 0%, rgba(212, 175, 55, 0.05) 50%, transparent 100%);
        border-radius: 12px 12px 0 0;
    }
    
    .app-title {
        font-family: 'Playfair Display', serif !important;
        font-size: 2.5rem;
        font-weight: 700;
        color: var(--accent-gold) !important;
        margin-bottom: 0.5rem;
        letter-spacing: 1px;
    }
    
    .app-subtitle {
        font-family: 'Amiri', serif !important;
        font-size: 1.1rem;
        color: var(--text-secondary);
        font-style: italic;
    }
    
    .arabic-text {
        font-family: 'Amiri', serif !important;
        font-size: 1.3rem;
        color: var(--accent-gold-light);
        direction: rtl;
        margin-top: 0.5rem;
    }
    
    /* Decorative elements */
    .ornament {
        color: var(--accent-gold);
        font-size: 1.5rem;
        opacity: 0.7;
    }
    
    /* Sidebar styling */
    [data-testid="stSidebar"] {
        background: linear-gradient(180deg, var(--bg-secondary) 0%, var(--bg-primary) 100%);
        border-right: 1px solid var(--border-color);
    }
    
    [data-testid="stSidebar"] .stMarkdown h1,
    [data-testid="stSidebar"] .stMarkdown h2,
    [data-testid="stSidebar"] .stMarkdown h3 {
        color: var(--accent-green) !important;
        font-family: 'Playfair Display', serif !important;
    }
    
    [data-testid="stSidebar"] .stMarkdown p {
        color: var(--text-secondary);
    }
    
    /* Button styling - Green and Gold */
    .stButton > button {
        background: linear-gradient(135deg, var(--accent-green-dark) 0%, var(--accent-green) 100%) !important;
        background-color: var(--accent-green) !important;
        color: #000000 !important;
        border: none !important;
        border-radius: 8px;
        font-weight: 600;
        font-family: 'Inter', sans-serif;
        transition: all 0.3s ease;
        padding: 0.5rem 1rem;
    }
    
    .stButton > button:hover {
        background: linear-gradient(135deg, var(--accent-green) 0%, var(--accent-green-light) 100%) !important;
        background-color: var(--accent-green-light) !important;
        transform: translateY(-2px);
        box-shadow: 0 4px 12px rgba(34, 197, 94, 0.3);
        color: #000000 !important;
    }
    
    .stButton > button[kind="secondary"] {
        background: var(--bg-tertiary) !important;
        color: var(--text-primary) !important;
        border: 1px solid var(--border-color);
    }
    
    .stButton > button[kind="secondary"]:hover {
        background: var(--bg-secondary) !important;
        border-color: var(--accent-green);
        color: var(--text-primary) !important;
    }
    
    /* Primary button text always visible - black on green - aggressive override */
    .stButton > button[type="submit"],
    .stButton > button:not([kind="secondary"]),
    button[type="submit"],
    form button,
    .stForm button {
        color: #000000 !important;
        -webkit-text-fill-color: #000000 !important;
    }
    
    /* Override BaseWeb button styling */
    [data-baseweb="button"] {
        background-color: var(--accent-green) !important;
        color: #000000 !important;
    }
    
    [data-baseweb="button"]:hover {
        background-color: var(--accent-green-light) !important;
        color: #000000 !important;
    }
    
    /* Target button text specifically */
    .stButton > button *,
    button[type="submit"] *,
    [data-baseweb="button"] * {
        color: #000000 !important;
    }
    
    /* Override any inline styles */
    button[style*="color"],
    .stButton button[style*="color"] {
        color: #000000 !important;
    }
    
    /* Chat messages */
    [data-testid="stChatMessage"] {
        background: var(--bg-secondary) !important;
        border-radius: 12px;
        padding: 1.25rem !important;
        margin-bottom: 1rem;
        border: 1px solid var(--border-color);
    }
    
    [data-testid="stChatMessage"][data-testid*="user"] {
        background: linear-gradient(135deg, var(--bg-tertiary) 0%, var(--bg-secondary) 100%) !important;
        border-left: 3px solid var(--accent-gold);
    }
    
    [data-testid="stChatMessage"][data-testid*="assistant"] {
        background: var(--bg-secondary) !important;
        border-left: 3px solid var(--accent-green);
    }
    
    /* Chat input - Fixed dark theme, no white borders or backgrounds - ultra aggressive */
    [data-testid="stChatInput"],
    [data-testid="stChatInput"] > div,
    [data-testid="stChatInput"] > div > div,
    [data-testid="stChatInput"] > div > div > div,
    [data-testid="stChatInput"] > div > div > div > div,
    [data-testid="stChatInput"] > div > div > div > div > div {
        background: var(--bg-secondary) !important;
        background-color: var(--bg-secondary) !important;
        background-image: none !important;
        border: 1px solid var(--border-color) !important;
        border-radius: 12px !important;
    }
    
    /* Remove white from all nested elements */
    [data-testid="stChatInput"] *,
    [data-testid="stChatInput"] > *,
    [data-testid="stChatInput"] > * > *,
    [data-testid="stChatInput"] > * > * > * {
        background-color: var(--bg-secondary) !important;
        background: var(--bg-secondary) !important;
    }
    
    /* Chat input container - ensure dark background */
    [data-testid="stChatInput"] > div,
    [data-testid="stChatInput"] > div > div,
    [data-testid="stChatInput"] > div > div > div {
        background-color: var(--bg-secondary) !important;
        background: var(--bg-secondary) !important;
    }
    
    [data-testid="stChatInput"] * {
        border-color: var(--border-color) !important;
    }
    
    [data-testid="stChatInput"] textarea {
        background: var(--bg-tertiary) !important;
        background-color: var(--bg-tertiary) !important;
        color: var(--text-primary) !important;
        font-family: 'Inter', sans-serif !important;
        font-size: 1rem !important;
        border: 1px solid var(--border-color) !important;
        border-color: var(--border-color) !important;
    }
    
    [data-testid="stChatInput"] textarea::placeholder {
        color: var(--text-muted) !important;
        opacity: 0.8 !important;
    }
    
    [data-testid="stChatInput"] textarea:focus {
        background: var(--bg-secondary) !important;
        background-color: var(--bg-secondary) !important;
        border-color: var(--accent-green) !important;
        outline: none !important;
    }
    
    /* Remove any white borders or backgrounds - aggressive override */
    [data-testid="stChatInput"] * {
        border-color: var(--border-color) !important;
    }
    
    [data-testid="stChatInput"] input,
    [data-testid="stChatInput"] textarea,
    [data-testid="stChatInput"] div,
    [data-testid="stChatInput"] span {
        border-color: var(--border-color) !important;
        background-color: var(--bg-tertiary) !important;
    }
    
    /* Override BaseWeb styling in chat input - remove white */
    [data-testid="stChatInput"] [data-baseweb="base-input"],
    [data-testid="stChatInput"] [data-baseweb="input"],
    [data-testid="stChatInput"] [data-baseweb="textarea"] {
        background-color: var(--bg-tertiary) !important;
        border-color: var(--border-color) !important;
    }
    
    [data-testid="stChatInput"] [data-baseweb="base-input"] *,
    [data-testid="stChatInput"] [data-baseweb="input"] *,
    [data-testid="stChatInput"] [data-baseweb="textarea"] * {
        background-color: transparent !important;
        border-color: var(--border-color) !important;
    }
    
    [data-testid="stChatInput"] [data-baseweb="base-input"] input,
    [data-testid="stChatInput"] [data-baseweb="input"] input,
    [data-testid="stChatInput"] [data-baseweb="textarea"] textarea {
        background-color: var(--bg-tertiary) !important;
        color: var(--text-primary) !important;
        border-color: var(--border-color) !important;
    }
    
    /* Remove any inline white styles */
    [data-testid="stChatInput"] [style*="border-color: rgb(255"],
    [data-testid="stChatInput"] [style*="border-color: white"],
    [data-testid="stChatInput"] [style*="background-color: rgb(255"],
    [data-testid="stChatInput"] [style*="background-color: white"] {
        border-color: var(--border-color) !important;
        background-color: var(--bg-tertiary) !important;
    }
    
    /* Chat message text and containers - remove white backgrounds */
    [data-testid="stChatMessage"],
    [data-testid="stChatMessage"] *,
    [data-testid="stChatMessage"] > div,
    [data-testid="stChatMessage"] > div > div {
        background-color: transparent !important;
        background: transparent !important;
    }
    
    [data-testid="stChatMessage"] p, 
    [data-testid="stChatMessage"] div, 
    [data-testid="stChatMessage"] span {
        color: var(--text-primary) !important;
    }
    
    /* Chat input container - remove any white backgrounds */
    [data-testid="stChatInput"],
    [data-testid="stChatInput"] > div,
    [data-testid="stChatInput"] > div > div,
    [data-testid="stChatInput"] > div > div > div {
        background-color: var(--bg-secondary) !important;
        background: var(--bg-secondary) !important;
    }
    
    /* Remove white backgrounds from any chat-related containers */
    .stChatMessage,
    .stChatInput,
    [class*="chat"],
    [class*="Chat"] {
        background-color: transparent !important;
        background: transparent !important;
    }
    
    /* Override any white backgrounds in the main content area - force dark */
    .main .block-container,
    .main [data-testid="stVerticalBlock"],
    .main [data-testid="stHorizontalBlock"],
    [data-testid="stAppViewContainer"],
    [data-testid="stAppViewContainer"] > div,
    [data-testid="stAppViewContainer"] > div > div,
    [data-testid="stVerticalBlock"],
    [data-testid="stHorizontalBlock"] {
        background-color: var(--bg-primary) !important;
        background: var(--bg-primary) !important;
    }
    
    /* Remove white backgrounds from all divs */
    div:not([class*="chat"]):not([data-testid="stChatInput"]):not([data-testid="stChatMessage"]) {
        background-color: transparent !important;
    }
    
    /* But ensure main containers are dark */
    .main,
    .main > div,
    .block-container,
    [data-testid="stAppViewContainer"] {
        background-color: var(--bg-primary) !important;
        background: var(--bg-primary) !important;
    }
    
    /* Remove white backgrounds from any element with white background */
    div[style*="background-color: rgb(255"],
    div[style*="background-color: white"],
    div[style*="background: rgb(255"],
    div[style*="background: white"],
    [style*="background-color: rgb(255, 255, 255)"],
    [style*="background: rgb(255, 255, 255)"] {
        background-color: var(--bg-secondary) !important;
        background: var(--bg-secondary) !important;
    }
    
    /* Specifically target chat input area containers */
    [data-testid="stChatInput"] ~ div,
    [data-testid="stChatInput"] + div,
    div:has([data-testid="stChatInput"]) {
        background-color: transparent !important;
        background: transparent !important;
    }
    
    /* Input fields - Enhanced visibility with dark theme */
    .stTextInput input, .stTextArea textarea, 
    input[type="text"], input[type="password"],
    input[type="email"], input[type="number"] {
        background: var(--bg-tertiary) !important;
        color: var(--text-primary) !important;
        border: 1px solid var(--border-color) !important;
        border-radius: 8px !important;
        font-family: 'Inter', sans-serif !important;
        font-size: 1rem !important;
        padding: 0.5rem 0.75rem !important;
    }
    
    /* Override Streamlit's default white input background */
    .stTextInput > div > div > input,
    .stTextArea > div > div > textarea {
        background-color: var(--bg-tertiary) !important;
        color: var(--text-primary) !important;
    }
    
    .stTextInput input::placeholder, .stTextArea textarea::placeholder,
    input[type="text"]::placeholder, input[type="password"]::placeholder {
        color: var(--text-muted) !important;
        opacity: 0.7 !important;
    }
    
    .stTextInput input:focus, .stTextArea textarea:focus,
    input[type="text"]:focus, input[type="password"]:focus {
        border-color: var(--accent-green) !important;
        box-shadow: 0 0 0 2px rgba(34, 197, 94, 0.2) !important;
        outline: none !important;
        background: var(--bg-secondary) !important;
        background-color: var(--bg-secondary) !important;
    }
    
    /* Input wrapper styling - ensure dark background */
    .stTextInput > div > div, .stTextArea > div > div {
        background: transparent !important;
        background-color: transparent !important;
    }
    
    /* Force dark theme on all input containers - BaseWeb override */
    [data-baseweb="input"], [data-baseweb="input"] > div {
        background-color: var(--bg-tertiary) !important;
    }
    
    [data-baseweb="input"] input,
    [data-baseweb="input"] input[type="text"],
    [data-baseweb="input"] input[type="password"] {
        background-color: var(--bg-tertiary) !important;
        color: var(--text-primary) !important;
        border-color: var(--border-color) !important;
    }
    
    [data-baseweb="input"]:focus-within input,
    [data-baseweb="input"]:focus-within input[type="text"],
    [data-baseweb="input"]:focus-within input[type="password"] {
        background-color: var(--bg-secondary) !important;
        border-color: var(--accent-green) !important;
    }
    
    /* Textarea */
    [data-baseweb="textarea"] textarea {
        background-color: var(--bg-tertiary) !important;
        color: var(--text-primary) !important;
        border-color: var(--border-color) !important;
    }
    
    /* Override any white backgrounds - most aggressive */
    input, textarea {
        background-color: var(--bg-tertiary) !important;
        color: var(--text-primary) !important;
    }
    
    input[style*="background-color: rgb(255"],
    input[style*="background-color: white"],
    input[style*="background-color: #fff"],
    textarea[style*="background-color: rgb(255"],
    textarea[style*="background-color: white"],
    textarea[style*="background-color: #fff"] {
        background-color: var(--bg-tertiary) !important;
        color: var(--text-primary) !important;
    }
    
    /* Target Streamlit's specific input classes */
    .stTextInput input, .stTextInput input[type="text"],
    .stTextInput input[type="password"],
    .stTextArea textarea {
        background: var(--bg-tertiary) !important;
        background-color: var(--bg-tertiary) !important;
        color: var(--text-primary) !important;
        -webkit-text-fill-color: var(--text-primary) !important;
    }
    
    /* Ensure input containers don't have white backgrounds */
    div[data-baseweb="base-input"],
    div[data-baseweb="input"],
    div[data-baseweb="textarea"] {
        background-color: transparent !important;
    }
    
    /* Form container */
    [data-testid="stForm"] {
        background: var(--bg-secondary) !important;
        border: 1px solid var(--border-color) !important;
        border-radius: 12px !important;
        padding: 1.5rem !important;
    }
    
    [data-testid="stForm"] label, [data-testid="stForm"] p, [data-testid="stForm"] span {
        color: var(--text-primary) !important;
    }
    
    /* Expander */
    .streamlit-expanderHeader {
        background: var(--bg-tertiary) !important;
        color: var(--text-primary) !important;
        border-radius: 8px !important;
        border: 1px solid var(--border-color) !important;
    }
    
    .streamlit-expanderContent {
        background: var(--bg-secondary) !important;
        border: 1px solid var(--border-color) !important;
        border-top: none !important;
        border-radius: 0 0 8px 8px !important;
    }
    
    /* Tabs */
    .stTabs [data-baseweb="tab-list"] {
        gap: 8px;
        background: var(--bg-tertiary);
        border-radius: 12px;
        padding: 0.5rem;
    }
    
    .stTabs [data-baseweb="tab"] {
        background: transparent;
        color: var(--text-secondary);
        border-radius: 8px;
        padding: 0.5rem 1rem;
        font-family: 'Inter', sans-serif;
    }
    
    .stTabs [aria-selected="true"] {
        background: var(--accent-green) !important;
        color: var(--text-primary) !important;
    }
    
    /* Success/Error messages */
    .stSuccess {
        background: rgba(74, 222, 128, 0.1) !important;
        border: 1px solid var(--success-color) !important;
        color: var(--success-color) !important;
        border-radius: 8px !important;
    }
    
    .stError {
        background: rgba(248, 113, 113, 0.1) !important;
        border: 1px solid var(--error-color) !important;
        color: var(--error-color) !important;
        border-radius: 8px !important;
    }
    
    .stWarning {
        background: rgba(212, 175, 55, 0.1) !important;
        border: 1px solid var(--accent-gold) !important;
        color: var(--accent-gold) !important;
        border-radius: 8px !important;
    }
    
    .stInfo {
        background: rgba(96, 165, 250, 0.1) !important;
        border: 1px solid #60a5fa !important;
        color: #60a5fa !important;
        border-radius: 8px !important;
    }
    
    /* Source card */
    .source-card {
        background: var(--bg-tertiary);
        border: 1px solid var(--border-color);
        border-radius: 8px;
        padding: 0.75rem 1rem;
        margin: 0.5rem 0;
        transition: all 0.2s ease;
    }
    
    .source-card:hover {
        border-color: var(--accent-green);
        transform: translateX(4px);
    }
    
    .source-title {
        color: var(--accent-green-light);
        font-weight: 500;
        font-size: 0.9rem;
    }
    
    .source-meta {
        color: var(--text-muted);
        font-size: 0.8rem;
    }
    
    /* Session list */
    .session-item {
        background: var(--bg-tertiary);
        border: 1px solid var(--border-color);
        border-radius: 8px;
        padding: 0.75rem;
        margin-bottom: 0.5rem;
        cursor: pointer;
        transition: all 0.2s ease;
    }
    
    .session-item:hover {
        border-color: var(--accent-green);
        background: var(--bg-secondary);
    }
    
    .session-item.active {
        border-color: var(--accent-green);
        background: linear-gradient(135deg, rgba(34, 197, 94, 0.1) 0%, transparent 100%);
    }
    
    /* Footer */
    .app-footer {
        text-align: center;
        padding: 2rem 0 1rem;
        color: var(--text-muted);
        font-size: 0.85rem;
        border-top: 1px solid var(--border-color);
        margin-top: 2rem;
    }
    
    .app-footer a {
        color: var(--accent-gold);
        text-decoration: none;
    }
    
    /* Spinner */
    .stSpinner > div {
        border-top-color: var(--accent-green) !important;
    }
    
    /* Geometric pattern overlay - Completely hidden for solid dark background */
    .geometric-pattern {
        display: none; /* Hide the pattern completely for solid dark background */
    }
    
    /* Scrollbar */
    ::-webkit-scrollbar {
        width: 8px;
        height: 8px;
    }
    
    ::-webkit-scrollbar-track {
        background: var(--bg-secondary);
    }
    
    ::-webkit-scrollbar-thumb {
        background: var(--border-color);
        border-radius: 4px;
    }
    
    ::-webkit-scrollbar-thumb:hover {
        background: var(--accent-gold-dark);
    }
    
    /* Additional text visibility fixes */
    .stMarkdown h1, .stMarkdown h2, .stMarkdown h3 {
        color: var(--text-primary) !important;
    }
    
    /* Selectbox and other inputs */
    .stSelectbox select, select {
        background: var(--bg-tertiary) !important;
        color: var(--text-primary) !important;
        border: 1px solid var(--border-color) !important;
        border-radius: 8px !important;
    }
    
    /* Checkbox and radio */
    .stCheckbox label, .stRadio label {
        color: var(--text-primary) !important;
    }
    
    /* Sidebar text */
    [data-testid="stSidebar"] p, [data-testid="stSidebar"] span,
    [data-testid="stSidebar"] div, [data-testid="stSidebar"] label {
        color: var(--text-primary) !important;
    }
    
    /* Main content area text */
    .main p, .main span, .main div, .main label {
        color: var(--text-primary) !important;
    }
    
    /* Divider */
    hr {
        border-color: var(--border-color) !important;
    }
    
    /* Links - Green accent */
    a {
        color: var(--accent-green) !important;
    }
    
    a:hover {
        color: var(--accent-green-light) !important;
    }
</style>

<style id="button-override">
    /* This style tag loads after Streamlit's styles to override them */
    form button[type="submit"],
    [data-testid="stForm"] button[type="submit"],
    form .stButton > button:not([kind="secondary"]),
    [data-testid="stForm"] .stButton > button:not([kind="secondary"]) {
        background: linear-gradient(135deg, #16a34a 0%, #22c55e 100%) !important;
        background-color: #22c55e !important;
        background-image: none !important;
        color: #000000 !important;
        -webkit-text-fill-color: #000000 !important;
        border: none !important;
    }
    
    form button[type="submit"] span,
    form button[type="submit"] div,
    form button[type="submit"] p,
    [data-testid="stForm"] button[type="submit"] span,
    [data-testid="stForm"] button[type="submit"] div,
    [data-testid="stForm"] button[type="submit"] p,
    form .stButton > button:not([kind="secondary"]) span,
    form .stButton > button:not([kind="secondary"]) div,
    form .stButton > button:not([kind="secondary"]) p,
    [data-testid="stForm"] .stButton > button:not([kind="secondary"]) span,
    [data-testid="stForm"] .stButton > button:not([kind="secondary"]) div,
    [data-testid="stForm"] .stButton > button:not([kind="secondary"]) p {
        color: #000000 !important;
        -webkit-text-fill-color: #000000 !important;
    }
</style>

<div class="geometric-pattern"></div>

<script>
    // Fix white backgrounds in chat input and containers
    (function() {
        function fixWhiteBoxes() {
            // Find chat input and fix white backgrounds
            const chatInput = document.querySelector('[data-testid="stChatInput"]');
            if (chatInput) {
                // Fix the chat input container and all nested divs
                const allElements = chatInput.querySelectorAll('*');
                allElements.forEach(el => {
                    const bg = window.getComputedStyle(el).backgroundColor;
                    if (bg && (bg.includes('rgb(255') || bg.includes('white') || bg === '#ffffff' || bg === 'rgb(255, 255, 255)')) {
                        el.style.setProperty('background-color', '#1a2a1a', 'important');
                        el.style.setProperty('background', '#1a2a1a', 'important');
                    }
                });
                
                // Also fix the chat input itself
                const chatBg = window.getComputedStyle(chatInput).backgroundColor;
                if (chatBg && (chatBg.includes('rgb(255') || chatBg.includes('white'))) {
                    chatInput.style.setProperty('background-color', '#1a2a1a', 'important');
                    chatInput.style.setProperty('background', '#1a2a1a', 'important');
                }
            }
            
            // Fix any white boxes in the main content area
            document.querySelectorAll('div').forEach(div => {
                const bg = window.getComputedStyle(div).backgroundColor;
                const rect = div.getBoundingClientRect();
                // Only fix visible white boxes (not tiny elements)
                if (rect.width > 100 && rect.height > 50 && 
                    bg && (bg.includes('rgb(255') || bg.includes('white') || bg === '#ffffff')) {
                    // Check if it's near the chat input
                    const chatInput = document.querySelector('[data-testid="stChatInput"]');
                    if (chatInput) {
                        const chatRect = chatInput.getBoundingClientRect();
                        const distance = Math.abs(rect.bottom - chatRect.top);
                        if (distance < 200) { // Within 200px of chat input
                            div.style.setProperty('background-color', 'transparent', 'important');
                            div.style.setProperty('background', 'transparent', 'important');
                        }
                    }
                }
            });
        }
        
        // Run continuously
        setInterval(fixWhiteBoxes, 100);
        fixWhiteBoxes();
        
        // Also observe DOM changes
        new MutationObserver(fixWhiteBoxes).observe(document.body, {
            childList: true,
            subtree: true,
            attributes: true,
            attributeFilter: ['style', 'class']
        });
    })();
    
    // Fix button styles - ultra aggressive continuous approach
    (function() {
        function forceButtonFix() {
            // Target all buttons
            document.querySelectorAll('button').forEach(btn => {
                const text = (btn.textContent || btn.innerText || '').trim();
                const bg = window.getComputedStyle(btn).backgroundColor;
                const computedColor = window.getComputedStyle(btn).color;
                const isWhite = bg && (bg.includes('rgb(255') || bg.includes('white') || bg === '#ffffff' || bg === 'rgb(255, 255, 255)');
                const isGrayText = computedColor && (computedColor.includes('rgb(128') || computedColor.includes('gray') || computedColor.includes('rgb(169') || computedColor.includes('rgb(107') || computedColor.includes('rgb(156') || computedColor.includes('rgb(209'));
                const isSubmit = btn.type === 'submit' || text === 'Sign In' || text.includes('Sign In') || text === 'Create Account' || text.includes('Create Account');
                
                // Fix submit buttons or buttons with white background/gray text
                if ((isSubmit || isWhite || isGrayText) && btn.getAttribute('kind') !== 'secondary') {
                    // Force all style properties individually
                    btn.style.removeProperty('background');
                    btn.style.removeProperty('background-color');
                    btn.style.removeProperty('background-image');
                    btn.style.setProperty('background', 'linear-gradient(135deg, #16a34a 0%, #22c55e 100%)', 'important');
                    btn.style.setProperty('background-color', '#22c55e', 'important');
                    btn.style.setProperty('background-image', 'none', 'important');
                    btn.style.setProperty('color', '#000000', 'important');
                    btn.style.setProperty('-webkit-text-fill-color', '#000000', 'important');
                    btn.style.setProperty('border', 'none', 'important');
                    
                    // Force child elements - target all possible text containers
                    btn.querySelectorAll('span, div, p, label, *').forEach(child => {
                        if (child.tagName !== 'BUTTON') {
                            child.style.setProperty('color', '#000000', 'important');
                            child.style.setProperty('-webkit-text-fill-color', '#000000', 'important');
                        }
                    });
                }
            });
        }
        
        // Run continuously every 30ms using requestAnimationFrame for better performance
        function runFix() {
            forceButtonFix();
            requestAnimationFrame(runFix);
        }
        runFix();
        
        // Also use setInterval as backup
        setInterval(forceButtonFix, 30);
        
        // Also observe DOM changes and style changes
        new MutationObserver(function(mutations) {
            mutations.forEach(function(mutation) {
                if (mutation.type === 'attributes' && mutation.attributeName === 'style') {
                    forceButtonFix();
                }
            });
            forceButtonFix();
        }).observe(document.body, {
            childList: true, 
            subtree: true, 
            attributes: true,
            attributeFilter: ['style', 'class']
        });
    })();
</script>
"""


# Apply custom CSS
st.markdown(get_custom_css(), unsafe_allow_html=True)


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
# Authentication Pages
# ============================================================================

def render_auth_header():
    """Render the beautiful authentication header."""
    st.markdown("""
    <div class="app-header">
        <div class="ornament">☽ ✦ ☾</div>
        <h1 class="app-title">Seerah Q&A</h1>
        <p class="app-subtitle">Journey Through the Life of the Prophet ﷺ</p>
        <p class="arabic-text">سيرة النبي محمد ﷺ</p>
        <div class="ornament">✦ ❋ ✦</div>
    </div>
    """, unsafe_allow_html=True)


def render_login_form(auth_manager: AuthManager) -> bool:
    """Render a beautiful login form."""
    # Inject JavaScript to fix button styles
    st.markdown("""
    <script>
    function fixFormButtons() {
        // Target all buttons in forms
        const forms = document.querySelectorAll('form, [data-testid="stForm"]');
        forms.forEach(form => {
            const buttons = form.querySelectorAll('button[type="submit"], button');
            buttons.forEach(btn => {
                const text = (btn.textContent || btn.innerText || '').trim();
                if (text.includes('Sign In') || text.includes('Create Account') || btn.type === 'submit') {
                    // Force override all styles
                    btn.setAttribute('style', 
                        'background: linear-gradient(135deg, #16a34a 0%, #22c55e 100%) !important; ' +
                        'background-color: #22c55e !important; ' +
                        'color: #000000 !important; ' +
                        'border: none !important;'
                    );
                    // Fix child elements
                    const children = btn.querySelectorAll('*');
                    children.forEach(child => {
                        child.setAttribute('style', 'color: #000000 !important;');
                    });
                }
            });
        });
    }
    
    // Run multiple times
    setTimeout(fixFormButtons, 50);
    setTimeout(fixFormButtons, 200);
    setTimeout(fixFormButtons, 500);
    setTimeout(fixFormButtons, 1000);
    
    // Also use MutationObserver
    const observer = new MutationObserver(fixFormButtons);
    observer.observe(document.body, { childList: true, subtree: true });
    </script>
    """, unsafe_allow_html=True)
    
    with st.form("login_form", clear_on_submit=True):
        st.markdown("### 🔑 Welcome Back")
        st.markdown("*Enter your credentials to continue your journey*")
        
        username = st.text_input("Username", placeholder="Enter your username")
        password = st.text_input("Password", type="password", placeholder="Enter your password")
        
        col1, col2 = st.columns([1, 1])
        with col1:
            # Use a custom styled button wrapper
            st.markdown("""
            <style>
            .custom-submit-btn {
                background: linear-gradient(135deg, #16a34a 0%, #22c55e 100%) !important;
                background-color: #22c55e !important;
                color: #000000 !important;
                border: none !important;
                padding: 0.5rem 1rem !important;
                border-radius: 8px !important;
                font-weight: 600 !important;
                width: 100% !important;
            }
            </style>
            """, unsafe_allow_html=True)
            submit = st.form_submit_button("Sign In", use_container_width=True, type="primary")
        
        # Inject JavaScript after form is rendered
        components.html("""
        <script>
        (function() {
            function fixButtons() {
                const buttons = document.querySelectorAll('form button[type="submit"], .stForm button[type="submit"]');
                buttons.forEach(btn => {
                    const text = (btn.textContent || btn.innerText || '').trim();
                    if (text.includes('Sign In') || text.includes('Create Account')) {
                        btn.style.cssText = 'background: linear-gradient(135deg, #16a34a 0%, #22c55e 100%) !important; background-color: #22c55e !important; color: #000000 !important; border: none !important;';
                        Array.from(btn.querySelectorAll('*')).forEach(el => {
                            el.style.cssText = 'color: #000000 !important;';
                        });
                    }
                });
            }
            setTimeout(fixButtons, 100);
            setTimeout(fixButtons, 500);
            const obs = new MutationObserver(fixButtons);
            obs.observe(document.body, {childList: true, subtree: true});
        })();
        </script>
        """, height=0)
        
        if submit:
            if not username or not password:
                st.error("Please enter both username and password")
                return False
            
            success, user = auth_manager.authenticate_user(username, password)
            
            if success and user:
                auth_manager.login_user(user)
                st.success("✅ Welcome back! Redirecting...")
                st.rerun()
                return True
            else:
                st.error("Invalid username or password")
                return False
    
    return False


def render_register_form(auth_manager: AuthManager) -> bool:
    """Render a beautiful registration form."""
    with st.form("register_form", clear_on_submit=True):
        st.markdown("### ✨ Create Account")
        st.markdown("*Registration is limited to authorized users only*")
        
        username = st.text_input("Username", placeholder="Choose a username")
        password = st.text_input("Password", type="password", placeholder="Create a password")
        confirm_password = st.text_input("Confirm Password", type="password", placeholder="Confirm your password")
        
        col1, col2 = st.columns([1, 1])
        with col1:
            submit = st.form_submit_button("Create Account", use_container_width=True)
        
        # Inject JavaScript after form is rendered
        components.html("""
        <script>
        (function() {
            function fixButtons() {
                const buttons = document.querySelectorAll('form button[type="submit"], .stForm button[type="submit"]');
                buttons.forEach(btn => {
                    const text = (btn.textContent || btn.innerText || '').trim();
                    if (text.includes('Sign In') || text.includes('Create Account')) {
                        btn.style.cssText = 'background: linear-gradient(135deg, #16a34a 0%, #22c55e 100%) !important; background-color: #22c55e !important; color: #000000 !important; border: none !important;';
                        Array.from(btn.querySelectorAll('*')).forEach(el => {
                            el.style.cssText = 'color: #000000 !important;';
                        });
                    }
                });
            }
            setTimeout(fixButtons, 100);
            setTimeout(fixButtons, 500);
            const obs = new MutationObserver(fixButtons);
            obs.observe(document.body, {childList: true, subtree: true});
        })();
        </script>
        """, height=0)
        
        if submit:
            if not username or not password:
                st.error("Please fill in all fields")
                return False
            
            if password != confirm_password:
                st.error("Passwords do not match")
                return False
            
            success, message = auth_manager.register_user(username, password)
            
            if success:
                st.success(f"✅ {message} Please login.")
                return True
            else:
                st.error(message)
                return False
    
    return False


def render_auth_page(auth_manager: AuthManager):
    """Render the full authentication page."""
    render_auth_header()
    
    col1, col2, col3 = st.columns([1, 2, 1])
    
    with col2:
        tab1, tab2 = st.tabs(["🔑 Login", "✨ Register"])
        
        with tab1:
            render_login_form(auth_manager)
        
        with tab2:
            render_register_form(auth_manager)
        
        st.markdown("---")
        st.markdown("""
        <div style="text-align: center; color: var(--text-muted); font-size: 0.9rem;">
            <p>📚 Powered by <strong>Yasir Qadhi's Seerah Series</strong></p>
            <p>104 lectures covering the complete biography of Prophet Muhammad ﷺ</p>
        </div>
        """, unsafe_allow_html=True)


def require_auth(auth_manager: AuthManager) -> bool:
    """Require authentication to access the page."""
    auth_manager.init_session_state()
    
    if not auth_manager.is_authenticated():
        render_auth_page(auth_manager)
        return False
    
    return True


# ============================================================================
# Sidebar Components
# ============================================================================

def render_sidebar():
    """Render the sidebar with session management."""
    with st.sidebar:
        # User info section
        st.markdown(f"""
        <div style="padding: 1rem 0; border-bottom: 1px solid var(--border-color); margin-bottom: 1rem;">
            <p style="color: var(--text-muted); font-size: 0.8rem; margin: 0;">Logged in as</p>
            <p style="color: var(--accent-gold); font-size: 1.1rem; font-weight: 600; margin: 0;">
                ✦ {st.session_state.username}
            </p>
        </div>
        """, unsafe_allow_html=True)
        
        if st.button("🚪 Logout", use_container_width=True):
            AuthManager.logout_user()
            st.rerun()
        
        st.markdown("---")
        
        # New chat button
        if st.button("✨ New Conversation", use_container_width=True, type="primary"):
            create_new_session()
        
        st.markdown("---")
        
        # Chat history
        st.markdown("### 📜 Your Conversations")
        
        user_id = st.session_state.user_id
        session_manager = SessionManager(user_id)
        sessions = session_manager.get_all_sessions(limit=15)
        
        if not sessions:
            st.markdown("""
            <p style="color: var(--text-muted); font-size: 0.9rem; font-style: italic;">
                No conversations yet. Start asking questions!
            </p>
            """, unsafe_allow_html=True)
        
        for session in sessions:
            is_current = session.id == st.session_state.current_session_id
            
            col1, col2 = st.columns([5, 1])
            
            with col1:
                button_type = "primary" if is_current else "secondary"
                title_preview = session.title[:25] + "..." if len(session.title) > 25 else session.title
                if st.button(
                    f"💬 {title_preview}",
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
        
        st.markdown("---")
        
        # Knowledge base status
        st.markdown("### 📚 Knowledge Base")
        retriever = get_retriever()
        if retriever.is_ready():
            st.success("✅ Ready (4,000+ chunks)")
        else:
            st.warning("⚠️ Not initialized")
        
        # About section
        st.markdown("---")
        st.markdown("""
        <div style="color: var(--text-muted); font-size: 0.8rem;">
            <p><strong>About</strong></p>
            <p>This Q&A system uses Dr. Yasir Qadhi's complete Seerah lecture series 
            (104 videos) as its knowledge base.</p>
            <p style="color: var(--accent-gold);">Ask anything about the life of Prophet Muhammad ﷺ</p>
        </div>
        """, unsafe_allow_html=True)


def create_new_session():
    """Create a new chat session."""
    user_id = st.session_state.user_id
    session_manager = SessionManager(user_id)
    session = session_manager.create_session("New Conversation")
    st.session_state.current_session_id = session.id
    st.session_state.messages = []
    st.rerun()


def switch_session(session_id: int):
    """Switch to a different chat session."""
    if st.session_state.current_session_id != session_id:
        st.session_state.current_session_id = session_id
        memory = ChatMemory(session_id)
        st.session_state.messages = memory.format_messages_for_display()
        st.rerun()


def ensure_session_exists():
    """Ensure user has at least one session."""
    if st.session_state.current_session_id is None:
        user_id = st.session_state.user_id
        session_manager = SessionManager(user_id)
        
        sessions = session_manager.get_all_sessions(limit=1)
        if sessions:
            st.session_state.current_session_id = sessions[0].id
            memory = ChatMemory(sessions[0].id)
            st.session_state.messages = memory.format_messages_for_display()
        else:
            session = session_manager.create_session("New Conversation")
            st.session_state.current_session_id = session.id
            st.session_state.messages = []


# ============================================================================
# Chat Interface
# ============================================================================

def render_chat_header():
    """Render the chat interface header."""
    st.markdown("""
    <div class="app-header">
        <div class="ornament">☽ ✦ ☾</div>
        <h1 class="app-title">Seerah Q&A</h1>
        <p class="app-subtitle">Ask about the life of Prophet Muhammad ﷺ</p>
        <div class="ornament">✦ ❋ ✦</div>
    </div>
    """, unsafe_allow_html=True)


def render_chat_interface():
    """Render the main chat interface."""
    render_chat_header()
    
    # Check if knowledge base is ready
    retriever = get_retriever()
    if not retriever.is_ready():
        st.warning("""
        ⚠️ **Knowledge base not initialized!**
        
        Please run the data pipeline first:
        ```bash
        python -m data_pipeline.knowledge_base --source huggingface --recreate
        ```
        """)
        return
    
    # Welcome message for new sessions
    if not st.session_state.messages:
        st.markdown("""
        <div style="text-align: center; padding: 2rem; color: var(--text-secondary);">
            <p style="font-size: 1.2rem;">بسم الله الرحمن الرحيم</p>
            <p>Welcome to your Seerah learning journey.</p>
            <p>Ask any question about the life of Prophet Muhammad ﷺ</p>
            <br>
            <p style="font-size: 0.9rem; color: var(--text-muted);">
                <strong>Try asking:</strong><br>
                "What happened at the Battle of Badr?"<br>
                "Tell me about the Hijrah to Madinah"<br>
                "Who was Khadijah رضي الله عنها?"
            </p>
        </div>
        """, unsafe_allow_html=True)
    
    # Display chat messages
    for message in st.session_state.messages:
        with st.chat_message(message['role']):
            st.markdown(message['content'])
            
            # Show sources for assistant messages
            if message['role'] == 'assistant' and message.get('sources'):
                with st.expander("📚 View Sources"):
                    for source in message['sources']:
                        lecture_num = source.get('lecture_number', source.get('playlist_index', '?'))
                        youtube_link = source.get('youtube_link', '')
                        title = source.get('title', 'Unknown')
                        
                        if youtube_link:
                            st.markdown(f"""
                            <div class="source-card">
                                <a href="{youtube_link}" target="_blank" class="source-title">{title}</a>
                                <div class="source-meta">Lecture {lecture_num}</div>
                            </div>
                            """, unsafe_allow_html=True)
                        else:
                            st.markdown(f"""
                            <div class="source-card">
                                <span class="source-title">{title}</span>
                                <div class="source-meta">Lecture {lecture_num}</div>
                            </div>
                            """, unsafe_allow_html=True)
    
    # Chat input
    if prompt := st.chat_input("Ask about the Seerah... ✦"):
        process_user_query(prompt)


def process_user_query(query: str):
    """Process a user's query and generate response."""
    session_id = st.session_state.current_session_id
    
    # Add user message
    st.session_state.messages.append({
        'role': 'user',
        'content': query,
        'sources': None
    })
    
    with st.chat_message("user"):
        st.markdown(query)
    
    # Generate response
    with st.chat_message("assistant"):
        with st.spinner("Searching the Seerah..."):
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
                            youtube_link = source.youtube_link
                            if youtube_link:
                                st.markdown(f"""
                                <div class="source-card">
                                    <a href="{youtube_link}" target="_blank" class="source-title">{source.title}</a>
                                    <div class="source-meta">Lecture {source.lecture_number}</div>
                                </div>
                                """, unsafe_allow_html=True)
                            else:
                                st.markdown(f"""
                                <div class="source-card">
                                    <span class="source-title">{source.title}</span>
                                    <div class="source-meta">Lecture {source.lecture_number}</div>
                                </div>
                                """, unsafe_allow_html=True)
                
                # Update session state
                st.session_state.messages.append({
                    'role': 'assistant',
                    'content': response.answer,
                    'sources': [s.to_dict() for s in response.sources]
                })
                
                # Auto-title session if first message
                if len(st.session_state.messages) == 2:
                    user_id = st.session_state.user_id
                    session_manager = SessionManager(user_id)
                    session_manager.auto_title_session(session_id, query)
                
            except Exception as e:
                error_msg = f"I apologize, but I encountered an error: {str(e)}"
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
        st.error("""
        ⚠️ **GEMINI_API_KEY not set!**
        
        Please set your Gemini API key in the `.env` file or environment variables.
        
        Get your API key from: https://makersuite.google.com/app/apikey
        """)
        return
    
    # Initialize session state
    init_session_state()
    
    # Get auth manager
    auth_manager = get_auth_manager()
    
    # Check authentication
    if not require_auth(auth_manager):
        return
    
    # Ensure user has a session
    ensure_session_exists()
    
    # Render main interface
    render_sidebar()
    render_chat_interface()
    
    # Footer
    st.markdown("""
    <div class="app-footer">
        <p>✦ Built with love for seeking knowledge ✦</p>
        <p>Powered by Yasir Qadhi's Seerah Series • Gemini AI • Streamlit</p>
        <p style="font-family: 'Amiri', serif; margin-top: 1rem;">
            صلى الله عليه وسلم
        </p>
    </div>
    """, unsafe_allow_html=True)


if __name__ == "__main__":
    main()
