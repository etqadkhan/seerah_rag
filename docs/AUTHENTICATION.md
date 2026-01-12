# Authentication System

This document describes the user authentication system used in the Seerah Q&A application.

## Overview

The authentication system provides:
- User registration with secure password hashing
- Login/logout functionality
- Session management using Streamlit session state
- User-to-chat-history mapping

## Security Features

### Password Hashing with bcrypt

Passwords are never stored in plain text. We use bcrypt for secure hashing:

```python
import bcrypt

def hash_password(password: str) -> str:
    """Generate secure hash with random salt."""
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(password.encode('utf-8'), salt)
    return hashed.decode('utf-8')

def verify_password(password: str, hash: str) -> bool:
    """Verify password against stored hash."""
    return bcrypt.checkpw(
        password.encode('utf-8'),
        hash.encode('utf-8')
    )
```

**Why bcrypt?**
- Automatic salting prevents rainbow table attacks
- Configurable work factor (cost) for future-proofing
- Time-tested and widely trusted
- Slow by design to prevent brute force attacks

### Input Validation

User inputs are validated before processing:

```python
def validate_registration(username: str, password: str) -> tuple[bool, str]:
    if len(username) < 3:
        return False, "Username must be at least 3 characters"
    
    if not username.isalnum():
        return False, "Username can only contain letters and numbers"
    
    if len(password) < 6:
        return False, "Password must be at least 6 characters"
    
    return True, "Valid"
```

## Database Schema

```sql
CREATE TABLE users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Index for faster lookups
CREATE INDEX idx_users_username ON users(username);
```

## User Flow

### Registration

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│  User enters    │────▶│  Validate       │────▶│  Hash password  │
│  credentials    │     │  inputs         │     │  with bcrypt    │
└─────────────────┘     └─────────────────┘     └─────────────────┘
                                                        │
                                                        ▼
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│  Show success   │◀────│  Store in       │◀────│  Check username │
│  message        │     │  database       │     │  uniqueness     │
└─────────────────┘     └─────────────────┘     └─────────────────┘
```

### Login

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│  User enters    │────▶│  Lookup user    │────▶│  Verify         │
│  credentials    │     │  in database    │     │  password       │
└─────────────────┘     └─────────────────┘     └─────────────────┘
                                                        │
                                                        ▼
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│  Redirect to    │◀────│  Update         │◀────│  Password       │
│  chat page      │     │  session state  │     │  matches?       │
└─────────────────┘     └─────────────────┘     └─────────────────┘
```

## Session Management

### Streamlit Session State

We use Streamlit's session state for managing login status:

```python
def init_session_state():
    """Initialize authentication-related session state."""
    if 'authenticated' not in st.session_state:
        st.session_state.authenticated = False
    
    if 'user_id' not in st.session_state:
        st.session_state.user_id = None
    
    if 'username' not in st.session_state:
        st.session_state.username = None
    
    if 'current_session_id' not in st.session_state:
        st.session_state.current_session_id = None

def login_user(user: User):
    """Set session state for logged-in user."""
    st.session_state.authenticated = True
    st.session_state.user_id = user.id
    st.session_state.username = user.username

def logout_user():
    """Clear session state on logout."""
    st.session_state.authenticated = False
    st.session_state.user_id = None
    st.session_state.username = None
    st.session_state.current_session_id = None
```

### Session Persistence

Streamlit session state persists for:
- The duration of the browser session
- Until the user closes the tab/browser
- Until explicit logout

**Note**: Session state is not persisted across server restarts. For HuggingFace Spaces, this means users need to log in again after the Space restarts.

## Implementation

### AuthManager Class

```python
class AuthManager:
    """Manages user authentication and session state."""
    
    def __init__(self):
        self.db = get_db()
    
    def register_user(self, username: str, password: str) -> tuple[bool, str]:
        """Register a new user account."""
        # Validate inputs
        valid, message = validate_registration(username, password)
        if not valid:
            return False, message
        
        # Hash password and create user
        password_hash = self.hash_password(password)
        user = self.db.create_user(username, password_hash)
        
        if user:
            return True, "Registration successful!"
        return False, "Username already exists"
    
    def authenticate_user(self, username: str, password: str) -> tuple[bool, User]:
        """Authenticate user credentials."""
        user = self.db.get_user_by_username(username)
        
        if not user:
            return False, None
        
        if self.verify_password(password, user.password_hash):
            return True, user
        
        return False, None
```

### UI Components

```python
def render_login_form(auth_manager: AuthManager):
    """Render login form."""
    st.subheader("Login")
    
    with st.form("login_form"):
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")
        submit = st.form_submit_button("Login")
        
        if submit:
            success, user = auth_manager.authenticate_user(username, password)
            
            if success:
                auth_manager.login_user(user)
                st.success("Login successful!")
                st.rerun()
            else:
                st.error("Invalid username or password")

def render_register_form(auth_manager: AuthManager):
    """Render registration form."""
    st.subheader("Register")
    
    with st.form("register_form"):
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")
        confirm = st.text_input("Confirm Password", type="password")
        submit = st.form_submit_button("Register")
        
        if submit:
            if password != confirm:
                st.error("Passwords do not match")
                return
            
            success, message = auth_manager.register_user(username, password)
            
            if success:
                st.success(message)
            else:
                st.error(message)
```

## User-Chat Mapping

Each user's chat history is isolated:

```sql
-- Chat sessions belong to users
SELECT * FROM chat_sessions WHERE user_id = ?;

-- Messages belong to sessions (which belong to users)
SELECT m.* FROM messages m
JOIN chat_sessions s ON m.session_id = s.id
WHERE s.user_id = ?;
```

This ensures:
- Users only see their own chat history
- Data isolation between users
- Proper cleanup when users are deleted

## Protected Routes

```python
def require_auth(auth_manager: AuthManager) -> bool:
    """Require authentication to access page."""
    auth_manager.init_session_state()
    
    if not auth_manager.is_authenticated():
        render_auth_page(auth_manager)
        return False
    
    return True

# Usage in app.py
def main():
    auth_manager = AuthManager()
    
    if not require_auth(auth_manager):
        return  # Shows login page
    
    # User is authenticated, show main app
    render_chat_interface()
```

## Security Considerations

### What We Do

1. **Password hashing**: bcrypt with automatic salting
2. **Input validation**: Prevent injection and invalid data
3. **Session isolation**: Users can't access others' data
4. **No password display**: Passwords masked in forms

### What We Don't Do (and why)

1. **HTTPS enforcement**: Handled by HuggingFace Spaces
2. **Rate limiting**: Would require Redis/external storage
3. **Email verification**: Simplified for demo purposes
4. **Password recovery**: Would require email integration
5. **Two-factor auth**: Out of scope for this project

### Recommendations for Production

If deploying in a production environment:

1. **Add rate limiting** to prevent brute force attacks
2. **Implement email verification** for account recovery
3. **Add password strength requirements**
4. **Consider OAuth integration** (Google, GitHub)
5. **Add audit logging** for security events
6. **Regular security audits**

## Testing Authentication

```python
# Test registration
auth = AuthManager()
success, msg = auth.register_user("testuser", "password123")
assert success == True

# Test duplicate username
success, msg = auth.register_user("testuser", "password123")
assert success == False
assert "exists" in msg.lower()

# Test login
success, user = auth.authenticate_user("testuser", "password123")
assert success == True
assert user.username == "testuser"

# Test wrong password
success, user = auth.authenticate_user("testuser", "wrongpassword")
assert success == False
```

## Troubleshooting

### "Username already exists"
- The username is taken
- Try a different username

### "Invalid username or password"
- Check for typos
- Ensure caps lock is off
- Username is case-sensitive

### Session Lost After Refresh
- Normal behavior for Streamlit
- Re-login required
- Consider this a feature, not a bug (security)

### Can't Access Chat History
- Verify you're logged into the correct account
- Chat history is user-specific
