# Deployment Guide - Hugging Face Spaces

This guide walks you through deploying the Seerah Q&A application on Hugging Face Spaces (free tier) with family-only access control.

## Why Hugging Face Spaces?

- **Free tier**: 16GB storage, 2 vCPU, 16GB RAM
- **Docker support**: Full control over deployment environment
- **Persistent storage**: Data survives restarts
- **Secrets management**: Secure API key and access control
- **Easy deployment**: Git-based workflow

## Prerequisites

1. **Hugging Face account**: Create at [huggingface.co](https://huggingface.co)
2. **Gemini API key**: Get from [makersuite.google.com](https://makersuite.google.com/app/apikey)
3. **Git installed**: For pushing code
4. **Pre-built knowledge base**: Transcripts and embeddings ready

## Step 1: Create Hugging Face Space

1. Go to [huggingface.co/spaces](https://huggingface.co/spaces)
2. Click "Create new Space"
3. Configure:
   - **Space name**: `seerah-qa` (or your preferred name)
   - **License**: Choose appropriate license
   - **SDK**: Select **Docker** (important!)
   - **Hardware**: CPU basic (free)
   - **Visibility**: Private (recommended for family app)

## Step 2: Configure Secrets

1. Go to your Space's Settings
2. Find "Repository secrets" section
3. Add these secrets:

| Secret Name | Value | Purpose |
|-------------|-------|---------|
| `GEMINI_API_KEY` | Your Gemini API key | Required for AI responses |
| `ALLOWED_USERNAMES` | `dad,mom,brother,sister` | Comma-separated whitelist |
| `MAX_USERS` | `10` | Maximum registrations allowed |

**Important**: The `ALLOWED_USERNAMES` restricts who can register. Only usernames in this list will be able to create accounts.

The app will read these automatically via environment variables.

## Step 3: Prepare Files for Deployment

### Required Files

```
seerah_rag/
├── app.py                    # Main Streamlit app
├── Dockerfile                # Docker configuration for HF Spaces
├── requirements.txt          # Dependencies
├── .huggingface/
│   └── spaces.yaml           # HF Spaces configuration
├── config/
│   └── settings.py
├── core/
│   ├── auth_manager.py
│   ├── chat_memory.py
│   ├── guardrails.py
│   └── retriever.py
├── database/
│   ├── db_manager.py
│   └── models.py
├── data_pipeline/
│   ├── transcript_fetcher.py
│   └── knowledge_base.py
└── data/
    ├── chroma_db/            # Pre-built vector database (REQUIRED)
    └── transcripts/          # Downloaded transcripts (optional)
```

### Dockerfile (Already Included)

The project includes a `Dockerfile` optimized for Hugging Face Spaces:

```dockerfile
FROM python:3.11-slim
WORKDIR /app
# ... installs dependencies and runs Streamlit on port 7860
```

### Handling Large Files

The ChromaDB database might be large. Options:

**Option A: Include in repo (if < 10GB)**
```bash
# Just commit the data directory
git add data/chroma_db/
git commit -m "Add pre-built knowledge base"
```

**Option B: Use Git LFS for large files**
```bash
# Install Git LFS
git lfs install

# Track large files
git lfs track "data/chroma_db/**"
git add .gitattributes
git commit -m "Configure Git LFS"
```

**Option C: Build on first run**
Modify `app.py` to check and build if missing:

```python
@st.cache_resource
def ensure_knowledge_base():
    retriever = SeerahRetriever()
    if not retriever.is_ready():
        st.warning("Building knowledge base... This may take a while.")
        # Trigger build
        from data_pipeline.knowledge_base import build_knowledge_base
        build_knowledge_base()
    return retriever
```

## Step 4: Update Settings for HuggingFace

Modify `config/settings.py` for HuggingFace environment:

```python
import os
from pathlib import Path

# Detect HuggingFace environment
IS_HUGGINGFACE = os.getenv("SPACE_ID") is not None

if IS_HUGGINGFACE:
    # Use persistent storage on HuggingFace
    BASE_DIR = Path("/data")  # HF persistent storage
else:
    BASE_DIR = Path(__file__).resolve().parent.parent

# Paths
DATA_DIR = BASE_DIR / "app_data"
TRANSCRIPTS_DIR = DATA_DIR / "transcripts"
CHROMA_DB_DIR = DATA_DIR / "chroma_db"
DATABASE_PATH = DATA_DIR / "seerah.db"

# Create directories
DATA_DIR.mkdir(exist_ok=True, parents=True)
TRANSCRIPTS_DIR.mkdir(exist_ok=True, parents=True)
CHROMA_DB_DIR.mkdir(exist_ok=True, parents=True)
```

## Step 5: Clone and Push

```bash
# Clone your HuggingFace Space
git clone https://huggingface.co/spaces/YOUR_USERNAME/seerah-qa
cd seerah-qa

# Copy your project files
cp -r /path/to/seerah_rag/* .

# Add all files
git add .
git commit -m "Initial deployment"

# Push to HuggingFace
git push
```

## Step 6: Monitor Deployment

1. Go to your Space page
2. Watch the "Logs" tab for build progress
3. Common issues:
   - **Import errors**: Missing dependencies in requirements.txt
   - **Memory errors**: Reduce batch sizes or chunk counts
   - **Timeout**: Build takes too long, consider pre-building

## Persistent Storage on HuggingFace

HuggingFace Spaces provides persistent storage at `/data`:

```python
# Files saved here persist across restarts
PERSISTENT_DIR = Path("/data")

# Example: Save SQLite database
DATABASE_PATH = PERSISTENT_DIR / "seerah.db"

# Example: Save ChromaDB
CHROMA_PATH = PERSISTENT_DIR / "chroma_db"
```

**Important**: The main repo storage is NOT persistent. Only `/data` survives restarts.

## Environment Variables

Access secrets in your app:

```python
import os

# HuggingFace automatically loads secrets as env vars
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# Check if running on HuggingFace
IS_HUGGINGFACE = os.getenv("SPACE_ID") is not None
```

## Space Configuration

The project includes `.huggingface/spaces.yaml` with Docker configuration:

```yaml
title: Seerah Q&A
emoji: 🕌
colorFrom: green
colorTo: blue
sdk: docker
app_port: 7860
pinned: false
hardware: cpu-basic
```

This file tells Hugging Face to use Docker SDK and expose port 7860.

## Troubleshooting

### App Won't Start

**Check logs for errors:**
- Go to Space → Logs tab
- Look for import errors or missing dependencies

**Common fixes:**
```bash
# Missing dependency
# Add to requirements.txt and push

# Path issues
# Use absolute paths or os.path.join
```

### Out of Memory

**Reduce memory usage:**
```python
# Smaller embedding batches
EMBEDDING_BATCH_SIZE = 50  # Instead of 100

# Fewer retrieved chunks
RETRIEVAL_TOP_K = 3  # Instead of 5
```

### Database Locked

**SQLite concurrency issue:**
```python
# Use connection timeout
conn = sqlite3.connect(db_path, timeout=30)

# Or use WAL mode
conn.execute("PRAGMA journal_mode=WAL")
```

### Slow Cold Start

HuggingFace free tier sleeps after inactivity. First request triggers cold start.

**Mitigations:**
- Accept cold start delay (30-60 seconds)
- Upgrade to paid tier for always-on
- Use `@st.cache_resource` for heavy loads

## Free Tier Limits

| Resource | Limit |
|----------|-------|
| Storage | 16GB |
| RAM | 16GB |
| vCPU | 2 |
| Sleep after | 48h inactivity |
| Cold start | ~30-60 seconds |

## Security Considerations

1. **Private Space**: Set visibility to "Private" for family-only access
2. **API Keys**: Always use Secrets, never commit keys
3. **Username Whitelist**: Set `ALLOWED_USERNAMES` to restrict registration
4. **User Data**: Stored in SQLite, consider encryption for sensitive data
5. **HTTPS**: Automatically provided by Hugging Face

### Access Control

The app enforces family-only access through:

1. **Username Whitelist**: Only usernames in `ALLOWED_USERNAMES` can register
2. **Max Users Limit**: `MAX_USERS` caps total registrations
3. **Private Space**: Only people with the link can access

Example whitelist setup:
```
ALLOWED_USERNAMES=dad,mom,ahmed,fatima,omar
```

Users must register with their exact whitelisted username (case-insensitive).

## Updating the App

```bash
# Make changes locally
git add .
git commit -m "Update feature X"
git push

# HuggingFace automatically rebuilds
```

## Custom Domain (Optional)

For professional deployment:
1. Upgrade to paid HuggingFace plan
2. Go to Space Settings
3. Configure custom domain
4. Update DNS records

## Monitoring

**View usage:**
- Space page shows visitor count
- Logs show request patterns

**Error tracking:**
- Check Logs tab for errors
- Add custom logging in app:

```python
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def process_query(query):
    logger.info(f"Processing query: {query[:50]}...")
    try:
        response = retriever.query(query)
        logger.info("Query successful")
        return response
    except Exception as e:
        logger.error(f"Query failed: {e}")
        raise
```

## Next Steps

After successful deployment:

1. **Test thoroughly**: Try various queries
2. **Share with users**: Send Space URL to authenticated users
3. **Monitor usage**: Check logs for issues
4. **Iterate**: Improve based on feedback
