# Seerah RAG - Code Reading Guide

A straightforward guide to understanding the codebase. Start from the top and work your way down.

---

## Quick Overview

This is a RAG (Retrieval-Augmented Generation) application for learning about the Seerah (biography of Prophet Muhammad ﷺ). It uses:
- **Streamlit** for the web UI
- **ChromaDB** for vector storage
- **HuggingFace sentence-transformers** for embeddings (free, local)
- **Google Gemini** for LLM responses
- **SQLite** for user authentication and chat history

---

## Recommended Reading Order

### 1. Start Here: Configuration
**File:** `config/settings.py`

This is your foundation. Read this first to understand:
- Environment variables (API keys, paths)
- Chunking parameters
- Model configurations
- System prompts

```
config/
└── settings.py          # All configuration in one place
```

### 2. Data Pipeline (How data flows in)
**Start with:** `data_pipeline/hf_data_loader.py` → `knowledge_base.py`

```
data_pipeline/
├── hf_data_loader.py    # Loads transcripts from HuggingFace
├── knowledge_base.py    # Chunks text, creates embeddings, stores in ChromaDB
└── transcript_fetcher.py # Legacy: fetches from YouTube (optional reading)
```

**Key functions to understand:**
- `load_seerah_dataset()` - Pulls data from HuggingFace
- `chunk_text()` - Splits transcripts into semantic chunks
- `build_vector_store()` - Creates ChromaDB collection with embeddings

### 3. Core Logic (How queries work)
**Start with:** `retriever.py` → `chat_memory.py` → `guardrails.py`

```
core/
├── retriever.py         # RAG pipeline: query → retrieve → generate
├── chat_memory.py       # Conversation history per session
├── guardrails.py        # Content moderation
└── auth_manager.py      # User authentication
```

**The main flow in `retriever.py`:**
1. User asks a question
2. Question is embedded using sentence-transformers
3. Similar chunks are retrieved from ChromaDB
4. Context is built from chunks
5. Gemini generates a response with the context

### 4. Database Layer
**File:** `database/db_manager.py` and `models.py`

```
database/
├── models.py            # Data structures (User, ChatSession, Message)
└── db_manager.py        # SQLite operations
```

### 5. Main Application
**File:** `app.py`

This ties everything together. The Streamlit app handles:
- Authentication flow
- Chat interface
- Session management
- Response display with sources

---

## Data Flow Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                        BUILD PHASE                               │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  HuggingFace Dataset                                            │
│        │                                                         │
│        ▼                                                         │
│  hf_data_loader.py                                              │
│        │                                                         │
│        ▼                                                         │
│  knowledge_base.py                                              │
│        │                                                         │
│        ├──────► Chunking (semantic text chunks)                 │
│        │                                                         │
│        ├──────► Embedding (sentence-transformers)               │
│        │                                                         │
│        ▼                                                         │
│  ChromaDB (data/chroma_db/)                                     │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│                        QUERY PHASE                               │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  User Query                                                      │
│        │                                                         │
│        ▼                                                         │
│  app.py (Streamlit UI)                                          │
│        │                                                         │
│        ▼                                                         │
│  retriever.py                                                    │
│        │                                                         │
│        ├──────► guardrails.py (content check)                   │
│        │                                                         │
│        ├──────► Embed query (sentence-transformers)             │
│        │                                                         │
│        ├──────► Search ChromaDB (similarity search)             │
│        │                                                         │
│        ├──────► chat_memory.py (add context)                    │
│        │                                                         │
│        ├──────► Gemini LLM (generate response)                  │
│        │                                                         │
│        ▼                                                         │
│  Response + Sources                                              │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

---

## File-by-File Reference

| File | Purpose | Key Classes/Functions |
|------|---------|----------------------|
| `config/settings.py` | All configuration | Constants, paths, prompts |
| `data_pipeline/hf_data_loader.py` | Load HuggingFace data | `load_seerah_dataset()`, `process_dataset_for_embedding()` |
| `data_pipeline/knowledge_base.py` | Build vector store | `chunk_text()`, `build_vector_store()`, `build_knowledge_base()` |
| `core/retriever.py` | RAG pipeline | `SeerahRetriever`, `query()`, `query_with_memory()` |
| `core/chat_memory.py` | Conversation state | `ChatMemory`, `SessionManager` |
| `core/guardrails.py` | Content moderation | `check_query()`, `ContentAction` |
| `core/auth_manager.py` | Authentication | `AuthManager`, `require_auth()` |
| `database/models.py` | Data models | `User`, `ChatSession`, `Message`, `SCHEMA_SQL` |
| `database/db_manager.py` | Database operations | `DatabaseManager`, `get_db()` |
| `app.py` | Main application | `main()`, UI rendering functions |

---

## Key Commands

```bash
# Build knowledge base from HuggingFace (recommended)
python -m data_pipeline.knowledge_base --source huggingface --recreate

# Build from local JSON files (legacy)
python -m data_pipeline.knowledge_base --source local --recreate

# Inspect HuggingFace dataset
python -m data_pipeline.hf_data_loader --inspect

# Run the application
streamlit run app.py
```

---

## Environment Variables

Create a `.env` file with:

```env
# Required
GEMINI_API_KEY=your_gemini_api_key_here

# Access Control (optional - defaults to 10 users)
MAX_USERS=5
ALLOWED_USERNAMES=user1,user2,user3,user4,user5
```

---

## Directory Structure

```
seerah_rag/
├── app.py                    # Main Streamlit application
├── config/
│   └── settings.py           # Configuration
├── core/
│   ├── auth_manager.py       # Authentication
│   ├── chat_memory.py        # Conversation memory
│   ├── guardrails.py         # Content moderation
│   └── retriever.py          # RAG pipeline
├── data/
│   ├── chroma_db/            # Vector database
│   ├── seerah.db             # User/session database
│   └── transcripts/          # Local transcripts (legacy)
├── data_pipeline/
│   ├── hf_data_loader.py     # HuggingFace loader
│   ├── knowledge_base.py     # Embedding pipeline
│   └── transcript_fetcher.py # YouTube fetcher (legacy)
├── database/
│   ├── db_manager.py         # Database operations
│   └── models.py             # Data models
├── docs/                     # Documentation
└── requirements.txt          # Dependencies
```

---

## Tips for Reading the Code

1. **Start with `settings.py`** - This tells you what's configurable
2. **Follow the data** - Trace how transcripts become embeddings
3. **Understand the RAG flow** - `retriever.py` is the heart of the system
4. **Check the prompts** - `SYSTEM_PROMPT` in settings defines AI behavior
5. **Ignore legacy files** - `transcript_fetcher.py` is only needed if you want YouTube data

---

## Quick Reference: The RAG Pipeline

```python
# Simplified version of what happens when you ask a question

def answer_question(query):
    # 1. Check if appropriate
    if not guardrails.is_allowed(query):
        return "I can only answer Seerah questions"
    
    # 2. Convert query to vector
    query_embedding = model.encode(query)
    
    # 3. Find similar chunks in ChromaDB
    chunks = chromadb.query(query_embedding, top_k=5)
    
    # 4. Build context from chunks
    context = "\n".join(chunk.text for chunk in chunks)
    
    # 5. Get conversation history
    history = chat_memory.get_recent_messages()
    
    # 6. Generate response with Gemini
    response = gemini.generate(
        system_prompt + history + context + query
    )
    
    return response
```

---

That's it! Start with `settings.py`, then follow the data flow, and you'll understand the whole system.
