# Dockerfile Explained

This document explains every line of the Dockerfile used to deploy the Seerah Q&A application on Hugging Face Spaces.

## The Complete Dockerfile

```dockerfile
# Dockerfile for Hugging Face Spaces deployment
# Seerah Q&A - RAG-powered Islamic knowledge application

FROM python:3.11-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV HF_HOME=/app/.cache/huggingface
ENV TRANSFORMERS_CACHE=/app/.cache/huggingface
ENV SENTENCE_TRANSFORMERS_HOME=/app/.cache/sentence_transformers

RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
    git \
    && rm -rf /var/lib/apt/lists/*

RUN mkdir -p /app/.cache/huggingface /app/.cache/sentence_transformers \
    && chmod -R 777 /app/.cache

COPY requirements.txt .

RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

COPY . .

RUN mkdir -p data/transcripts data/chroma_db

RUN chmod -R 777 /app/data

EXPOSE 7860

HEALTHCHECK CMD curl --fail http://localhost:7860/_stcore/health || exit 1

CMD ["streamlit", "run", "app.py", \
     "--server.port=7860", \
     "--server.address=0.0.0.0", \
     "--server.enableCORS=false", \
     "--server.enableXsrfProtection=false", \
     "--browser.gatherUsageStats=false"]
```

---

## Line-by-Line Explanation

### Base Image

```dockerfile
FROM python:3.11-slim
```

**What it does**: Uses Python 3.11 on a minimal Debian-based image.

**Why this choice**:
- `python:3.11` - Matches our local development Python version
- `slim` variant - Smaller image size (~150MB vs ~900MB for full image)
- Official Python image - Well-maintained, secure, optimized

**Alternatives considered**:
- `python:3.11-alpine` - Even smaller but has compatibility issues with some packages (numpy, torch)
- `python:3.11` (full) - Unnecessary bloat for our use case

---

### Working Directory

```dockerfile
WORKDIR /app
```

**What it does**: Sets `/app` as the working directory for all subsequent commands.

**Why**: 
- Clean separation from system files
- All `COPY`, `RUN`, and `CMD` commands execute from this directory
- Standard convention for application code

---

### Environment Variables

```dockerfile
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV HF_HOME=/app/.cache/huggingface
ENV TRANSFORMERS_CACHE=/app/.cache/huggingface
ENV SENTENCE_TRANSFORMERS_HOME=/app/.cache/sentence_transformers
```

| Variable | Purpose |
|----------|---------|
| `PYTHONDONTWRITEBYTECODE=1` | Prevents Python from creating `.pyc` files (saves space) |
| `PYTHONUNBUFFERED=1` | Outputs Python logs immediately (important for debugging) |
| `HF_HOME` | Where Hugging Face caches downloaded models |
| `TRANSFORMERS_CACHE` | Transformers library cache location |
| `SENTENCE_TRANSFORMERS_HOME` | Where sentence-transformers stores the embedding model |

**Why set cache paths explicitly**:
- HF Spaces runs as user `1000` (not root)
- Default cache locations may not be writable
- Explicit paths ensure the embedding model downloads successfully

---

### System Dependencies

```dockerfile
RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
    git \
    && rm -rf /var/lib/apt/lists/*
```

| Package | Why Needed |
|---------|------------|
| `build-essential` | Compiles C extensions for numpy, scipy, etc. |
| `curl` | Health check command uses curl |
| `git` | Some Python packages need git for installation |

**The cleanup** (`rm -rf /var/lib/apt/lists/*`):
- Removes apt cache after installation
- Reduces final image size by ~100MB

---

### Cache Directory Setup

```dockerfile
RUN mkdir -p /app/.cache/huggingface /app/.cache/sentence_transformers \
    && chmod -R 777 /app/.cache
```

**What it does**: Creates cache directories with full permissions.

**Why `777` permissions**:
- HF Spaces runs containers as non-root user (UID 1000)
- The embedding model (~80MB) downloads on first run
- Without proper permissions, the download fails with "Permission denied"

---

### Python Dependencies

```dockerfile
COPY requirements.txt .

RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt
```

**Why copy requirements.txt first**:
- Docker layer caching optimization
- If only code changes (not dependencies), Docker reuses the cached pip install layer
- Saves 5-10 minutes on rebuilds

**`--no-cache-dir` flag**:
- Prevents pip from caching downloaded packages
- Reduces image size by ~200MB

---

### Application Code

```dockerfile
COPY . .
```

**What it does**: Copies entire project into the container.

**What gets copied**:
- `app.py` - Main Streamlit application
- `config/` - Settings and prompts
- `core/` - RAG logic, auth, memory
- `database/` - SQLite management
- `data/chroma_db/` - Pre-built knowledge base (via Git LFS)
- `docs/` - Documentation

**What doesn't get copied** (via .dockerignore if present):
- `venv/` - Local virtual environment
- `.env` - Secrets (loaded from HF Spaces secrets instead)
- `__pycache__/` - Compiled Python files

---

### Data Directories

```dockerfile
RUN mkdir -p data/transcripts data/chroma_db
RUN chmod -R 777 /app/data
```

**Purpose**: Ensures data directories exist with proper permissions.

**Note**: The `data/chroma_db/` directory is already populated from the Git LFS files. This command ensures the structure exists even if empty.

---

### Port Configuration

```dockerfile
EXPOSE 7860
```

**Why port 7860**:
- Hugging Face Spaces standard port for Docker SDK
- Must match `app_port: 7860` in README.md frontmatter
- Streamlit default is 8501, but we override it

---

### Health Check

```dockerfile
HEALTHCHECK CMD curl --fail http://localhost:7860/_stcore/health || exit 1
```

**What it does**: Docker periodically checks if the app is responding.

**The endpoint** (`/_stcore/health`):
- Built-in Streamlit health endpoint
- Returns 200 if Streamlit is running
- Returns error if crashed

**Why it matters**:
- HF Spaces uses this to detect crashed containers
- Enables automatic restart on failure
- Shows "Running" vs "Error" status in UI

---

### Startup Command

```dockerfile
CMD ["streamlit", "run", "app.py", \
     "--server.port=7860", \
     "--server.address=0.0.0.0", \
     "--server.enableCORS=false", \
     "--server.enableXsrfProtection=false", \
     "--browser.gatherUsageStats=false"]
```

| Flag | Purpose |
|------|---------|
| `--server.port=7860` | Match HF Spaces expected port |
| `--server.address=0.0.0.0` | Listen on all interfaces (required for Docker) |
| `--server.enableCORS=false` | Disable CORS (HF Spaces handles this) |
| `--server.enableXsrfProtection=false` | Disable XSRF (can cause issues in iframe) |
| `--browser.gatherUsageStats=false` | Disable telemetry |

**Why `CMD` not `ENTRYPOINT`**:
- `CMD` can be overridden for debugging
- `ENTRYPOINT` + `CMD` combo is overkill for single-command apps

---

## Build Process Timeline

When HF Spaces builds your Docker image:

```
1. Pull base image (python:3.11-slim)     ~30 seconds
2. Install system packages                 ~1 minute
3. Create cache directories                ~1 second
4. Copy requirements.txt                   ~1 second
5. Install Python packages                 ~3-5 minutes
6. Copy application code + ChromaDB        ~1-2 minutes (LFS files)
7. Set permissions                         ~1 second
8. Start Streamlit                         ~10 seconds
                                           ─────────────
                                    Total: ~5-8 minutes (first build)
```

**Subsequent builds** (if only code changed): ~2-3 minutes (reuses pip cache layer)

---

## Common Build Errors

### 1. "Permission denied" for model download

**Symptom**: App crashes when loading embedding model

**Fix**: Ensure cache directories have `777` permissions

### 2. "Port already in use"

**Symptom**: Container won't start

**Fix**: Ensure only port 7860 is used, not 8501

### 3. "Module not found"

**Symptom**: Import errors on startup

**Fix**: Check requirements.txt includes all dependencies

---

## Testing Locally

```bash
# Build the image
docker build -t seerah-qa .

# Run with environment variables
docker run -p 7860:7860 \
  -e GEMINI_API_KEY=your_key \
  -e ALLOWED_USERNAMES=dad,mom \
  seerah-qa

# Access at http://localhost:7860
```

---

## Image Size Optimization

Current optimizations save ~500MB:

| Optimization | Savings |
|--------------|---------|
| `slim` base image | ~750MB |
| `--no-cache-dir` for pip | ~200MB |
| `rm -rf /var/lib/apt/lists/*` | ~100MB |
| No `.pyc` files | ~50MB |

**Final image size**: ~2.5GB (mostly due to PyTorch/sentence-transformers)
