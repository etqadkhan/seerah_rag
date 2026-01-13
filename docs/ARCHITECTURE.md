# System Architecture

This document provides a comprehensive overview of the Seerah Q&A application architecture.

## High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                              USER INTERFACE                              │
│                          (Streamlit - app.py)                           │
├─────────────────────────────────────────────────────────────────────────┤
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐   │
│  │  Auth UI    │  │  Chat UI    │  │  Sidebar    │  │  Sources    │   │
│  │  Login/Reg  │  │  Messages   │  │  Sessions   │  │  Citations  │   │
│  └─────────────┘  └─────────────┘  └─────────────┘  └─────────────┘   │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                              CORE LAYER                                  │
├─────────────────────────────────────────────────────────────────────────┤
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐        │
│  │  auth_manager   │  │  chat_memory    │  │    retriever    │        │
│  │  ─────────────  │  │  ─────────────  │  │  ─────────────  │        │
│  │  • Registration │  │  • Buffer mem   │  │  • Query embed  │        │
│  │  • Login        │  │  • Summary mem  │  │  • Retrieval    │        │
│  │  • Sessions     │  │  • Persistence  │  │  • Generation   │        │
│  └─────────────────┘  └─────────────────┘  └─────────────────┘        │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                            DATABASE LAYER                                │
├─────────────────────────────────────────────────────────────────────────┤
│  ┌─────────────────────────┐    ┌─────────────────────────┐           │
│  │       db_manager        │    │        models           │           │
│  │  ─────────────────────  │    │  ─────────────────────  │           │
│  │  • User CRUD            │    │  • User                 │           │
│  │  • Session CRUD         │    │  • ChatSession          │           │
│  │  • Message CRUD         │    │  • Message              │           │
│  └─────────────────────────┘    └─────────────────────────┘           │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                            STORAGE LAYER                                 │
├─────────────────────────────────────────────────────────────────────────┤
│  ┌─────────────────────┐              ┌─────────────────────┐          │
│  │      SQLite         │              │      ChromaDB       │          │
│  │  ─────────────────  │              │  ─────────────────  │          │
│  │  • Users            │              │  • Embeddings       │          │
│  │  • Chat sessions    │              │  • Chunk metadata   │          │
│  │  • Messages         │              │  • Vector search    │          │
│  │  • Summaries        │              │                     │          │
│  └─────────────────────┘              └─────────────────────┘          │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                          EXTERNAL SERVICES                               │
├─────────────────────────────────────────────────────────────────────────┤
│  ┌─────────────────────┐              ┌─────────────────────┐          │
│  │    Google Gemini    │              │      YouTube        │          │
│  │  ─────────────────  │              │  ─────────────────  │          │
│  │  • text-embedding   │              │  • Transcripts      │          │
│  │  • gemini-1.5-flash │              │  • Metadata         │          │
│  └─────────────────────┘              └─────────────────────┘          │
└─────────────────────────────────────────────────────────────────────────┘
```

## Component Details

### 1. User Interface Layer (`app.py`)

The Streamlit frontend provides:

| Component | Responsibility |
|-----------|---------------|
| Auth UI | Login/registration forms |
| Chat UI | Message display, input handling |
| Sidebar | Session management, history |
| Sources | Citation display with video links |

**Key functions:**
```python
def main()                    # Entry point
def render_sidebar()          # Session list, user info
def render_chat_interface()   # Chat messages, input
def process_user_query()      # Query handling
```

### 2. Core Layer

#### auth_manager.py
Handles user authentication:
- Password hashing (bcrypt)
- Login verification
- Session state management

#### chat_memory.py
Manages conversation context:
- Buffer memory (recent N messages)
- Summary memory (condensed history)
- SQLite persistence

#### retriever.py
RAG pipeline implementation:
- Query embedding
- Vector search
- Response generation

### 3. Database Layer

#### db_manager.py
SQLite operations:
- Connection management
- CRUD operations
- Query execution

#### models.py
Data structures:
- User
- ChatSession
- Message
- SQL schema definitions

### 4. Storage Layer

#### SQLite (seerah.db)
Stores:
- User accounts
- Chat sessions
- Messages
- Conversation summaries

#### ChromaDB (chroma_db/)
Stores:
- Document embeddings
- Chunk metadata
- Vector indices

## Data Pipeline

```
┌──────────────┐    ┌──────────────┐    ┌──────────────┐    ┌──────────────┐
│   YouTube    │───▶│  Transcript  │───▶│  Knowledge   │───▶│   ChromaDB   │
│   Playlist   │    │   Fetcher    │    │    Base      │    │   Storage    │
└──────────────┘    └──────────────┘    └──────────────┘    └──────────────┘
      │                    │                    │                    │
      │                    ▼                    ▼                    ▼
      │             ┌──────────────┐    ┌──────────────┐    ┌──────────────┐
      │             │  Raw JSON    │    │   Chunked    │    │  Embedded    │
      │             │  Transcripts │    │   Documents  │    │   Vectors    │
      └─────────────┴──────────────┴────┴──────────────┴────┴──────────────┘
```

### Data Pipeline Modules

#### hf_data_loader.py (Method 2 - Recommended)
Loads cleaned transcripts from HuggingFace dataset. This is the recommended approach as it doesn't require API keys and provides better quality transcripts.

#### transcript_fetcher.py (Method 1 - Legacy)

```python
# Input: YouTube playlist URL
# Output: JSON files per video

def get_playlist_videos(playlist_id) -> list[dict]
    # Uses yt-dlp to fetch video metadata
    
def fetch_transcript(video_id) -> dict
    # Uses Supadata API for captions
    
def save_transcripts(transcripts, output_dir)
    # Saves JSON with metadata and segments
```

### knowledge_base.py

```python
# Input: Transcript JSON files
# Output: ChromaDB collection

def load_transcripts(transcripts_dir) -> list[dict]
    # Load all JSON files
    
def chunk_transcript(transcript) -> list[dict]
    # Apply chunking strategy
    
def create_embeddings(chunks) -> list[list[float]]
    # Generate Gemini embeddings
    
def build_vector_store(chunks, embeddings)
    # Store in ChromaDB
```

## Query Processing Flow

```
┌─────────┐     ┌─────────────────────────────────────────────────────────┐
│  User   │────▶│                     QUERY PIPELINE                       │
│  Query  │     ├─────────────────────────────────────────────────────────┤
└─────────┘     │  1. Embed Query                                         │
                │     └─▶ Gemini text-embedding-004                       │
                │                                                          │
                │  2. Retrieve Chunks                                      │
                │     └─▶ ChromaDB similarity search (top-k)              │
                │                                                          │
                │  3. Load Memory                                          │
                │     ├─▶ Summary (if exists)                             │
                │     └─▶ Recent messages (buffer)                        │
                │                                                          │
                │  4. Build Prompt                                         │
                │     ├─▶ System prompt                                   │
                │     ├─▶ Memory context                                  │
                │     ├─▶ Retrieved chunks                                │
                │     └─▶ User query                                      │
                │                                                          │
                │  5. Generate Response                                    │
                │     └─▶ Gemini gemini-1.5-flash                         │
                │                                                          │
                │  6. Save to Memory                                       │
                │     ├─▶ Save user message                               │
                │     ├─▶ Save assistant response                         │
                │     └─▶ Update summary (if threshold)                   │
                └─────────────────────────────────────────────────────────┘
                                        │
                                        ▼
                                ┌─────────────┐
                                │  Response   │
                                │  + Sources  │
                                └─────────────┘
```

## File Structure

```
seerah_rag/
│
├── app.py                      # Main Streamlit application
│                               # Entry point, UI rendering
│
├── requirements.txt            # Python dependencies
│
├── config/
│   ├── __init__.py
│   └── settings.py             # All configuration constants
│                               # Paths, API keys, model params
│
├── core/
│   ├── __init__.py
│   ├── auth_manager.py         # User authentication
│   │                           # Registration, login, sessions
│   │
│   ├── chat_memory.py          # Conversation memory
│   │                           # Buffer, summary, persistence
│   │
│   └── retriever.py            # RAG pipeline
│                               # Embed, retrieve, generate
│
├── database/
│   ├── __init__.py
│   ├── db_manager.py           # SQLite operations
│   │                           # Connection, CRUD
│   │
│   └── models.py               # Data models
│                               # User, ChatSession, Message
│
├── data_pipeline/
│   ├── __init__.py
│   ├── hf_data_loader.py       # HuggingFace dataset loader (Method 2 - recommended)
│   ├── transcript_fetcher.py   # YouTube transcript extraction (Method 1 - legacy)
│   │                           # Playlist parsing, download
│   │
│   └── knowledge_base.py       # Embedding pipeline
│                               # Chunking, embedding, storage
│
├── docs/
│   ├── ARCHITECTURE.md         # This file
│   ├── MEMORY_MANAGEMENT.md    # Memory system details
│   ├── CHUNKING_STRATEGY.md    # Chunking approach
│   ├── AUTHENTICATION.md       # Auth system docs
│   └── DEPLOYMENT.md           # HuggingFace deployment
│
└── data/
    ├── transcripts/            # Raw transcript JSONs
    │   └── *.json
    │
    ├── chroma_db/              # Vector database
    │   └── (ChromaDB files)
    │
    └── seerah.db               # SQLite database
```

## Key Design Decisions

### 1. SQLite for User Data

**Why SQLite?**
- Zero configuration
- File-based (easy to deploy)
- Sufficient for moderate user load
- Easy backup (single file)

**Alternative considered:** PostgreSQL
- Better for high concurrency
- Would require additional hosting

### 2. ChromaDB for Vectors

**Why ChromaDB?**
- Python-native
- Persistent storage
- Good free-tier performance
- Simple API

**Alternative considered:** Pinecone
- Better scalability
- Requires API key and external service

### 3. Hybrid Memory

**Why buffer + summary?**
- Balances detail and efficiency
- Recent context most important
- Scalable to long conversations

**Alternative considered:** Full history
- Token limits exceeded quickly
- Expensive API calls

### 4. Streamlit Frontend

**Why Streamlit?**
- Pure Python (no JavaScript)
- Rapid development
- Built-in session state
- Easy HuggingFace deployment

**Alternative considered:** FastAPI + React
- More flexible
- More complex to develop/deploy

## Scalability Considerations

### Current Limits

| Component | Limit | Bottleneck |
|-----------|-------|------------|
| Users | ~1000 | SQLite concurrency |
| Concurrent requests | ~10 | Streamlit server |
| Vector store size | ~50k chunks | ChromaDB memory |
| Response time | ~5-10s | Gemini API |

### Scaling Strategies

1. **More users**: Migrate to PostgreSQL
2. **More concurrency**: Deploy multiple Streamlit instances
3. **More vectors**: Use Pinecone or Weaviate
4. **Faster responses**: Cache common queries

## Security Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                      Security Layers                         │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  ┌─────────────────────────────────────────────────────┐   │
│  │  HTTPS (HuggingFace)                                │   │
│  │  • TLS encryption in transit                        │   │
│  └─────────────────────────────────────────────────────┘   │
│                          │                                   │
│                          ▼                                   │
│  ┌─────────────────────────────────────────────────────┐   │
│  │  Authentication (auth_manager.py)                   │   │
│  │  • bcrypt password hashing                          │   │
│  │  • Session-based access control                     │   │
│  └─────────────────────────────────────────────────────┘   │
│                          │                                   │
│                          ▼                                   │
│  ┌─────────────────────────────────────────────────────┐   │
│  │  Data Isolation                                     │   │
│  │  • User-scoped queries                              │   │
│  │  • Session ownership verification                   │   │
│  └─────────────────────────────────────────────────────┘   │
│                          │                                   │
│                          ▼                                   │
│  ┌─────────────────────────────────────────────────────┐   │
│  │  Secrets Management (HuggingFace Secrets)           │   │
│  │  • API keys stored securely                         │   │
│  │  • Environment variable injection                   │   │
│  └─────────────────────────────────────────────────────┘   │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

## Error Handling

```python
# Global error handling pattern
try:
    response = retriever.query(user_query)
except chromadb.errors.NoDataError:
    st.error("Knowledge base not initialized")
except google.api_core.exceptions.ResourceExhausted:
    st.error("API rate limit reached. Please wait.")
except sqlite3.DatabaseError:
    st.error("Database error. Please try again.")
except Exception as e:
    logger.error(f"Unexpected error: {e}")
    st.error("Something went wrong. Please try again.")
```

## Testing Strategy

| Layer | Test Type | Tools |
|-------|-----------|-------|
| UI | Manual, E2E | Streamlit testing, Selenium |
| Core | Unit tests | pytest |
| Database | Integration | pytest, SQLite in-memory |
| API | Integration | pytest, mocks |

## Monitoring Points

```python
# Key metrics to track
- Query latency (retrieval + generation)
- Error rate by type
- User registrations/logins
- Active sessions
- ChromaDB query performance
- Gemini API usage
```
