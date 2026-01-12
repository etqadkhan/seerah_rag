"""
Authentication Manager Module

This module handles user authentication including:
- User registration with password hashing
- Login verification
- Session management for Streamlit

Security:
- Passwords are hashed using bcrypt
- Never stores plain text passwords
- Uses secure session state management

See docs/AUTHENTICATION.md for detailed documentation.
"""

import sys
from pathlib import Path
from typing import Optional
import streamlit as st
import bcrypt

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from config.settings import ALLOWED_USERNAMES, MAX_USERS
from database.db_manager import get_db
from database.models import User


class AuthManager:
    """
    Manages user authentication and session state.
    
    This class provides methods for:
    - Registering new users
    - Authenticating existing users
    - Managing Streamlit session state for login persistence
    """
    
    def __init__(self):
        """Initialize the auth manager with database connection."""
        self.db = get_db()
    
    # ========================================================================
    # Password Hashing
    # ========================================================================
    
    @staticmethod
    def hash_password(password: str) -> str:
        """
        Hash a password using bcrypt.
        
        Args:
            password: Plain text password
            
        Returns:
            Hashed password string
        """
        salt = bcrypt.gensalt()
        hashed = bcrypt.hashpw(password.encode('utf-8'), salt)
        return hashed.decode('utf-8')
    
    @staticmethod
    def verify_password(password: str, password_hash: str) -> bool:
        """
        Verify a password against its hash.
        
        Args:
            password: Plain text password to verify
            password_hash: Stored password hash
            
        Returns:
            True if password matches, False otherwise
        """
        try:
            return bcrypt.checkpw(
                password.encode('utf-8'),
                password_hash.encode('utf-8')
            )
        except Exception:
            return False
    
    # ========================================================================
    # User Operations
    # ========================================================================
    
    def register_user(self, username: str, password: str) -> tuple[bool, str]:
        """
        Register a new user account.
        
        Registration is restricted to:
        1. Usernames in the ALLOWED_USERNAMES whitelist (if configured)
        2. Total users below MAX_USERS limit
        
        Args:
            username: Desired username (must be unique and whitelisted)
            password: Plain text password
            
        Returns:
            Tuple of (success: bool, message: str)
        """
        # Validate inputs
        if not username or len(username) < 3:
            return False, "Username must be at least 3 characters"
        
        if not password or len(password) < 6:
            return False, "Password must be at least 6 characters"
        
        # Check for invalid characters in username
        if not username.isalnum():
            return False, "Username can only contain letters and numbers"
        
        # Whitelist check (if configured)
        if ALLOWED_USERNAMES:
            if username.lower() not in ALLOWED_USERNAMES:
                return False, "Registration is restricted. Username not authorized."
        
        # Max users check
        current_user_count = self.db.count_users()
        if current_user_count >= MAX_USERS:
            return False, "Registration is closed. Maximum users reached."
        
        # Hash password and create user
        password_hash = self.hash_password(password)
        user = self.db.create_user(username, password_hash)
        
        if user:
            return True, "Registration successful!"
        else:
            return False, "Username already exists"
    
    def authenticate_user(self, username: str, password: str) -> tuple[bool, Optional[User]]:
        """
        Authenticate a user with username and password.
        
        Args:
            username: Username to authenticate
            password: Plain text password
            
        Returns:
            Tuple of (success: bool, user: User or None)
        """
        user = self.db.get_user_by_username(username)
        
        if not user:
            return False, None
        
        if self.verify_password(password, user.password_hash):
            return True, user
        
        return False, None
    
    # ========================================================================
    # Streamlit Session Management
    # ========================================================================
    
    @staticmethod
    def init_session_state():
        """
        Initialize Streamlit session state for authentication.
        
        Call this at the start of your Streamlit app.
        """
        if 'authenticated' not in st.session_state:
            st.session_state.authenticated = False
        
        if 'user_id' not in st.session_state:
            st.session_state.user_id = None
        
        if 'username' not in st.session_state:
            st.session_state.username = None
        
        if 'current_session_id' not in st.session_state:
            st.session_state.current_session_id = None
    
    @staticmethod
    def login_user(user: User):
        """
        Set session state for a logged-in user.
        
        Args:
            user: User object to log in
        """
        st.session_state.authenticated = True
        st.session_state.user_id = user.id
        st.session_state.username = user.username
    
    @staticmethod
    def logout_user():
        """Clear session state and log out user."""
        st.session_state.authenticated = False
        st.session_state.user_id = None
        st.session_state.username = None
        st.session_state.current_session_id = None
    
    @staticmethod
    def is_authenticated() -> bool:
        """
        Check if a user is currently authenticated.
        
        Returns:
            True if user is logged in, False otherwise
        """
        return st.session_state.get('authenticated', False)
    
    @staticmethod
    def get_current_user_id() -> Optional[int]:
        """
        Get the current logged-in user's ID.
        
        Returns:
            User ID if logged in, None otherwise
        """
        return st.session_state.get('user_id')
    
    @staticmethod
    def get_current_username() -> Optional[str]:
        """
        Get the current logged-in user's username.
        
        Returns:
            Username if logged in, None otherwise
        """
        return st.session_state.get('username')


# ============================================================================
# Streamlit UI Components
# ============================================================================

def render_login_form(auth_manager: AuthManager) -> bool:
    """
    Render a login form in Streamlit.
    
    Args:
        auth_manager: AuthManager instance
        
    Returns:
        True if login successful, False otherwise
    """
    st.subheader("Login")
    
    with st.form("login_form"):
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")
        submit = st.form_submit_button("Login")
        
        if submit:
            if not username or not password:
                st.error("Please enter both username and password")
                return False
            
            success, user = auth_manager.authenticate_user(username, password)
            
            if success and user:
                auth_manager.login_user(user)
                st.success("Login successful!")
                st.rerun()
                return True
            else:
                st.error("Invalid username or password")
                return False
    
    return False


def render_register_form(auth_manager: AuthManager) -> bool:
    """
    Render a registration form in Streamlit.
    
    Args:
        auth_manager: AuthManager instance
        
    Returns:
        True if registration successful, False otherwise
    """
    st.subheader("Register")
    
    # Show registration restriction notice
    if ALLOWED_USERNAMES:
        st.info(
            "Registration is restricted to authorized family members only. "
            "Please use your assigned username."
        )
    
    with st.form("register_form"):
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")
        confirm_password = st.text_input("Confirm Password", type="password")
        submit = st.form_submit_button("Register")
        
        if submit:
            if not username or not password:
                st.error("Please fill in all fields")
                return False
            
            if password != confirm_password:
                st.error("Passwords do not match")
                return False
            
            success, message = auth_manager.register_user(username, password)
            
            if success:
                st.success(message + " Please login.")
                return True
            else:
                st.error(message)
                return False
    
    return False


def render_auth_page(auth_manager: AuthManager):
    """
    Render the full authentication page with login/register tabs.
    
    Args:
        auth_manager: AuthManager instance
    """
    st.title("🕌 Seerah Q&A")
    st.markdown("*Learn about the life of Prophet Muhammad ﷺ*")
    
    st.markdown("---")
    
    tab1, tab2 = st.tabs(["Login", "Register"])
    
    with tab1:
        render_login_form(auth_manager)
    
    with tab2:
        render_register_form(auth_manager)
    
    st.markdown("---")
    st.markdown(
        "*This application uses Yasir Qadhi's Seerah lecture series "
        "as its knowledge base.*"
    )


# ============================================================================
# Convenience Functions
# ============================================================================

def require_auth(auth_manager: AuthManager) -> bool:
    """
    Require authentication to access the page.
    
    If not authenticated, shows the login page.
    
    Args:
        auth_manager: AuthManager instance
        
    Returns:
        True if user is authenticated, False otherwise
    """
    auth_manager.init_session_state()
    
    if not auth_manager.is_authenticated():
        render_auth_page(auth_manager)
        return False
    
    return True
