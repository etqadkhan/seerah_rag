"""
Database Manager Module

This module handles all SQLite database operations for:
- User management (CRUD operations)
- Chat session management
- Message storage and retrieval

The database is designed to persist user data and chat history,
enabling conversation memory across sessions.
"""

import sqlite3
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Optional
import sys

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from config.settings import DATABASE_PATH
from database.models import User, ChatSession, Message, SCHEMA_SQL


class DatabaseManager:
    """
    Manages SQLite database connections and operations.
    
    This class provides a clean interface for all database operations,
    ensuring proper connection handling and error management.
    """
    
    def __init__(self, db_path: Path = DATABASE_PATH):
        """
        Initialize the database manager.
        
        Args:
            db_path: Path to the SQLite database file
        """
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_database()
    
    def _init_database(self):
        """Initialize database schema if not exists."""
        with self.get_connection() as conn:
            conn.executescript(SCHEMA_SQL)
            conn.commit()
    
    @contextmanager
    def get_connection(self):
        """
        Context manager for database connections.
        
        Yields:
            sqlite3.Connection: Database connection
        """
        conn = sqlite3.connect(self.db_path, detect_types=sqlite3.PARSE_DECLTYPES)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.close()
    
    # ========================================================================
    # User Operations
    # ========================================================================
    
    def create_user(self, username: str, password_hash: str) -> Optional[User]:
        """
        Create a new user account.
        
        Args:
            username: Unique username
            password_hash: Hashed password (use bcrypt)
            
        Returns:
            User object if created, None if username exists
        """
        with self.get_connection() as conn:
            try:
                cursor = conn.execute(
                    "INSERT INTO users (username, password_hash) VALUES (?, ?)",
                    (username, password_hash)
                )
                conn.commit()
                
                return User(
                    id=cursor.lastrowid,
                    username=username,
                    password_hash=password_hash,
                    created_at=datetime.now()
                )
            except sqlite3.IntegrityError:
                # Username already exists
                return None
    
    def get_user_by_username(self, username: str) -> Optional[User]:
        """
        Retrieve a user by username.
        
        Args:
            username: Username to look up
            
        Returns:
            User object if found, None otherwise
        """
        with self.get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM users WHERE username = ?",
                (username,)
            ).fetchone()
            
            if row:
                return User(
                    id=row['id'],
                    username=row['username'],
                    password_hash=row['password_hash'],
                    created_at=row['created_at']
                )
            return None
    
    def get_user_by_id(self, user_id: int) -> Optional[User]:
        """
        Retrieve a user by ID.
        
        Args:
            user_id: User ID to look up
            
        Returns:
            User object if found, None otherwise
        """
        with self.get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM users WHERE id = ?",
                (user_id,)
            ).fetchone()
            
            if row:
                return User(
                    id=row['id'],
                    username=row['username'],
                    password_hash=row['password_hash'],
                    created_at=row['created_at']
                )
            return None
    
    def count_users(self) -> int:
        """
        Count total number of registered users.
        
        Returns:
            Total number of users in the database
        """
        with self.get_connection() as conn:
            row = conn.execute("SELECT COUNT(*) as count FROM users").fetchone()
            return row['count'] if row else 0
    
    # ========================================================================
    # Chat Session Operations
    # ========================================================================
    
    def create_session(self, user_id: int, title: str = "New Chat") -> ChatSession:
        """
        Create a new chat session for a user.
        
        Args:
            user_id: ID of the user
            title: Optional title for the session
            
        Returns:
            Created ChatSession object
        """
        with self.get_connection() as conn:
            cursor = conn.execute(
                "INSERT INTO chat_sessions (user_id, title) VALUES (?, ?)",
                (user_id, title)
            )
            conn.commit()
            
            return ChatSession(
                id=cursor.lastrowid,
                user_id=user_id,
                title=title,
                created_at=datetime.now(),
                updated_at=datetime.now()
            )
    
    def get_session(self, session_id: int) -> Optional[ChatSession]:
        """
        Retrieve a chat session by ID.
        
        Args:
            session_id: Session ID to look up
            
        Returns:
            ChatSession object if found, None otherwise
        """
        with self.get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM chat_sessions WHERE id = ?",
                (session_id,)
            ).fetchone()
            
            if row:
                return ChatSession(
                    id=row['id'],
                    user_id=row['user_id'],
                    title=row['title'],
                    summary=row['summary'],
                    created_at=row['created_at'],
                    updated_at=row['updated_at']
                )
            return None
    
    def get_user_sessions(self, user_id: int, limit: int = 50) -> list[ChatSession]:
        """
        Get all chat sessions for a user, ordered by most recent.
        
        Args:
            user_id: User ID
            limit: Maximum number of sessions to return
            
        Returns:
            List of ChatSession objects
        """
        with self.get_connection() as conn:
            rows = conn.execute(
                """
                SELECT * FROM chat_sessions 
                WHERE user_id = ? 
                ORDER BY updated_at DESC 
                LIMIT ?
                """,
                (user_id, limit)
            ).fetchall()
            
            return [
                ChatSession(
                    id=row['id'],
                    user_id=row['user_id'],
                    title=row['title'],
                    summary=row['summary'],
                    created_at=row['created_at'],
                    updated_at=row['updated_at']
                )
                for row in rows
            ]
    
    def update_session_title(self, session_id: int, title: str) -> bool:
        """
        Update the title of a chat session.
        
        Args:
            session_id: Session ID to update
            title: New title
            
        Returns:
            True if updated, False otherwise
        """
        with self.get_connection() as conn:
            cursor = conn.execute(
                """
                UPDATE chat_sessions 
                SET title = ?, updated_at = CURRENT_TIMESTAMP 
                WHERE id = ?
                """,
                (title, session_id)
            )
            conn.commit()
            return cursor.rowcount > 0
    
    def update_session_summary(self, session_id: int, summary: str) -> bool:
        """
        Update the summary of a chat session.
        
        Used for conversation memory - stores condensed history.
        
        Args:
            session_id: Session ID to update
            summary: New summary text
            
        Returns:
            True if updated, False otherwise
        """
        with self.get_connection() as conn:
            cursor = conn.execute(
                """
                UPDATE chat_sessions 
                SET summary = ?, updated_at = CURRENT_TIMESTAMP 
                WHERE id = ?
                """,
                (summary, session_id)
            )
            conn.commit()
            return cursor.rowcount > 0
    
    def delete_session(self, session_id: int) -> bool:
        """
        Delete a chat session and all its messages.
        
        Args:
            session_id: Session ID to delete
            
        Returns:
            True if deleted, False otherwise
        """
        with self.get_connection() as conn:
            cursor = conn.execute(
                "DELETE FROM chat_sessions WHERE id = ?",
                (session_id,)
            )
            conn.commit()
            return cursor.rowcount > 0
    
    # ========================================================================
    # Message Operations
    # ========================================================================
    
    def add_message(
        self,
        session_id: int,
        role: str,
        content: str,
        sources: Optional[str] = None
    ) -> Message:
        """
        Add a message to a chat session.
        
        Args:
            session_id: Session ID
            role: 'user' or 'assistant'
            content: Message content
            sources: Optional JSON string of source references
            
        Returns:
            Created Message object
        """
        with self.get_connection() as conn:
            cursor = conn.execute(
                """
                INSERT INTO messages (session_id, role, content, sources) 
                VALUES (?, ?, ?, ?)
                """,
                (session_id, role, content, sources)
            )
            
            # Update session's updated_at timestamp
            conn.execute(
                "UPDATE chat_sessions SET updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                (session_id,)
            )
            
            conn.commit()
            
            return Message(
                id=cursor.lastrowid,
                session_id=session_id,
                role=role,
                content=content,
                sources=sources,
                created_at=datetime.now()
            )
    
    def get_session_messages(
        self,
        session_id: int,
        limit: Optional[int] = None,
        offset: int = 0
    ) -> list[Message]:
        """
        Get messages from a chat session.
        
        Args:
            session_id: Session ID
            limit: Maximum number of messages (None for all)
            offset: Number of messages to skip from the beginning
            
        Returns:
            List of Message objects in chronological order
        """
        with self.get_connection() as conn:
            if limit:
                rows = conn.execute(
                    """
                    SELECT * FROM messages 
                    WHERE session_id = ? 
                    ORDER BY created_at ASC
                    LIMIT ? OFFSET ?
                    """,
                    (session_id, limit, offset)
                ).fetchall()
            else:
                rows = conn.execute(
                    """
                    SELECT * FROM messages 
                    WHERE session_id = ? 
                    ORDER BY created_at ASC
                    """,
                    (session_id,)
                ).fetchall()
            
            return [
                Message(
                    id=row['id'],
                    session_id=row['session_id'],
                    role=row['role'],
                    content=row['content'],
                    sources=row['sources'],
                    created_at=row['created_at']
                )
                for row in rows
            ]
    
    def get_recent_messages(self, session_id: int, n: int = 10) -> list[Message]:
        """
        Get the N most recent messages from a session.
        
        Used for conversation memory - buffer of recent messages.
        
        Args:
            session_id: Session ID
            n: Number of recent messages to retrieve
            
        Returns:
            List of Message objects in chronological order
        """
        with self.get_connection() as conn:
            rows = conn.execute(
                """
                SELECT * FROM (
                    SELECT * FROM messages 
                    WHERE session_id = ? 
                    ORDER BY created_at DESC 
                    LIMIT ?
                ) ORDER BY created_at ASC
                """,
                (session_id, n)
            ).fetchall()
            
            return [
                Message(
                    id=row['id'],
                    session_id=row['session_id'],
                    role=row['role'],
                    content=row['content'],
                    sources=row['sources'],
                    created_at=row['created_at']
                )
                for row in rows
            ]
    
    def get_message_count(self, session_id: int) -> int:
        """
        Get the total number of messages in a session.
        
        Args:
            session_id: Session ID
            
        Returns:
            Number of messages
        """
        with self.get_connection() as conn:
            row = conn.execute(
                "SELECT COUNT(*) as count FROM messages WHERE session_id = ?",
                (session_id,)
            ).fetchone()
            return row['count'] if row else 0
    
    def delete_message(self, message_id: int) -> bool:
        """
        Delete a specific message.
        
        Args:
            message_id: Message ID to delete
            
        Returns:
            True if deleted, False otherwise
        """
        with self.get_connection() as conn:
            cursor = conn.execute(
                "DELETE FROM messages WHERE id = ?",
                (message_id,)
            )
            conn.commit()
            return cursor.rowcount > 0


# ============================================================================
# Global Database Instance
# ============================================================================

# Singleton pattern for database manager
_db_instance: Optional[DatabaseManager] = None


def get_db() -> DatabaseManager:
    """
    Get the global database manager instance.
    
    Returns:
        DatabaseManager singleton instance
    """
    global _db_instance
    if _db_instance is None:
        _db_instance = DatabaseManager()
    return _db_instance


def init_db(db_path: Path = DATABASE_PATH) -> DatabaseManager:
    """
    Initialize the database with a specific path.
    
    Args:
        db_path: Path to the SQLite database file
        
    Returns:
        DatabaseManager instance
    """
    global _db_instance
    _db_instance = DatabaseManager(db_path)
    return _db_instance
