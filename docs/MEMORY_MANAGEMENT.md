# Memory Management in Seerah Q&A

This document explains how conversation memory is managed in the Seerah Q&A application, enabling contextual conversations and follow-up questions.

## Overview

The memory system uses a **hybrid approach** combining:
1. **Buffer Memory**: Recent messages kept in full detail
2. **Summary Memory**: Condensed history of older messages

This balances context relevance, token efficiency, and information retention.

## Why Memory Matters in RAG

Without memory, each question is treated independently:

```
User: "Who was Abu Talib?"
Assistant: "Abu Talib was the uncle of Prophet Muhammad..."

User: "When did he die?"
Assistant: "I don't have enough context. Who are you asking about?"
```

With memory, conversations flow naturally:

```
User: "Who was Abu Talib?"
Assistant: "Abu Talib was the uncle of Prophet Muhammad..."

User: "When did he die?"
Assistant: "Abu Talib died in the Year of Sorrow (619 CE)..."
```

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Per-User Storage                          │
├─────────────────────────────────────────────────────────────┤
│  user_id → [Session 1] → [Messages Array]                   │
│           [Session 2] → [Messages Array]                    │
│           [Session 3] → [Messages Array]                    │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│                    Memory Types                              │
├─────────────────────────────────────────────────────────────┤
│  Buffer Memory    │ Last N messages in full detail          │
│  Summary Memory   │ Condensed history of older messages     │
│  Hybrid           │ Buffer + Summary (what we use)          │
└─────────────────────────────────────────────────────────────┘
```

## How It Works

### 1. Session-Based Storage

Each user can have multiple chat sessions:

```python
# Database schema
users → chat_sessions → messages
  │         │              │
  │         │              ├── id
  │         │              ├── role ('user' or 'assistant')
  │         │              ├── content
  │         │              └── sources (JSON)
  │         │
  │         ├── id
  │         ├── user_id
  │         ├── title
  │         ├── summary (condensed history)
  │         └── timestamps
  │
  ├── id
  ├── username
  └── password_hash
```

### 2. Buffer Memory

The most recent messages are kept in full:

```python
BUFFER_SIZE = 5  # Number of message pairs (user + assistant)

# Get recent messages for context
recent_messages = get_last_n_messages(session_id, n=10)
```

**Why buffer memory?**
- Recent messages are most relevant for follow-ups
- Full detail captures nuance and context
- Manageable token count

### 3. Summary Memory

When the conversation exceeds the buffer threshold, older messages are summarized:

```python
SUMMARY_THRESHOLD = 10  # Messages before summarizing

def update_summary(session_id):
    # Get messages beyond the buffer
    all_messages = get_all_messages()
    old_messages = all_messages[:-buffer_size]
    
    # Generate summary using LLM
    summary = llm.summarize(old_messages)
    
    # Store in database
    db.update_session_summary(session_id, summary)
```

**Summary prompt:**
```
Summarize the following conversation concisely, capturing:
1. Main questions asked by the user
2. Key information provided in responses
3. Any specific Seerah topics covered

Keep the summary brief but informative for maintaining conversation context.
```

### 4. Query Processing Flow

```python
def process_query(user_id, session_id, query):
    # 1. Load recent messages (buffer)
    recent_messages = get_last_n_messages(session_id, n=5)
    
    # 2. Load conversation summary (if exists)
    summary = get_session_summary(session_id)
    
    # 3. Retrieve relevant chunks from vector DB
    context_chunks = retriever.search(query, k=5)
    
    # 4. Build prompt with memory + context
    prompt = build_prompt(
        system_prompt=SYSTEM_PROMPT,
        summary=summary,
        recent_messages=recent_messages,
        context=context_chunks,
        query=query
    )
    
    # 5. Get response from Gemini
    response = gemini.generate(prompt)
    
    # 6. Save to database
    save_message(session_id, "user", query)
    save_message(session_id, "assistant", response)
    
    # 7. Update summary if buffer exceeds threshold
    if get_message_count(session_id) > SUMMARY_THRESHOLD:
        update_summary(session_id)
    
    return response
```

## Prompt Structure

The final prompt sent to the LLM:

```
[System Prompt]
You are a knowledgeable Islamic scholar assistant specializing in the Seerah...

[Summary (if exists)]
=== Conversation Summary ===
User asked about Abu Talib and his role in protecting the Prophet.
Topics covered: Early Meccan period, Year of Sorrow.

[Recent Messages]
=== Recent Conversation ===
User: Tell me about the Year of Sorrow
Assistant: The Year of Sorrow (Aam al-Huzn) refers to 619 CE...
User: Who else died that year?
Assistant: Khadijah, the Prophet's beloved wife, also passed away...

[Retrieved Context]
=== Knowledge Base Context ===
[Source 1: Lecture 45 - The Year of Sorrow]
The Year of Sorrow marked a turning point...

[Source 2: Lecture 23 - Abu Talib's Protection]
Abu Talib served as the Prophet's protector...

[Current Query]
=== Current Question ===
How did the Prophet cope with these losses?

Provide a helpful, accurate answer based on the context.
```

## Token Management

To avoid exceeding context limits:

```python
MAX_CONTEXT_TOKENS = 4000

def build_context(summary, recent_messages, chunks):
    total_tokens = 0
    context_parts = []
    
    # Add summary first (usually small)
    if summary:
        tokens = estimate_tokens(summary)
        if total_tokens + tokens < MAX_CONTEXT_TOKENS:
            context_parts.append(summary)
            total_tokens += tokens
    
    # Add recent messages
    for msg in recent_messages:
        tokens = estimate_tokens(msg.content)
        if total_tokens + tokens < MAX_CONTEXT_TOKENS:
            context_parts.append(msg)
            total_tokens += tokens
    
    # Add chunks (most important)
    for chunk in chunks:
        tokens = estimate_tokens(chunk.text)
        if total_tokens + tokens < MAX_CONTEXT_TOKENS:
            context_parts.append(chunk)
            total_tokens += tokens
    
    return context_parts
```

## Database Persistence

All memory is persisted in SQLite:

```sql
-- Messages table stores full conversation history
CREATE TABLE messages (
    id INTEGER PRIMARY KEY,
    session_id INTEGER REFERENCES chat_sessions(id),
    role TEXT NOT NULL,
    content TEXT NOT NULL,
    sources TEXT,  -- JSON string of source citations
    created_at TIMESTAMP
);

-- Sessions store summary for older messages
CREATE TABLE chat_sessions (
    id INTEGER PRIMARY KEY,
    user_id INTEGER REFERENCES users(id),
    title TEXT,
    summary TEXT,  -- Condensed history
    created_at TIMESTAMP,
    updated_at TIMESTAMP
);
```

## Implementation Classes

### ChatMemory

Manages memory for a single session:

```python
class ChatMemory:
    def __init__(self, session_id: int):
        self.session_id = session_id
        self.buffer_size = 10  # Messages
        
    def add_message(self, role, content, sources=None):
        """Add message and potentially update summary."""
        
    def get_recent_messages(self, n=None):
        """Get buffer of recent messages."""
        
    def get_summary(self):
        """Get conversation summary."""
        
    def get_memory_context(self):
        """Get full memory context for prompt building."""
```

### SessionManager

Manages multiple sessions per user:

```python
class SessionManager:
    def __init__(self, user_id: int):
        self.user_id = user_id
        
    def create_session(self, title="New Chat"):
        """Create a new chat session."""
        
    def get_all_sessions(self, limit=50):
        """Get user's sessions, most recent first."""
        
    def delete_session(self, session_id):
        """Delete a session and its messages."""
```

## Configuration

Adjust memory behavior in `config/settings.py`:

```python
# Memory Configuration
BUFFER_SIZE = 5          # Message pairs to keep in full
SUMMARY_THRESHOLD = 10   # Messages before summarizing
MAX_CONTEXT_TOKENS = 4000  # Maximum tokens for context
```

## Best Practices

1. **Keep buffer size reasonable**: 5-10 message pairs is usually enough
2. **Summarize periodically**: Don't wait too long to summarize
3. **Prioritize recent context**: Recent messages matter more than old ones
4. **Monitor token usage**: Stay within LLM context limits
5. **Persist everything**: Never rely solely on in-memory storage

## Debugging Memory Issues

```python
# Check memory state
memory = ChatMemory(session_id)

# View recent messages
for msg in memory.get_recent_messages():
    print(f"{msg.role}: {msg.content[:50]}...")

# Check summary
summary = memory.get_summary()
print(f"Summary: {summary}")

# Check total message count
count = memory.get_message_count()
print(f"Total messages: {count}")
```

## Future Improvements

1. **Semantic compression**: Use embeddings to identify most important past messages
2. **Entity tracking**: Track mentioned people, places, events across conversation
3. **Dynamic buffer sizing**: Adjust based on conversation complexity
4. **Cross-session memory**: Reference relevant info from past sessions
