---
title: Seerah Q&A
emoji: 🕌
colorFrom: green
colorTo: blue
sdk: docker
app_port: 7860
pinned: false
---

# 🕌 Seerah Q&A

A RAG-powered Q&A application for learning about the Seerah (biography) of Prophet Muhammad ﷺ, using Yasir Qadhi's comprehensive 104-video lecture series as its knowledge base.

## Features

- **Intelligent Q&A**: Ask questions about the life of the Prophet and get accurate, contextual answers
- **Source Citations**: Every answer includes references to specific lecture videos with timestamps
- **Conversation Memory**: The system remembers your previous questions for natural follow-up discussions
- **User Accounts**: Personal chat history with multiple conversation sessions
- **Modern UI**: Clean, responsive Streamlit interface

## Quick Start

### Prerequisites

- Python 3.10+
- Gemini API key ([Get one here](https://makersuite.google.com/app/apikey))

### Installation

```bash
# Clone the repository
git clone https://github.com/yourusername/seerah_rag.git
cd seerah_rag

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### Configuration

Create a `.env` file in the project root:

```env
# Required
GEMINI_API_KEY=your_gemini_api_key_here

# Access Control (for family-only access)
ALLOWED_USERNAMES=dad,mom,brother,sister  # Only these users can register
MAX_USERS=10  # Maximum users allowed
```

### Building the Knowledge Base

This is a one-time setup to download transcripts and create embeddings:

```bash
# Step 1: Download all transcripts from YouTube (takes ~30 minutes)
python -m data_pipeline.transcript_fetcher

# Step 2: Build the vector database (takes ~1-2 hours depending on API limits)
python -m data_pipeline.knowledge_base
```

### Running the App

```bash
streamlit run app.py
```

Open http://localhost:8501 in your browser.

## Project Structure

```
seerah_rag/
├── app.py                      # Main Streamlit application
├── requirements.txt            # Python dependencies
├── config/
│   └── settings.py             # Configuration constants
├── core/
│   ├── auth_manager.py         # User authentication
│   ├── chat_memory.py          # Conversation memory
│   └── retriever.py            # RAG pipeline
├── database/
│   ├── db_manager.py           # SQLite operations
│   └── models.py               # Data models
├── data_pipeline/
│   ├── transcript_fetcher.py   # YouTube transcript extraction
│   └── knowledge_base.py       # Embedding pipeline
├── docs/
│   ├── ARCHITECTURE.md         # System design
│   ├── MEMORY_MANAGEMENT.md    # How conversation memory works
│   ├── CHUNKING_STRATEGY.md    # How transcripts are processed
│   ├── AUTHENTICATION.md       # User auth system
│   └── DEPLOYMENT.md           # HuggingFace deployment guide
└── data/
    ├── transcripts/            # Downloaded transcripts
    ├── chroma_db/              # Vector database
    └── seerah.db               # User & chat database
```

## How It Works

### 1. Data Pipeline

The application processes Yasir Qadhi's Seerah lecture series:

1. **Transcript Fetching**: Downloads transcripts from all 104 YouTube videos
2. **Chunking**: Splits transcripts into ~500-token chunks with overlap
3. **Embedding**: Generates vector embeddings using Gemini's embedding model
4. **Storage**: Stores embeddings in ChromaDB for fast retrieval

### 2. Query Processing

When you ask a question:

1. **Embedding**: Your query is converted to a vector embedding
2. **Retrieval**: ChromaDB finds the most relevant transcript chunks
3. **Memory**: Recent conversation history is loaded for context
4. **Generation**: Gemini generates an answer using the retrieved context
5. **Citation**: Sources are displayed with video links and timestamps

### 3. Memory System

The app uses a hybrid memory approach:

- **Buffer Memory**: Last 5 message pairs kept in full detail
- **Summary Memory**: Older messages condensed into a summary

This allows natural follow-up questions while managing token limits.

## Documentation

Detailed documentation is available in the `docs/` folder:

| Document | Description |
|----------|-------------|
| [ARCHITECTURE.md](docs/ARCHITECTURE.md) | System design and component overview |
| [MEMORY_MANAGEMENT.md](docs/MEMORY_MANAGEMENT.md) | How conversation memory works |
| [CHUNKING_STRATEGY.md](docs/CHUNKING_STRATEGY.md) | Transcript processing approach |
| [AUTHENTICATION.md](docs/AUTHENTICATION.md) | User authentication system |
| [DEPLOYMENT.md](docs/DEPLOYMENT.md) | HuggingFace Spaces deployment |

## Deployment

### Hugging Face Spaces (Recommended - Free Tier)

The app is designed for easy deployment on Hugging Face Spaces free tier using Docker:

#### Step 1: Prepare Your Repository

```bash
# Make sure your knowledge base is built
python -m data_pipeline.transcript_fetcher
python -m data_pipeline.knowledge_base

# The data/ folder should contain:
# - chroma_db/ (vector database)
# - seerah.db (user database - optional, will be created)
```

#### Step 2: Create Hugging Face Space

1. Go to [huggingface.co/spaces](https://huggingface.co/spaces)
2. Click "Create new Space"
3. Choose:
   - **Space name**: `seerah-qa` (or your preference)
   - **License**: Select appropriate license
   - **SDK**: Select **Docker**
   - **Hardware**: CPU basic (free)
4. Click "Create Space"

#### Step 3: Configure Secrets

In your Space settings, add these secrets:

| Secret | Value | Required |
|--------|-------|----------|
| `GEMINI_API_KEY` | Your Google Gemini API key | Yes |
| `ALLOWED_USERNAMES` | `dad,mom,brother,sister` (comma-separated) | Yes |
| `MAX_USERS` | `10` | Optional |

#### Step 4: Push Your Code

```bash
# Clone your HF Space repository
git clone https://huggingface.co/spaces/YOUR_USERNAME/seerah-qa
cd seerah-qa

# Copy your project files
cp -r /path/to/seerah_rag/* .

# Important: Include the data folder with ChromaDB
# (Make sure .gitignore doesn't exclude data/chroma_db for deployment)

# Push to Hugging Face
git add .
git commit -m "Initial deployment"
git push
```

#### Step 5: Access Your App

Your app will be available at:
`https://YOUR_USERNAME-seerah-qa.hf.space`

#### Troubleshooting

- **App won't start**: Check the Logs tab in your Space
- **"Knowledge base not ready"**: Ensure `data/chroma_db/` was pushed
- **Registration fails**: Verify `ALLOWED_USERNAMES` secret is set correctly

### Local Docker Testing

```bash
# Build the Docker image
docker build -t seerah-qa .

# Run with environment variables
docker run -p 7860:7860 \
  -e GEMINI_API_KEY=your_key \
  -e ALLOWED_USERNAMES=dad,mom,brother \
  seerah-qa

# Access at http://localhost:7860
```

See [DEPLOYMENT.md](docs/DEPLOYMENT.md) for more detailed instructions.

## Configuration

Key settings in `config/settings.py`:

| Setting | Default | Description |
|---------|---------|-------------|
| `CHUNK_SIZE` | 500 | Tokens per chunk |
| `CHUNK_OVERLAP` | 50 | Overlap between chunks |
| `RETRIEVAL_TOP_K` | 5 | Chunks to retrieve per query |
| `BUFFER_SIZE` | 5 | Message pairs in memory buffer |
| `LLM_MODEL` | gemini-2.0-flash | Gemini model for generation |
| `ALLOWED_USERNAMES` | [] | Whitelist of usernames that can register |
| `MAX_USERS` | 10 | Maximum registered users allowed |

## Tech Stack

- **Frontend**: Streamlit
- **LLM**: Google Gemini (gemini-2.0-flash)
- **Embeddings**: HuggingFace sentence-transformers (all-MiniLM-L6-v2) - runs locally, free!
- **Vector Store**: ChromaDB
- **Database**: SQLite
- **Authentication**: bcrypt
- **Deployment**: Docker / Hugging Face Spaces

## API Costs

The app uses Gemini API which has a generous free tier:

- **Free tier**: 15 requests/minute, 1 million tokens/month
- **Embedding**: ~$0.00 per 1M tokens (free tier)
- **Generation**: ~$0.00 per 1M tokens (free tier)

For most personal/educational use, you'll stay within free limits.

## Contributing

Contributions are welcome! Please:

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Submit a pull request

## License

MIT License - See LICENSE file for details.

## Acknowledgments

- **Yasir Qadhi** for the incredible Seerah lecture series
- **Google** for Gemini API
- **Streamlit** for the amazing framework
- **ChromaDB** for the vector database

## Disclaimer

This application is an educational tool. The AI-generated responses are based on the lecture transcripts and may not always be perfectly accurate. For authoritative Islamic knowledge, please consult qualified scholars.

---

*Built with ❤️ for the Muslim community*
