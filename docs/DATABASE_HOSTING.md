# Database Hosting in Docker

This document explains how the two databases (ChromaDB and SQLite) work inside the Docker container on Hugging Face Spaces.

## Overview: Two Databases, Two Purposes

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         DATABASE ARCHITECTURE                            │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  ┌─────────────────────────────┐    ┌─────────────────────────────┐    │
│  │        CHROMADB             │    │         SQLITE               │    │
│  │    (Knowledge Base)         │    │    (User Database)           │    │
│  ├─────────────────────────────┤    ├─────────────────────────────┤    │
│  │                             │    │                              │    │
│  │  Purpose:                   │    │  Purpose:                    │    │
│  │  • Store transcript chunks  │    │  • User accounts             │    │
│  │  • Store embeddings         │    │  • Chat sessions             │    │
│  │  • Enable semantic search   │    │  • Message history           │    │
│  │                             │    │                              │    │
│  │  Location:                  │    │  Location:                   │    │
│  │  /app/data/chroma_db/       │    │  /data/seerah.db (HF)        │    │
│  │                             │    │  data/seerah.db (local)      │    │
│  │                             │    │                              │    │
│  │  Size: ~59MB                │    │  Size: ~100KB (grows)        │    │
│  │                             │    │                              │    │
│  │  Persistence:               │    │  Persistence:                │    │
│  │  ✓ Bundled in Docker image  │    │  ✓ HF Persistent Storage     │    │
│  │  ✓ Survives restarts        │    │  ✓ Survives restarts         │    │
│  │  ✗ Read-only at runtime     │    │  ✓ Read-write at runtime     │    │
│  │                             │    │                              │    │
│  └─────────────────────────────┘    └─────────────────────────────┘    │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## ChromaDB: The Knowledge Base

### What is ChromaDB?

ChromaDB is a vector database that stores:
1. **Transcript chunks** - Text segments from the 104 Seerah lectures
2. **Embeddings** - 384-dimensional vectors representing each chunk's meaning
3. **Metadata** - Video ID, title, timestamps, lecture number

### File Structure

```
data/chroma_db/
├── chroma.sqlite3                           # Main database (54MB)
│   └── Contains: embeddings, metadata, IDs
│
└── dbe04449-192e-4efa-a4f0-b145529b93ed/   # HNSW index directory
    ├── data_level0.bin                      # Index data
    ├── header.bin                           # Index header
    ├── index_metadata.pickle                # Index config
    ├── length.bin                           # Vector lengths
    └── link_lists.bin                       # Graph connections
```

### How ChromaDB is Built (One-Time, Locally)

```python
# In data_pipeline/knowledge_base.py

# 1. Load transcripts
transcripts = load_all_transcripts()  # 104 JSON files

# 2. Chunk the text
chunks = []
for transcript in transcripts:
    chunks.extend(semantic_chunk(transcript))  # ~5000 chunks total

# 3. Generate embeddings (using sentence-transformers)
model = SentenceTransformer('all-MiniLM-L6-v2')
embeddings = model.encode([c.text for c in chunks])

# 4. Store in ChromaDB
collection.add(
    documents=[c.text for c in chunks],
    embeddings=embeddings,
    metadatas=[c.metadata for c in chunks],
    ids=[c.id for c in chunks]
)
```

### How ChromaDB is Deployed

```
LOCAL                          GIT LFS                       DOCKER
─────                          ───────                       ──────

data/chroma_db/    ───────▶   Stored as LFS    ───────▶   /app/data/chroma_db/
(59MB)                         objects on                  (copied during
                               HF servers                   docker build)
```

The ChromaDB files are:
1. **Too large for regular Git** (54MB sqlite3 file)
2. **Tracked with Git LFS** (Large File Storage)
3. **Downloaded during build** when HF clones the repo
4. **Copied into Docker image** via `COPY . .`

### How ChromaDB is Queried at Runtime

```python
# In core/retriever.py

class SeerahRetriever:
    def __init__(self):
        # Connect to ChromaDB (read-only)
        self._client = chromadb.PersistentClient(
            path=str(CHROMA_DB_DIR),  # /app/data/chroma_db/
            settings=Settings(anonymized_telemetry=False)
        )
        self._collection = self._client.get_collection("seerah_knowledge_base")
    
    def retrieve(self, query: str, top_k: int = 5):
        # 1. Embed the query
        query_embedding = self.embed_query(query)
        
        # 2. Find similar chunks
        results = self._collection.query(
            query_embeddings=[query_embedding],
            n_results=top_k
        )
        
        return results
```

### ChromaDB is Read-Only in Production

**Why read-only?**
- The knowledge base is pre-built and doesn't change
- No need to add new vectors at runtime
- Prevents accidental corruption

**What if you need to update the knowledge base?**
1. Rebuild locally with new transcripts
2. Push updated files to HF
3. Space rebuilds with new data

---

## SQLite: The User Database

### What SQLite Stores

```sql
-- Users table
CREATE TABLE users (
    id INTEGER PRIMARY KEY,
    username TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,  -- bcrypt hash
    created_at TIMESTAMP
);

-- Chat sessions
CREATE TABLE chat_sessions (
    id INTEGER PRIMARY KEY,
    user_id INTEGER,
    title TEXT,
    summary TEXT,
    created_at TIMESTAMP,
    updated_at TIMESTAMP
);

-- Messages
CREATE TABLE messages (
    id INTEGER PRIMARY KEY,
    session_id INTEGER,
    role TEXT,          -- 'user' or 'assistant'
    content TEXT,
    sources TEXT,       -- JSON array of citations
    created_at TIMESTAMP
);
```

### The Persistence Problem

**Challenge**: Docker containers are ephemeral. When a container restarts, all filesystem changes are lost.

```
Container Start          Container Running         Container Restart
───────────────          ─────────────────         ─────────────────

/app/data/seerah.db      User registers            /app/data/seerah.db
(empty)                  User chats                (empty again!)
                         Data written to file      All data lost!
```

### The Solution: HF Persistent Storage

Hugging Face Spaces provides a persistent `/data` directory that survives container restarts.

```python
# In config/settings.py

# Detect if running on HF Spaces
IS_HUGGINGFACE = os.getenv("SPACE_ID") is not None

if IS_HUGGINGFACE:
    # Use persistent storage
    DATABASE_PATH = Path("/data/seerah.db")
else:
    # Local development
    DATABASE_PATH = Path("data/seerah.db")
```

### How Persistent Storage Works

```
┌─────────────────────────────────────────────────────────────────────────┐
│                    HF SPACES PERSISTENT STORAGE                          │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │                     DOCKER CONTAINER                             │   │
│  │                                                                  │   │
│  │  Ephemeral Storage (lost on restart):                           │   │
│  │  ┌────────────────────────────────────────────────────────────┐ │   │
│  │  │  /app/                                                      │ │   │
│  │  │  ├── app.py                                                 │ │   │
│  │  │  ├── config/                                                │ │   │
│  │  │  ├── core/                                                  │ │   │
│  │  │  └── data/chroma_db/  (read-only knowledge base)           │ │   │
│  │  └────────────────────────────────────────────────────────────┘ │   │
│  │                                                                  │   │
│  │  Persistent Storage (survives restart):                         │   │
│  │  ┌────────────────────────────────────────────────────────────┐ │   │
│  │  │  /data/                          ◄──── Mounted from HF     │ │   │
│  │  │  └── seerah.db                        persistent storage   │ │   │
│  │  └────────────────────────────────────────────────────────────┘ │   │
│  │                                                                  │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│                                                                          │
│                              │                                           │
│                              │ Volume Mount                              │
│                              ▼                                           │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │                    HF STORAGE BACKEND                            │   │
│  │                                                                  │   │
│  │  /data/seerah.db  ───────▶  Persisted across container restarts │   │
│  │                                                                  │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

### Database Initialization Flow

```python
# In database/db_manager.py

class DatabaseManager:
    def __init__(self, db_path: Path = DATABASE_PATH):
        self.db_path = Path(db_path)
        
        # Ensure parent directory exists
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Initialize schema if database is new
        self._init_database()
    
    def _init_database(self):
        """Create tables if they don't exist."""
        with self.get_connection() as conn:
            conn.executescript(SCHEMA_SQL)
            conn.commit()
```

**First container start**:
1. `/data/` directory is empty
2. App creates `/data/seerah.db`
3. Schema is initialized
4. Users can register

**Subsequent restarts**:
1. `/data/seerah.db` already exists
2. App opens existing database
3. All users and chats preserved

---

## Environment-Specific Behavior

### Local Development

```
┌─────────────────────────────────────────┐
│         LOCAL DEVELOPMENT               │
├─────────────────────────────────────────┤
│                                         │
│  ChromaDB: data/chroma_db/              │
│  SQLite:   data/seerah.db               │
│                                         │
│  Both in project directory              │
│  Both read-write                        │
│  Persist across app restarts            │
│                                         │
└─────────────────────────────────────────┘
```

### Hugging Face Spaces

```
┌─────────────────────────────────────────┐
│         HUGGING FACE SPACES             │
├─────────────────────────────────────────┤
│                                         │
│  ChromaDB: /app/data/chroma_db/         │
│  ├── Bundled in Docker image            │
│  ├── Read-only (pre-built)              │
│  └── Survives restarts (in image)       │
│                                         │
│  SQLite:   /data/seerah.db              │
│  ├── HF Persistent Storage              │
│  ├── Read-write                         │
│  └── Survives restarts (persistent)     │
│                                         │
└─────────────────────────────────────────┘
```

### Detection Code

```python
# How the app knows where it's running

import os

# HF Spaces sets SPACE_ID environment variable
IS_HUGGINGFACE = os.getenv("SPACE_ID") is not None

# Example values:
# Local:  SPACE_ID = None
# HF:     SPACE_ID = "Etqad/seerah-app"
```

---

## Database Operations

### User Registration

```python
# 1. Check whitelist
if ALLOWED_USERNAMES and username.lower() not in ALLOWED_USERNAMES:
    return False, "Username not authorized"

# 2. Check user limit
if db.count_users() >= MAX_USERS:
    return False, "Maximum users reached"

# 3. Hash password
password_hash = bcrypt.hashpw(password.encode(), bcrypt.gensalt())

# 4. Insert into SQLite
cursor.execute(
    "INSERT INTO users (username, password_hash) VALUES (?, ?)",
    (username, password_hash)
)
# Writes to /data/seerah.db on HF Spaces
```

### Saving Chat Messages

```python
# After generating a response
memory.add_message('user', query)
memory.add_message('assistant', response.answer, sources=sources)

# This writes to SQLite:
cursor.execute(
    "INSERT INTO messages (session_id, role, content, sources) VALUES (?, ?, ?, ?)",
    (session_id, role, content, json.dumps(sources))
)
```

### Querying ChromaDB

```python
# Semantic search
results = collection.query(
    query_embeddings=[embedding],
    n_results=5,
    include=['documents', 'metadatas', 'distances']
)

# Returns:
# {
#   'documents': [['chunk1 text', 'chunk2 text', ...]],
#   'metadatas': [[{video_id, title, ...}, ...]],
#   'distances': [[0.23, 0.31, ...]]
# }
```

---

## Backup and Recovery

### ChromaDB

**No backup needed** - it's pre-built and stored in Git LFS. To recover:
1. Re-clone the repository
2. Rebuild the Docker image

### SQLite User Database

**Currently no automatic backup**. If the database is lost:
1. Users need to re-register
2. Chat history is lost

**Future improvement**: Could export to HF Dataset or external storage.

---

## Performance Considerations

### ChromaDB Query Performance

| Operation | Time | Notes |
|-----------|------|-------|
| First query | ~10s | Loads embedding model |
| Subsequent queries | ~100ms | Model cached |
| Vector search | ~10ms | HNSW index is fast |

### SQLite Write Performance

| Operation | Time | Notes |
|-----------|------|-------|
| User registration | ~10ms | Single insert |
| Save message | ~5ms | Single insert |
| Load session | ~20ms | Multiple selects |

**Note**: SQLite on `/data/` may be slower than local SSD due to network storage, but still fast enough for this use case.

---

## Summary

| Aspect | ChromaDB | SQLite |
|--------|----------|--------|
| **Purpose** | Knowledge base (transcripts) | User data (accounts, chats) |
| **Location (HF)** | `/app/data/chroma_db/` | `/data/seerah.db` |
| **Size** | ~59MB (fixed) | ~100KB+ (grows) |
| **Access** | Read-only | Read-write |
| **Persistence** | Bundled in image | HF Persistent Storage |
| **Survives restart** | Yes | Yes |
| **Updated by** | Developer (rebuild) | App at runtime |
