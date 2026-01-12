"""
Chat Memory Management Module

This module handles conversation memory for the RAG application.
It implements a hybrid memory system combining:
1. Buffer Memory: Recent messages in full detail
2. Summary Memory: Condensed history of older messages

The memory system enables:
- Contextual follow-up questions
- Reference to previous discussions
- Long conversation continuity

See docs/MEMORY_MANAGEMENT.md for detailed documentation.
"""

import json
import sys
from pathlib import Path
from typing import Optional

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

import google.generativeai as genai

from config.settings import (
    GEMINI_API_KEY,
    BUFFER_SIZE,
    SUMMARY_THRESHOLD,
    SUMMARY_PROMPT,
    LLM_MODEL,
)
from database.db_manager import get_db
from database.models import Message, ChatSession


# Configure Gemini
genai.configure(api_key=GEMINI_API_KEY)


class ChatMemory:
    """
    Manages conversation memory for a chat session.
    
    Memory Strategy:
    ================
    1. BUFFER MEMORY (Recent Messages)
       - Keeps the last N message pairs (user + assistant) in full
       - Provides detailed context for recent conversation
       - Default: Last 5 message pairs (10 messages total)
    
    2. SUMMARY MEMORY (Older Messages)
       - Condenses older messages into a summary
       - Preserves key topics and information
       - Updated when buffer exceeds threshold
    
    This hybrid approach balances:
    - Context relevance (recent messages matter more)
    - Token efficiency (don't waste tokens on old details)
    - Information retention (important topics are summarized)
    """
    
    def __init__(self, session_id: int):
        """
        Initialize memory for a specific chat session.
        
        Args:
            session_id: ID of the chat session
        """
        self.session_id = session_id
        self.db = get_db()
        self.buffer_size = BUFFER_SIZE * 2  # Pairs (user + assistant)
        self.summary_threshold = SUMMARY_THRESHOLD
    
    # ========================================================================
    # Message Operations
    # ========================================================================
    
    def add_message(
        self,
        role: str,
        content: str,
        sources: Optional[list[dict]] = None
    ) -> Message:
        """
        Add a message to the conversation memory.
        
        Args:
            role: 'user' or 'assistant'
            content: Message content
            sources: Optional list of source references
            
        Returns:
            Created Message object
        """
        sources_json = json.dumps(sources) if sources else None
        message = self.db.add_message(
            session_id=self.session_id,
            role=role,
            content=content,
            sources=sources_json
        )
        
        # Check if we need to update the summary
        self._maybe_update_summary()
        
        return message
    
    def get_recent_messages(self, n: Optional[int] = None) -> list[Message]:
        """
        Get recent messages from the buffer.
        
        Args:
            n: Number of messages (default: buffer_size)
            
        Returns:
            List of recent messages in chronological order
        """
        if n is None:
            n = self.buffer_size
        return self.db.get_recent_messages(self.session_id, n)
    
    def get_all_messages(self) -> list[Message]:
        """
        Get all messages in the session.
        
        Returns:
            List of all messages in chronological order
        """
        return self.db.get_session_messages(self.session_id)
    
    def get_message_count(self) -> int:
        """
        Get total message count in session.
        
        Returns:
            Number of messages
        """
        return self.db.get_message_count(self.session_id)
    
    # ========================================================================
    # Summary Management
    # ========================================================================
    
    def get_summary(self) -> Optional[str]:
        """
        Get the conversation summary.
        
        Returns:
            Summary string if exists, None otherwise
        """
        session = self.db.get_session(self.session_id)
        return session.summary if session else None
    
    def update_summary(self, summary: str) -> bool:
        """
        Update the conversation summary.
        
        Args:
            summary: New summary text
            
        Returns:
            True if updated successfully
        """
        return self.db.update_session_summary(self.session_id, summary)
    
    def _maybe_update_summary(self):
        """
        Check if summary needs updating and update if necessary.
        
        Summary is updated when:
        - Message count exceeds threshold
        - AND there are messages not yet summarized
        """
        message_count = self.get_message_count()
        
        if message_count >= self.summary_threshold:
            # Get messages beyond the buffer
            all_messages = self.get_all_messages()
            messages_to_summarize = all_messages[:-self.buffer_size]
            
            if messages_to_summarize:
                self._generate_summary(messages_to_summarize)
    
    def _generate_summary(self, messages: list[Message]):
        """
        Generate a summary of the given messages using Gemini.
        
        Args:
            messages: Messages to summarize
        """
        # Format messages for summarization
        conversation_text = self._format_messages_for_summary(messages)
        
        # Get existing summary to incorporate
        existing_summary = self.get_summary()
        
        prompt = SUMMARY_PROMPT + "\n\n"
        
        if existing_summary:
            prompt += f"Previous Summary:\n{existing_summary}\n\n"
        
        prompt += f"New Conversation to Incorporate:\n{conversation_text}"
        
        try:
            model = genai.GenerativeModel(LLM_MODEL)
            response = model.generate_content(prompt)
            new_summary = response.text.strip()
            
            self.update_summary(new_summary)
        except Exception as e:
            print(f"Error generating summary: {e}")
    
    def _format_messages_for_summary(self, messages: list[Message]) -> str:
        """
        Format messages for summarization.
        
        Args:
            messages: Messages to format
            
        Returns:
            Formatted conversation string
        """
        lines = []
        for msg in messages:
            role_label = "User" if msg.role == "user" else "Assistant"
            lines.append(f"{role_label}: {msg.content}")
        return "\n".join(lines)
    
    # ========================================================================
    # Context Building
    # ========================================================================
    
    def get_memory_context(self) -> dict:
        """
        Get the full memory context for prompt building.
        
        Returns:
            Dictionary with:
            - summary: Conversation summary (if exists)
            - recent_messages: Recent message list
            - formatted_history: Ready-to-use formatted string
        """
        summary = self.get_summary()
        recent_messages = self.get_recent_messages()
        
        return {
            'summary': summary,
            'recent_messages': recent_messages,
            'formatted_history': self._format_for_prompt(summary, recent_messages),
        }
    
    def _format_for_prompt(
        self,
        summary: Optional[str],
        recent_messages: list[Message]
    ) -> str:
        """
        Format memory for inclusion in LLM prompt.
        
        Args:
            summary: Conversation summary
            recent_messages: Recent messages
            
        Returns:
            Formatted string for prompt
        """
        parts = []
        
        if summary:
            parts.append("=== Conversation Summary ===")
            parts.append(summary)
            parts.append("")
        
        if recent_messages:
            parts.append("=== Recent Conversation ===")
            for msg in recent_messages:
                role = "User" if msg.role == "user" else "Assistant"
                parts.append(f"{role}: {msg.content}")
        
        return "\n".join(parts)
    
    def format_messages_for_display(self) -> list[dict]:
        """
        Format all messages for UI display.
        
        Returns:
            List of message dictionaries with parsed sources
        """
        messages = self.get_all_messages()
        formatted = []
        
        for msg in messages:
            sources = None
            if msg.sources:
                try:
                    sources = json.loads(msg.sources)
                except json.JSONDecodeError:
                    pass
            
            formatted.append({
                'role': msg.role,
                'content': msg.content,
                'sources': sources,
                'created_at': msg.created_at,
            })
        
        return formatted


class SessionManager:
    """
    Manages chat sessions for a user.
    
    Provides functionality for:
    - Creating new sessions
    - Switching between sessions
    - Listing user's sessions
    - Auto-titling sessions based on first message
    """
    
    def __init__(self, user_id: int):
        """
        Initialize session manager for a user.
        
        Args:
            user_id: ID of the user
        """
        self.user_id = user_id
        self.db = get_db()
    
    def create_session(self, title: str = "New Chat") -> ChatSession:
        """
        Create a new chat session.
        
        Args:
            title: Optional session title
            
        Returns:
            Created ChatSession object
        """
        return self.db.create_session(self.user_id, title)
    
    def get_session(self, session_id: int) -> Optional[ChatSession]:
        """
        Get a specific session.
        
        Args:
            session_id: Session ID
            
        Returns:
            ChatSession if found and belongs to user, None otherwise
        """
        session = self.db.get_session(session_id)
        
        # Verify session belongs to user
        if session and session.user_id == self.user_id:
            return session
        return None
    
    def get_all_sessions(self, limit: int = 50) -> list[ChatSession]:
        """
        Get all sessions for the user.
        
        Args:
            limit: Maximum sessions to return
            
        Returns:
            List of ChatSession objects, most recent first
        """
        return self.db.get_user_sessions(self.user_id, limit)
    
    def delete_session(self, session_id: int) -> bool:
        """
        Delete a session.
        
        Args:
            session_id: Session ID to delete
            
        Returns:
            True if deleted, False otherwise
        """
        # Verify ownership first
        session = self.get_session(session_id)
        if session:
            return self.db.delete_session(session_id)
        return False
    
    def update_session_title(self, session_id: int, title: str) -> bool:
        """
        Update session title.
        
        Args:
            session_id: Session ID
            title: New title
            
        Returns:
            True if updated, False otherwise
        """
        # Verify ownership
        session = self.get_session(session_id)
        if session:
            return self.db.update_session_title(session_id, title)
        return False
    
    def auto_title_session(self, session_id: int, first_message: str) -> bool:
        """
        Automatically generate a title from the first message.
        
        Args:
            session_id: Session ID
            first_message: First user message
            
        Returns:
            True if title was updated
        """
        # Take first 50 chars of message as title
        title = first_message[:50].strip()
        if len(first_message) > 50:
            title += "..."
        
        return self.update_session_title(session_id, title)
    
    def get_or_create_session(self) -> ChatSession:
        """
        Get existing session or create a new one.
        
        Returns the most recent session if one exists,
        otherwise creates a new session.
        
        Returns:
            ChatSession object
        """
        sessions = self.get_all_sessions(limit=1)
        
        if sessions:
            return sessions[0]
        
        return self.create_session()


# ============================================================================
# Memory Helper Functions
# ============================================================================

def get_chat_memory(session_id: int) -> ChatMemory:
    """
    Get a ChatMemory instance for a session.
    
    Args:
        session_id: Session ID
        
    Returns:
        ChatMemory instance
    """
    return ChatMemory(session_id)


def get_session_manager(user_id: int) -> SessionManager:
    """
    Get a SessionManager instance for a user.
    
    Args:
        user_id: User ID
        
    Returns:
        SessionManager instance
    """
    return SessionManager(user_id)
