# System Overview

A comprehensive guide to how all components of the Seerah Q&A application work together.

## High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           SEERAH Q&A SYSTEM                                  │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│   USER                                                                       │
│    │                                                                         │
│    │ HTTPS Request                                                           │
│    ▼                                                                         │
│  ┌────────────────────────────────────────────────────────────────────────┐ │
│  │                        STREAMLIT FRONTEND                               │ │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐                  │ │
│  │  │ Auth Page    │  │ Chat UI      │  │ Session      │                  │ │
│  │  │ Login/Reg    │  │ Messages     │  │ Management   │                  │ │
│  │  └──────────────┘  └──────────────┘  └──────────────┘                  │ │
│  └───────────────────────────────┬────────────────────────────────────────┘ │
│                                  │                                           │
│                                  ▼                                           │
│  ┌────────────────────────────────────────────────────────────────────────┐ │
│  │                          CORE MODULES                                   │ │
│  │                                                                         │ │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌────────────┐ │ │
│  │  │ AuthManager  │  │ Guardrails   │  │ Retriever    │  │ ChatMemory │ │ │
│  │  │              │  │              │  │ (RAG)        │  │            │ │ │
│  │  │ • Register   │  │ • Filter     │  │ • Embed      │  │ • Store    │ │ │
│  │  │ • Login      │  │ • Classify   │  │ • Search     │  │ • Load     │ │ │
│  │  │ • Session    │  │ • Redirect   │  │ • Generate   │  │ • Summary  │ │ │
│  │  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘  └─────┬──────┘ │ │
│  └─────────┼─────────────────┼─────────────────┼────────────────┼────────┘ │
│            │                 │                 │                │          │
│            ▼                 ▼                 ▼                ▼          │
│  ┌────────────────────────────────────────────────────────────────────────┐ │
│  │                         DATA LAYER                                      │ │
│  │                                                                         │ │
│  │  ┌──────────────────┐  ┌──────────────────┐  ┌──────────────────────┐ │ │
│  │  │     SQLite       │  │    ChromaDB      │  │    Gemini API        │ │ │
│  │  │                  │  │                  │  │                      │ │ │
│  │  │  Users           │  │  Embeddings      │  │  Generation          │ │ │
│  │  │  Sessions        │  │  Transcripts     │  │  Classification      │ │ │
│  │  │  Messages        │  │  Metadata        │  │                      │ │ │
│  │  │                  │  │                  │  │                      │ │ │
│  │  │  /data/seerah.db │  │  /app/data/      │  │  api.google.com      │ │ │
│  │  └──────────────────┘  └──────────────────┘  └──────────────────────┘ │ │
│  │                                                                         │ │
│  └─────────────────────────────────────────────────────────────────────────┘ │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Component Details

### 1. Streamlit Frontend (`app.py`)

The main entry point that handles:
- Page configuration and styling
- Authentication flow
- Chat interface rendering
- Session management sidebar

```python
# Simplified flow
def main():
    # 1. Check API key
    if not GEMINI_API_KEY:
        show_error()
        return
    
    # 2. Initialize session state
    init_session_state()
    
    # 3. Require authentication
    if not require_auth(auth_manager):
        return  # Shows login page
    
    # 4. Ensure user has a chat session
    ensure_session_exists()
    
    # 5. Render the app
    render_sidebar()      # Session list, logout
    render_chat_interface()  # Chat messages, input
```

### 2. Authentication (`core/auth_manager.py`)

Handles user registration, login, and session state:

```
┌─────────────────────────────────────────────────────────────┐
│                    AUTHENTICATION FLOW                       │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  REGISTRATION                                                │
│  ───────────                                                 │
│  User Input ──▶ Validate ──▶ Check Whitelist ──▶ Hash PW    │
│                    │              │                  │       │
│                    │              ▼                  ▼       │
│                    │         ALLOWED_USERNAMES    bcrypt    │
│                    │         ['dad','mom',...]    salted    │
│                    │              │                  │       │
│                    │              ▼                  ▼       │
│                    └────────▶ Check User Count ──▶ SQLite   │
│                                   │               INSERT    │
│                                   ▼                         │
│                               MAX_USERS                     │
│                                                              │
│  LOGIN                                                       │
│  ─────                                                       │
│  User Input ──▶ Query SQLite ──▶ Verify bcrypt ──▶ Session  │
│                                                    State    │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

**Key security features**:
- Password hashing with bcrypt (salted)
- Username whitelist (configurable)
- Maximum user limit
- Session-based authentication

### 3. Content Guardrails (`core/guardrails.py`)

Two-tier content moderation system:

```
┌─────────────────────────────────────────────────────────────┐
│                    GUARDRAILS FLOW                           │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  User Query                                                  │
│      │                                                       │
│      ▼                                                       │
│  ┌─────────────────────────────────┐                        │
│  │ TIER 1: Keyword Filter (Fast)   │                        │
│  │                                 │                        │
│  │ Check against BLOCKED_PATTERNS  │                        │
│  │ (profanity, hate speech, etc.)  │                        │
│  └────────────────┬────────────────┘                        │
│                   │                                          │
│          Match? ──┼── Yes ──▶ BLOCK (return polite refusal) │
│                   │                                          │
│                   No                                         │
│                   │                                          │
│                   ▼                                          │
│  ┌─────────────────────────────────┐                        │
│  │ Check Relevant Keywords         │                        │
│  │                                 │                        │
│  │ RELEVANT_KEYWORDS list          │                        │
│  │ (prophet, seerah, battle, etc.) │                        │
│  └────────────────┬────────────────┘                        │
│                   │                                          │
│          Match? ──┼── Yes ──▶ ALLOW (proceed to RAG)        │
│                   │                                          │
│                   No                                         │
│                   │                                          │
│                   ▼                                          │
│  ┌─────────────────────────────────┐                        │
│  │ TIER 2: LLM Classification      │                        │
│  │                                 │                        │
│  │ Gemini classifies as:           │                        │
│  │ • RELEVANT → ALLOW              │                        │
│  │ • OFF_TOPIC → REDIRECT          │                        │
│  │ • INAPPROPRIATE → BLOCK         │                        │
│  └─────────────────────────────────┘                        │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

### 4. RAG Retriever (`core/retriever.py`)

The core intelligence of the system:

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                          RAG PIPELINE                                        │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  "Who was Khadijah?"                                                         │
│         │                                                                    │
│         ▼                                                                    │
│  ┌─────────────────────────────────────────────────────────────────────────┐│
│  │ STEP 1: EMBED QUERY                                                      ││
│  │                                                                          ││
│  │  sentence-transformers/all-MiniLM-L6-v2                                  ││
│  │  "Who was Khadijah?" ──▶ [0.12, -0.34, 0.56, ...] (384 dimensions)      ││
│  │                                                                          ││
│  │  Runs LOCALLY (free, no API call)                                        ││
│  └─────────────────────────────────────────────────────────────────────────┘│
│         │                                                                    │
│         ▼                                                                    │
│  ┌─────────────────────────────────────────────────────────────────────────┐│
│  │ STEP 2: VECTOR SEARCH                                                    ││
│  │                                                                          ││
│  │  ChromaDB.query(embedding, top_k=5)                                      ││
│  │                                                                          ││
│  │  Returns 5 most similar transcript chunks:                               ││
│  │  ┌──────────────────────────────────────────────────────────────────┐   ││
│  │  │ Chunk 1: "Khadijah bint Khuwaylid was a successful merchant..."  │   ││
│  │  │ Chunk 2: "The Prophet married Khadijah when he was 25..."        │   ││
│  │  │ Chunk 3: "She was the first to believe in his prophethood..."    │   ││
│  │  │ ...                                                               │   ││
│  │  └──────────────────────────────────────────────────────────────────┘   ││
│  └─────────────────────────────────────────────────────────────────────────┘│
│         │                                                                    │
│         ▼                                                                    │
│  ┌─────────────────────────────────────────────────────────────────────────┐│
│  │ STEP 3: BUILD CONTEXT                                                    ││
│  │                                                                          ││
│  │  [Source 1: Lecture 15 - The Prophet's Marriage]                        ││
│  │  Khadijah bint Khuwaylid was a successful merchant...                   ││
│  │                                                                          ││
│  │  [Source 2: Lecture 16 - Early Revelations]                             ││
│  │  The Prophet married Khadijah when he was 25...                         ││
│  │                                                                          ││
│  │  + Conversation History (if any)                                         ││
│  └─────────────────────────────────────────────────────────────────────────┘│
│         │                                                                    │
│         ▼                                                                    │
│  ┌─────────────────────────────────────────────────────────────────────────┐│
│  │ STEP 4: GENERATE RESPONSE                                                ││
│  │                                                                          ││
│  │  Gemini API Call:                                                        ││
│  │  ┌────────────────────────────────────────────────────────────────────┐ ││
│  │  │ SYSTEM_PROMPT (config/settings.py)                                 │ ││
│  │  │ + Conversation History                                              │ ││
│  │  │ + Retrieved Context                                                 │ ││
│  │  │ + User Question                                                     │ ││
│  │  └────────────────────────────────────────────────────────────────────┘ ││
│  │                                    │                                     ││
│  │                                    ▼                                     ││
│  │  "Khadijah bint Khuwaylid (رضي الله عنها) holds a position of immense   ││
│  │   honor in Islamic history as the first wife of Prophet Muhammad ﷺ..." ││
│  └─────────────────────────────────────────────────────────────────────────┘│
│         │                                                                    │
│         ▼                                                                    │
│  ┌─────────────────────────────────────────────────────────────────────────┐│
│  │ STEP 5: SAVE TO MEMORY                                                   ││
│  │                                                                          ││
│  │  SQLite: INSERT INTO messages (session_id, role, content, sources)      ││
│  └─────────────────────────────────────────────────────────────────────────┘│
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 5. Chat Memory (`core/chat_memory.py`)

Manages conversation history with a hybrid approach:

```
┌─────────────────────────────────────────────────────────────┐
│                    MEMORY STRATEGY                           │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  Message History:                                            │
│  ─────────────────                                           │
│  [Msg 1] [Msg 2] [Msg 3] ... [Msg 8] [Msg 9] [Msg 10]       │
│     │      │       │           │       │       │             │
│     └──────┴───────┴─ OLDER ───┴───────┴───────┘             │
│                       │                    │                 │
│                       ▼                    ▼                 │
│              ┌─────────────────┐  ┌─────────────────┐       │
│              │ SUMMARIZED      │  │ BUFFER          │       │
│              │                 │  │ (Full Detail)   │       │
│              │ "User asked     │  │                 │       │
│              │ about Khadijah, │  │ Last 5 Q&A      │       │
│              │ then the Battle │  │ pairs kept      │       │
│              │ of Badr..."     │  │ verbatim        │       │
│              └────────┬────────┘  └────────┬────────┘       │
│                       │                    │                 │
│                       └────────┬───────────┘                 │
│                                │                             │
│                                ▼                             │
│                       ┌─────────────────┐                   │
│                       │ CONTEXT SENT    │                   │
│                       │ TO GEMINI       │                   │
│                       │                 │                   │
│                       │ Summary +       │                   │
│                       │ Recent Messages │                   │
│                       └─────────────────┘                   │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

**Configuration** (from `config/settings.py`):
- `BUFFER_SIZE = 5` - Keep last 5 message pairs in full
- `SUMMARY_THRESHOLD = 10` - Summarize after 10 messages
- `MAX_CONTEXT_TOKENS = 4000` - Token limit for context

---

## Data Flow: Complete Request Lifecycle

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    COMPLETE REQUEST LIFECYCLE                                │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  1. USER TYPES QUESTION                                                      │
│     "Tell me about the Battle of Badr"                                       │
│            │                                                                 │
│            ▼                                                                 │
│  2. STREAMLIT RECEIVES INPUT                                                 │
│     st.chat_input("Ask about the Seerah...")                                │
│            │                                                                 │
│            ▼                                                                 │
│  3. PROCESS_USER_QUERY() CALLED                                             │
│     ┌─────────────────────────────────────────────────────────────────┐    │
│     │ a. Display user message in chat                                  │    │
│     │ b. Show "Thinking..." spinner                                    │    │
│     │ c. Call retriever.query_with_memory()                           │    │
│     └─────────────────────────────────────────────────────────────────┘    │
│            │                                                                 │
│            ▼                                                                 │
│  4. GUARDRAILS CHECK                                                         │
│     ┌─────────────────────────────────────────────────────────────────┐    │
│     │ • Keyword filter: No blocked patterns                           │    │
│     │ • Relevance check: "battle" is relevant keyword                 │    │
│     │ • Result: ALLOW                                                  │    │
│     └─────────────────────────────────────────────────────────────────┘    │
│            │                                                                 │
│            ▼                                                                 │
│  5. VECTOR SEARCH                                                            │
│     ┌─────────────────────────────────────────────────────────────────┐    │
│     │ • Embed query with sentence-transformers (local, free)          │    │
│     │ • Query ChromaDB for top 5 similar chunks                       │    │
│     │ • Filter by similarity threshold (0.3)                          │    │
│     └─────────────────────────────────────────────────────────────────┘    │
│            │                                                                 │
│            ▼                                                                 │
│  6. LOAD MEMORY CONTEXT                                                      │
│     ┌─────────────────────────────────────────────────────────────────┐    │
│     │ • Fetch recent messages from SQLite                             │    │
│     │ • Get summary if conversation is long                           │    │
│     │ • Format for LLM context                                        │    │
│     └─────────────────────────────────────────────────────────────────┘    │
│            │                                                                 │
│            ▼                                                                 │
│  7. GENERATE RESPONSE                                                        │
│     ┌─────────────────────────────────────────────────────────────────┐    │
│     │ Gemini API Call:                                                 │    │
│     │ • System prompt (scholarly tone, structure, citations)          │    │
│     │ • Memory context (previous conversation)                        │    │
│     │ • Retrieved chunks (transcript excerpts)                        │    │
│     │ • Current question                                              │    │
│     │                                                                  │    │
│     │ Returns: Formatted response with honorifics and citations       │    │
│     └─────────────────────────────────────────────────────────────────┘    │
│            │                                                                 │
│            ▼                                                                 │
│  8. DISPLAY & SAVE                                                           │
│     ┌─────────────────────────────────────────────────────────────────┐    │
│     │ • Display response in chat UI                                   │    │
│     │ • Show source citations with YouTube links                      │    │
│     │ • Save Q&A to SQLite (messages table)                          │    │
│     │ • Update session title if first message                        │    │
│     └─────────────────────────────────────────────────────────────────┘    │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Configuration Hierarchy

```
┌─────────────────────────────────────────────────────────────┐
│                    CONFIGURATION SOURCES                     │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  Priority (highest to lowest):                               │
│                                                              │
│  1. ENVIRONMENT VARIABLES (runtime)                          │
│     ├─ GEMINI_API_KEY                                        │
│     ├─ ALLOWED_USERNAMES                                     │
│     └─ MAX_USERS                                             │
│     │                                                        │
│     │  On HF Spaces: Set via Secrets UI                     │
│     │  Locally: Set via .env file                           │
│     │                                                        │
│     ▼                                                        │
│  2. config/settings.py (defaults)                            │
│     ├─ CHUNK_SIZE = 500                                      │
│     ├─ LLM_MODEL = "gemini-2.0-flash"                       │
│     ├─ RETRIEVAL_TOP_K = 5                                   │
│     ├─ BUFFER_SIZE = 5                                       │
│     └─ SYSTEM_PROMPT = "..."                                 │
│     │                                                        │
│     │  Hardcoded, change requires redeploy                  │
│     │                                                        │
│     ▼                                                        │
│  3. Dockerfile (build-time)                                  │
│     ├─ Python version                                        │
│     ├─ System packages                                       │
│     └─ Port configuration                                    │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

---

## Error Handling

```
┌─────────────────────────────────────────────────────────────┐
│                    ERROR HANDLING LAYERS                     │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  LAYER 1: Input Validation                                   │
│  ─────────────────────────                                   │
│  • Username length check (≥3 chars)                         │
│  • Password length check (≥6 chars)                         │
│  • Alphanumeric username validation                          │
│                                                              │
│  LAYER 2: Authentication                                     │
│  ───────────────────────                                     │
│  • Whitelist check (403-style rejection)                    │
│  • Max users check                                           │
│  • bcrypt verification (timing-safe)                        │
│                                                              │
│  LAYER 3: Content Moderation                                 │
│  ───────────────────────────                                 │
│  • Blocked content → Polite refusal                         │
│  • Off-topic → Redirect message                             │
│  • Classification failure → Allow (fail-open)               │
│                                                              │
│  LAYER 4: RAG Pipeline                                       │
│  ─────────────────────                                       │
│  • Empty results → "I don't have info on this"              │
│  • API timeout → Retry with backoff                         │
│  • API error → Display error message                        │
│                                                              │
│  LAYER 5: Database                                           │
│  ────────────────                                            │
│  • Connection errors → Graceful fallback                    │
│  • Integrity errors → Meaningful message                    │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

---

## File Reference

| File | Purpose | Key Functions |
|------|---------|---------------|
| `app.py` | Main entry | `main()`, `render_chat_interface()` |
| `config/settings.py` | Configuration | All constants, `SYSTEM_PROMPT` |
| `core/auth_manager.py` | Authentication | `register_user()`, `authenticate_user()` |
| `core/guardrails.py` | Content filtering | `check_query()`, `ContentGuardrails` |
| `core/retriever.py` | RAG pipeline | `SeerahRetriever.query()` |
| `core/chat_memory.py` | Conversation memory | `ChatMemory`, `SessionManager` |
| `database/db_manager.py` | SQLite operations | `DatabaseManager` |
| `database/models.py` | Data models | `User`, `ChatSession`, `Message` |
| `data_pipeline/knowledge_base.py` | Build ChromaDB | `build_knowledge_base()` |
| `data_pipeline/transcript_fetcher.py` | Fetch transcripts | `fetch_all_transcripts()` |

---

## Performance Characteristics

| Operation | Time | Cost |
|-----------|------|------|
| First page load | ~10s | Free (model download) |
| Subsequent page loads | ~500ms | Free |
| Vector search | ~100ms | Free (local) |
| Response generation | ~2-5s | Gemini API |
| User registration | ~10ms | Free |
| Message save | ~5ms | Free |

**Monthly costs** (estimated for family use):
- Gemini API: ~$0 (free tier: 1M tokens/month)
- HF Spaces: $0 (free tier)
- Total: **$0/month**
