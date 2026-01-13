# Deployment Flow

This document explains the complete end-to-end deployment process from local development to a running Hugging Face Space.

## Overview

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         DEPLOYMENT PIPELINE                                  │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  LOCAL DEVELOPMENT          GIT + LFS              HUGGING FACE SPACES     │
│  ─────────────────          ────────               ───────────────────     │
│                                                                             │
│  ┌─────────────┐           ┌─────────┐           ┌─────────────────┐       │
│  │ Code +      │  push     │ GitHub/ │  webhook  │ Docker Build    │       │
│  │ ChromaDB    │ ───────▶  │ HF Repo │ ───────▶  │ on HF Servers   │       │
│  │ (59MB LFS)  │           │         │           │                 │       │
│  └─────────────┘           └─────────┘           └────────┬────────┘       │
│                                                           │                 │
│                                                           ▼                 │
│                                                  ┌─────────────────┐       │
│                                                  │ Running         │       │
│                                                  │ Container       │       │
│                                                  │ (Port 7860)     │       │
│                                                  └─────────────────┘       │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Phase 1: Local Development

### 1.1 Project Structure

```
seerah_rag/
├── app.py                    # Streamlit entry point
├── Dockerfile                # Container definition
├── requirements.txt          # Python dependencies
├── .env                      # LOCAL secrets (never committed)
├── config/
│   └── settings.py           # Configuration + prompts
├── core/
│   ├── auth_manager.py       # User authentication
│   ├── chat_memory.py        # Conversation history
│   ├── guardrails.py         # Content moderation
│   └── retriever.py          # RAG pipeline
├── database/
│   ├── db_manager.py         # SQLite operations
│   └── models.py             # Data models
└── data/
    ├── chroma_db/            # Vector database (59MB)
    │   ├── chroma.sqlite3    # Main ChromaDB file
    │   └── dbe04449-.../     # HNSW index files
    └── seerah.db             # User database (local only)
```

### 1.2 Building the Knowledge Base (One-Time)

```bash
# Step 1: Fetch transcripts from YouTube
# Method 2 (Recommended): Build from HuggingFace dataset (no API keys needed)
python -m data_pipeline.knowledge_base --source huggingface --recreate

# Method 1 (Legacy): If you need to fetch from YouTube instead
# python -m data_pipeline.transcript_fetcher
# Creates: data/transcripts/*.json (104 files)

# Step 2: Build embeddings and vector store
python -m data_pipeline.knowledge_base
# Creates: data/chroma_db/ (59MB)
```

### 1.3 Local Testing

```bash
# Activate virtual environment
source venv/bin/activate

# Set environment variables
export GEMINI_API_KEY=your_key
export ALLOWED_USERNAMES=dad,mom,brother

# Run the app
streamlit run app.py
# Access at http://localhost:8501
```

---

## Phase 2: Preparing for Deployment

### 2.1 Configuration Files

**README.md** (with YAML frontmatter):
```yaml
---
title: Seerah Q&A
emoji: 🕌
colorFrom: green
colorTo: blue
sdk: docker
app_port: 7860
pinned: false
---
```

**Dockerfile**: See [DOCKERFILE_EXPLAINED.md](DOCKERFILE_EXPLAINED.md)

**requirements.txt**:
```
streamlit>=1.28.0
google-generativeai>=0.3.0
chromadb>=0.4.0
bcrypt>=4.0.0
python-dotenv>=1.0.0
sentence-transformers>=2.2.0
# ... other dependencies
```

### 2.2 Git LFS Setup

The ChromaDB files are too large for regular Git (>10MB limit on HF):

```bash
# Install Git LFS
git lfs install

# Track large files (already in .gitattributes)
git lfs track "data/chroma_db/*.sqlite3"
git lfs track "*.bin"
```

---

## Phase 3: Pushing to Hugging Face

### 3.1 Clone HF Space Repository

```bash
git clone https://huggingface.co/spaces/YOUR_USERNAME/YOUR_SPACE
cd YOUR_SPACE
```

### 3.2 Copy Project Files

```bash
# Copy everything except venv and .env
cp -r /path/to/seerah_rag/* .
rm -rf venv
rm .env

# Ensure ChromaDB is included
ls -la data/chroma_db/
```

### 3.3 Commit and Push

```bash
git add -A
git commit -m "Deploy Seerah Q&A"
git push

# Git LFS automatically uploads large files
# Output: "Uploading LFS objects: 100% (6/6), 62 MB"
```

---

## Phase 4: Hugging Face Build Process

### 4.1 What Happens After Push

```
┌─────────────────────────────────────────────────────────────────┐
│                    HF SPACES BUILD PIPELINE                      │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  1. DETECT SDK                                                   │
│     ├─ Reads README.md frontmatter                              │
│     └─ sdk: docker → Uses Dockerfile                            │
│                                                                  │
│  2. PULL LFS FILES                                               │
│     ├─ Downloads chroma.sqlite3 (54MB)                          │
│     └─ Downloads *.bin index files (8MB)                        │
│                                                                  │
│  3. BUILD DOCKER IMAGE                                           │
│     ├─ FROM python:3.11-slim                                    │
│     ├─ Install system deps (apt-get)                            │
│     ├─ Install Python deps (pip)                                │
│     └─ Copy application code                                    │
│                                                                  │
│  4. INJECT SECRETS                                               │
│     ├─ GEMINI_API_KEY → Environment variable                    │
│     ├─ ALLOWED_USERNAMES → Environment variable                 │
│     └─ MAX_USERS → Environment variable                         │
│                                                                  │
│  5. START CONTAINER                                              │
│     ├─ Run CMD from Dockerfile                                  │
│     ├─ Streamlit starts on port 7860                            │
│     └─ Health check confirms running                            │
│                                                                  │
│  6. ROUTE TRAFFIC                                                │
│     └─ https://username-spacename.hf.space → Container:7860     │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### 4.2 Build Timeline

| Step | Duration | Notes |
|------|----------|-------|
| Clone repo | ~30s | Including LFS files |
| Pull base image | ~30s | Cached after first build |
| apt-get install | ~1 min | System dependencies |
| pip install | ~4 min | Python packages + PyTorch |
| Copy files | ~30s | Application code |
| Start container | ~30s | Including model download |
| **Total** | **~7 min** | First build |

**Subsequent builds**: ~3-4 minutes (Docker layer caching)

### 4.3 Monitoring the Build

1. Go to your Space: `https://huggingface.co/spaces/YOUR_USERNAME/YOUR_SPACE`
2. Click the **"Logs"** tab
3. Watch for:
   - `Building Docker image...`
   - `Installing requirements...`
   - `Starting container...`
   - `Application startup complete`

---

## Phase 5: Runtime Behavior

### 5.1 Application Startup Sequence

```python
# 1. Streamlit initializes
st.set_page_config(...)

# 2. Load environment variables
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")  # From HF Secrets
ALLOWED_USERNAMES = os.getenv("ALLOWED_USERNAMES")  # From HF Secrets

# 3. Initialize components (cached)
@st.cache_resource
def get_retriever():
    return SeerahRetriever()  # Loads ChromaDB + embedding model

# 4. Check authentication
if not require_auth(auth_manager):
    render_auth_page()  # Show login/register

# 5. Render chat interface
render_chat_interface()
```

### 5.2 First Request Flow

```
User Request                    Server Response
─────────────                   ───────────────

GET /                           
    │
    ▼
┌─────────────────┐
│ Load embedding  │  (~10 sec on first request)
│ model (80MB)    │  Downloads from HuggingFace Hub
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Initialize      │  (~1 sec)
│ ChromaDB        │  Loads from /app/data/chroma_db/
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Render login    │  (~100ms)
│ page            │
└────────┬────────┘
         │
         ▼
    HTML Response
```

### 5.3 Query Processing Flow

```
User asks: "Who was Khadijah?"
         │
         ▼
┌─────────────────────────────────────────────────────────┐
│ 1. GUARDRAILS CHECK                                      │
│    └─ Is query appropriate? → Yes, continue             │
└────────────────────────────────────────────────────────┬┘
                                                         │
┌────────────────────────────────────────────────────────▼┐
│ 2. EMBED QUERY                                          │
│    └─ sentence-transformers → [0.12, -0.34, ...] 384d  │
└────────────────────────────────────────────────────────┬┘
                                                         │
┌────────────────────────────────────────────────────────▼┐
│ 3. VECTOR SEARCH                                        │
│    └─ ChromaDB.query(embedding, top_k=5)               │
│    └─ Returns 5 most relevant transcript chunks        │
└────────────────────────────────────────────────────────┬┘
                                                         │
┌────────────────────────────────────────────────────────▼┐
│ 4. BUILD CONTEXT                                        │
│    └─ Format chunks with source citations              │
│    └─ Add conversation history                         │
└────────────────────────────────────────────────────────┬┘
                                                         │
┌────────────────────────────────────────────────────────▼┐
│ 5. GENERATE RESPONSE                                    │
│    └─ Gemini API call with system prompt + context     │
│    └─ Stream response to user                          │
└────────────────────────────────────────────────────────┬┘
                                                         │
┌────────────────────────────────────────────────────────▼┐
│ 6. SAVE TO MEMORY                                       │
│    └─ Store Q&A in SQLite (persistent /data/)          │
└─────────────────────────────────────────────────────────┘
```

---

## Phase 6: Updates and Maintenance

### 6.1 Updating the App

```bash
# Make changes locally
vim config/settings.py

# Test locally
streamlit run app.py

# Push to HF
cd /path/to/hf-space-clone
cp -r /path/to/seerah_rag/* .
git add -A
git commit -m "Update system prompt"
git push
```

HF Spaces automatically rebuilds on push.

### 6.2 Checking Logs

```
Space Page → Logs tab

Look for:
✓ "Application startup complete"
✗ "Error: ..." (any errors)
✗ "ModuleNotFoundError" (missing dependency)
```

### 6.3 Restarting the Space

If the app is stuck:
1. Go to Space Settings
2. Click "Restart" or "Factory reboot"

---

## Troubleshooting

### Build Fails

| Error | Cause | Fix |
|-------|-------|-----|
| `Config error` | Missing YAML frontmatter | Add `---` block to README.md |
| `LFS error` | Large files not tracked | Run `git lfs track` |
| `pip install fails` | Incompatible packages | Check requirements.txt versions |

### Runtime Fails

| Error | Cause | Fix |
|-------|-------|-----|
| `GEMINI_API_KEY not set` | Secret not configured | Add in Space Settings |
| `Knowledge base not ready` | ChromaDB missing | Ensure data/chroma_db/ is pushed |
| `Permission denied` | File permissions | Check Dockerfile chmod commands |

### User Access Issues

| Issue | Cause | Fix |
|-------|-------|-----|
| 404 error | Space private or not built | Check visibility settings |
| Registration fails | Username not whitelisted | Check ALLOWED_USERNAMES secret |
| Login fails | Wrong password | User must re-register if DB reset |

---

## Architecture Summary

```
┌─────────────────────────────────────────────────────────────────┐
│                    DEPLOYED ARCHITECTURE                         │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │                    HF SPACES CONTAINER                    │   │
│  │                                                           │   │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────────┐  │   │
│  │  │  Streamlit  │  │   Gemini    │  │  Sentence       │  │   │
│  │  │  (UI)       │  │   API       │  │  Transformers   │  │   │
│  │  │  Port 7860  │  │  (Cloud)    │  │  (Local)        │  │   │
│  │  └──────┬──────┘  └──────┬──────┘  └────────┬────────┘  │   │
│  │         │                │                   │           │   │
│  │         └────────────────┼───────────────────┘           │   │
│  │                          │                               │   │
│  │  ┌───────────────────────▼───────────────────────────┐  │   │
│  │  │              RAG Pipeline (retriever.py)           │  │   │
│  │  └───────────────────────┬───────────────────────────┘  │   │
│  │                          │                               │   │
│  │         ┌────────────────┼────────────────┐             │   │
│  │         ▼                ▼                ▼             │   │
│  │  ┌────────────┐  ┌────────────┐  ┌─────────────────┐   │   │
│  │  │ ChromaDB   │  │ SQLite     │  │ HF Persistent   │   │   │
│  │  │ /app/data/ │  │ /data/     │  │ Storage /data/  │   │   │
│  │  │ (read-only)│  │ (users,    │  │ (survives       │   │   │
│  │  │            │  │  chats)    │  │  restarts)      │   │   │
│  │  └────────────┘  └────────────┘  └─────────────────┘   │   │
│  │                                                           │   │
│  └──────────────────────────────────────────────────────────┘   │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```
