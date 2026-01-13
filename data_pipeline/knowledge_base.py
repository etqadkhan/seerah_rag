"""
Knowledge Base Builder Module

This module handles creating the vector database from transcripts.
It includes:
- Loading transcripts from HuggingFace (cleaned data) or local JSON files
- Semantic chunking with overlap (simplified - no timestamp concerns)
- Generating embeddings using HuggingFace sentence-transformers (free!)
- Storing in ChromaDB for efficient retrieval

Usage:
    # Build from HuggingFace (recommended - cleaner data):
    python -m data_pipeline.knowledge_base --source huggingface --recreate
    
    # Build from local JSON files (legacy):
    python -m data_pipeline.knowledge_base --source local --recreate

See docs/CHUNKING_STRATEGY.md for detailed chunking approach.
"""

import json
import sys
import re
from pathlib import Path
from typing import Generator

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from sentence_transformers import SentenceTransformer
import chromadb
from chromadb.config import Settings

from config.settings import (
    TRANSCRIPTS_DIR,
    CHROMA_DB_DIR,
    COLLECTION_NAME,
    CHUNK_SIZE,
    CHUNK_OVERLAP,
    MIN_CHUNK_SIZE,
    EMBEDDING_MODEL,
    EMBEDDING_BATCH_SIZE,
)


# Initialize the embedding model (loaded once, reused)
print(f"Loading embedding model: {EMBEDDING_MODEL}")
_embedding_model = None


def get_embedding_model() -> SentenceTransformer:
    """Get or initialize the sentence transformer model (singleton pattern)."""
    global _embedding_model
    if _embedding_model is None:
        _embedding_model = SentenceTransformer(EMBEDDING_MODEL)
    return _embedding_model


# ============================================================================
# Transcript Loading - Multiple Sources
# ============================================================================

def load_from_huggingface() -> list[dict]:
    """
    Load transcripts from HuggingFace dataset.
    This is the recommended source - cleaner, better quality transcripts.
    
    Returns:
        List of transcript dictionaries with 'title', 'lecture_number', 'text'
    """
    from data_pipeline.hf_data_loader import process_dataset_for_embedding
    
    print("Loading from HuggingFace dataset...")
    return process_dataset_for_embedding()


def load_from_local(transcripts_dir: Path = TRANSCRIPTS_DIR) -> list[dict]:
    """
    Load all transcript JSON files from the local transcripts directory.
    This is the legacy source from YouTube auto-captions.
    
    Args:
        transcripts_dir: Directory containing transcript JSON files
        
    Returns:
        List of transcript dictionaries sorted by playlist index
    """
    transcripts = []
    transcripts_dir = Path(transcripts_dir)
    
    for filepath in sorted(transcripts_dir.glob("*.json")):
        # Skip summary files
        if filepath.name.startswith("_"):
            continue
            
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)
            
            # Extract full text from segments or use full_text field
            transcript_data = data.get('transcript', {})
            if 'full_text' in transcript_data:
                text = transcript_data['full_text']
            elif 'segments' in transcript_data:
                text = ' '.join(seg.get('text', '') for seg in transcript_data['segments'])
            else:
                continue
            
            transcripts.append({
                'title': data.get('title', f"Lecture {len(transcripts) + 1}"),
                'lecture_number': data.get('playlist_index', len(transcripts) + 1),
                'video_id': data.get('video_id', ''),
                'text': text,
            })
    
    print(f"Loaded {len(transcripts)} transcripts from local files")
    return transcripts


# ============================================================================
# Text Processing Utilities
# ============================================================================

def estimate_tokens(text: str) -> int:
    """
    Estimate token count for text.
    Uses a simple approximation: ~4 characters per token.
    
    Args:
        text: Input text
        
    Returns:
        Estimated token count
    """
    return len(text) // 4


def split_into_sentences(text: str) -> list[str]:
    """
    Split text into sentences using regex patterns.
    
    Args:
        text: Input text
        
    Returns:
        List of sentences
    """
    # Pattern for sentence boundaries
    # Handles: periods, question marks, exclamation marks
    # Avoids splitting on: Mr., Mrs., Dr., etc.
    pattern = r'(?<=[.!?])\s+(?=[A-Z])|(?<=[.!?])(?=\s*$)'
    
    sentences = re.split(pattern, text)
    return [s.strip() for s in sentences if s.strip()]


def clean_text(text: str) -> str:
    """
    Clean and normalize text for better embedding.
    
    Args:
        text: Raw text
        
    Returns:
        Cleaned text
    """
    # Remove excessive whitespace
    text = re.sub(r'\s+', ' ', text)
    # Remove any control characters
    text = re.sub(r'[\x00-\x1f\x7f-\x9f]', '', text)
    return text.strip()


# ============================================================================
# Simplified Chunking (No Timestamps)
# ============================================================================

def chunk_text(
    text: str,
    target_tokens: int = CHUNK_SIZE,
    overlap_tokens: int = CHUNK_OVERLAP
) -> list[str]:
    """
    Chunk text into smaller pieces with overlap.
    Uses sentence boundaries for cleaner chunks.
    
    This simplified approach focuses purely on content quality,
    without worrying about timestamps or video positions.
    
    Args:
        text: Full transcript text
        target_tokens: Target tokens per chunk
        overlap_tokens: Overlap tokens between chunks
        
    Returns:
        List of text chunks
    """
    # Clean the text first
    text = clean_text(text)
    
    # Split into sentences
    sentences = split_into_sentences(text)
    
    if not sentences:
        # If no clear sentences, fall back to simple splitting
        return simple_chunk_text(text, target_tokens, overlap_tokens)
    
    chunks = []
    current_sentences = []
    current_tokens = 0
    
    for sentence in sentences:
        sentence_tokens = estimate_tokens(sentence)
        
        # If this sentence alone is too big, split it
        if sentence_tokens > target_tokens:
            # Flush current chunk first
            if current_sentences:
                chunks.append(' '.join(current_sentences))
                current_sentences = []
                current_tokens = 0
            
            # Split the long sentence
            sub_chunks = simple_chunk_text(sentence, target_tokens, overlap_tokens)
            chunks.extend(sub_chunks)
            continue
        
        # If adding this sentence exceeds target, create chunk
        if current_tokens + sentence_tokens > target_tokens and current_sentences:
            # Create chunk
            chunks.append(' '.join(current_sentences))
            
            # Calculate overlap - keep last few sentences
            overlap_sentences = []
            overlap_count = 0
            for s in reversed(current_sentences):
                s_tokens = estimate_tokens(s)
                if overlap_count + s_tokens <= overlap_tokens:
                    overlap_sentences.insert(0, s)
                    overlap_count += s_tokens
                else:
                    break
            
            current_sentences = overlap_sentences
            current_tokens = overlap_count
        
        current_sentences.append(sentence)
        current_tokens += sentence_tokens
    
    # Don't forget the last chunk
    if current_sentences:
        chunks.append(' '.join(current_sentences))
    
    # Filter out chunks that are too small
    min_tokens = MIN_CHUNK_SIZE
    chunks = [c for c in chunks if estimate_tokens(c) >= min_tokens]
    
    return chunks


def simple_chunk_text(
    text: str,
    target_tokens: int = CHUNK_SIZE,
    overlap_tokens: int = CHUNK_OVERLAP
) -> list[str]:
    """
    Simple character-based chunking fallback.
    Used when sentence splitting doesn't work well.
    
    Args:
        text: Text to chunk
        target_tokens: Target tokens per chunk
        overlap_tokens: Overlap tokens between chunks
        
    Returns:
        List of text chunks
    """
    # Estimate characters per chunk (4 chars per token)
    target_chars = target_tokens * 4
    overlap_chars = overlap_tokens * 4
    
    chunks = []
    start = 0
    
    while start < len(text):
        end = start + target_chars
        
        # Try to break at a word boundary
        if end < len(text):
            # Look for last space before end
            space_idx = text.rfind(' ', start, end)
            if space_idx > start:
                end = space_idx
        
        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)
        
        # Move start, accounting for overlap
        start = end - overlap_chars
        if start < 0:
            start = end
    
    return chunks


def chunk_transcript(transcript: dict) -> list[dict]:
    """
    Chunk a single transcript into retrievable chunks.
    
    Simplified pipeline (no timestamps):
    1. Get clean text from transcript
    2. Chunk into semantic pieces with overlap
    3. Add metadata to each chunk
    
    Args:
        transcript: Transcript dictionary with 'title', 'lecture_number', 'text'
        
    Returns:
        List of chunk dictionaries with metadata
    """
    text = transcript.get('text', '')
    
    if not text or len(text) < MIN_CHUNK_SIZE * 4:
        return []
    
    # Chunk the text
    text_chunks = chunk_text(text)
    
    # Build chunk dictionaries with metadata
    chunks = []
    lecture_num = transcript.get('lecture_number', 0)
    title = transcript.get('title', f'Lecture {lecture_num}')
    video_id = transcript.get('video_id', '')
    
    for i, chunk_content in enumerate(text_chunks):
        chunk = {
            'id': f"lecture_{lecture_num:03d}_chunk_{i:04d}",
            'text': chunk_content,
            'title': title,
            'lecture_number': lecture_num,
            'video_id': video_id,
            'chunk_index': i,
        }
        chunks.append(chunk)
    
    return chunks


def chunk_all_transcripts(transcripts: list[dict]) -> list[dict]:
    """
    Chunk all transcripts into a flat list of chunks.
    
    Args:
        transcripts: List of transcript dictionaries
        
    Returns:
        Flat list of all chunks with metadata
    """
    all_chunks = []
    
    for transcript in transcripts:
        chunks = chunk_transcript(transcript)
        all_chunks.extend(chunks)
        title = transcript.get('title', 'Unknown')[:40]
        print(f"  Chunked '{title}...' into {len(chunks)} chunks")
    
    print(f"Total chunks created: {len(all_chunks)}")
    return all_chunks


# ============================================================================
# Embedding Generation (HuggingFace sentence-transformers - FREE!)
# ============================================================================

def create_embeddings_batch(texts: list[str]) -> list[list[float]]:
    """
    Generate embeddings for a batch of texts using sentence-transformers.
    
    This runs locally on CPU/GPU - completely FREE!
    
    Args:
        texts: List of text strings to embed
        
    Returns:
        List of embedding vectors
    """
    try:
        model = get_embedding_model()
        # encode() returns numpy arrays, convert to lists for ChromaDB
        embeddings = model.encode(texts, show_progress_bar=False)
        return embeddings.tolist()
    except Exception as e:
        print(f"Error generating embeddings: {e}")
        raise


def create_embeddings(
    chunks: list[dict],
    batch_size: int = EMBEDDING_BATCH_SIZE
) -> Generator[tuple[list[dict], list[list[float]]], None, None]:
    """
    Generate embeddings for chunks in batches.
    
    Uses HuggingFace sentence-transformers (runs locally, FREE!).
    
    Args:
        chunks: List of chunk dictionaries
        batch_size: Number of chunks to embed at once
        
    Yields:
        Tuples of (batch_chunks, embeddings)
    """
    total_batches = (len(chunks) + batch_size - 1) // batch_size
    
    # Pre-load model
    print(f"  Loading embedding model...")
    get_embedding_model()
    
    for i in range(0, len(chunks), batch_size):
        batch_chunks = chunks[i:i + batch_size]
        texts = [chunk['text'] for chunk in batch_chunks]
        
        batch_num = i // batch_size + 1
        print(f"  Embedding batch {batch_num}/{total_batches} ({len(texts)} chunks)...")
        
        embeddings = create_embeddings_batch(texts)
        
        # No rate limiting needed for local model!
        yield batch_chunks, embeddings


# ============================================================================
# Vector Store (ChromaDB)
# ============================================================================

def get_chroma_client(persist_dir: Path = CHROMA_DB_DIR) -> chromadb.PersistentClient:
    """
    Get or create a ChromaDB client with persistence.
    
    Args:
        persist_dir: Directory for ChromaDB persistence
        
    Returns:
        ChromaDB PersistentClient
    """
    persist_dir = Path(persist_dir)
    persist_dir.mkdir(parents=True, exist_ok=True)
    
    client = chromadb.PersistentClient(
        path=str(persist_dir),
        settings=Settings(anonymized_telemetry=False)
    )
    return client


def get_or_create_collection(
    client: chromadb.PersistentClient,
    collection_name: str = COLLECTION_NAME
) -> chromadb.Collection:
    """
    Get or create a ChromaDB collection.
    
    Args:
        client: ChromaDB client
        collection_name: Name of the collection
        
    Returns:
        ChromaDB Collection
    """
    collection = client.get_or_create_collection(
        name=collection_name,
        metadata={"description": "Seerah lecture transcripts knowledge base (HuggingFace cleaned data)"}
    )
    return collection


def build_vector_store(
    chunks: list[dict],
    persist_dir: Path = CHROMA_DB_DIR,
    collection_name: str = COLLECTION_NAME,
    recreate: bool = False
) -> chromadb.Collection:
    """
    Build the vector store from chunks.
    
    Args:
        chunks: List of chunk dictionaries with text and metadata
        persist_dir: Directory for ChromaDB persistence
        collection_name: Name of the collection
        recreate: If True, delete and recreate the collection
        
    Returns:
        ChromaDB Collection with embedded chunks
    """
    client = get_chroma_client(persist_dir)
    
    if recreate:
        try:
            client.delete_collection(collection_name)
            print(f"Deleted existing collection: {collection_name}")
        except Exception:
            pass
    
    collection = get_or_create_collection(client, collection_name)
    
    # Check if collection already has documents
    existing_count = collection.count()
    if existing_count > 0 and not recreate:
        print(f"Collection already has {existing_count} documents. Use --recreate to rebuild.")
        return collection
    
    print(f"Building vector store with {len(chunks)} chunks...")
    
    # Generate embeddings and add to collection in batches
    for batch_chunks, embeddings in create_embeddings(chunks):
        # Prepare data for ChromaDB
        ids = [chunk['id'] for chunk in batch_chunks]
        documents = [chunk['text'] for chunk in batch_chunks]
        metadatas = [
            {
                'title': chunk.get('title', ''),
                'lecture_number': chunk.get('lecture_number', 0),
                'video_id': chunk.get('video_id', ''),
                'chunk_index': chunk.get('chunk_index', 0),
            }
            for chunk in batch_chunks
        ]
        
        # Add to collection
        collection.add(
            ids=ids,
            embeddings=embeddings,
            documents=documents,
            metadatas=metadatas
        )
    
    print(f"Vector store built with {collection.count()} documents")
    return collection


# ============================================================================
# Main Build Pipeline
# ============================================================================

def build_knowledge_base(
    source: str = "huggingface",
    transcripts_dir: Path = TRANSCRIPTS_DIR,
    chroma_dir: Path = CHROMA_DB_DIR,
    recreate: bool = False
) -> dict:
    """
    Full pipeline to build the knowledge base.
    
    1. Load transcripts from source (HuggingFace or local)
    2. Chunk transcripts using semantic chunking
    3. Generate embeddings using sentence-transformers
    4. Store in ChromaDB
    
    Args:
        source: Data source - 'huggingface' (recommended) or 'local'
        transcripts_dir: Directory containing local transcript JSON files
        chroma_dir: Directory for ChromaDB persistence
        recreate: If True, rebuild the entire knowledge base
        
    Returns:
        Summary dictionary with statistics
    """
    print("=" * 60)
    print("Building Seerah Knowledge Base")
    print(f"Source: {source.upper()}")
    print("=" * 60)
    
    # Step 1: Load transcripts
    print("\n[1/3] Loading transcripts...")
    
    if source == "huggingface":
        transcripts = load_from_huggingface()
    else:
        transcripts = load_from_local(transcripts_dir)
    
    if not transcripts:
        print("No transcripts found!")
        return {'error': 'No transcripts found'}
    
    # Step 2: Chunk transcripts
    print("\n[2/3] Chunking transcripts...")
    chunks = chunk_all_transcripts(transcripts)
    
    # Step 3: Build vector store (includes embedding)
    print("\n[3/3] Building vector store (this may take a while)...")
    collection = build_vector_store(chunks, chroma_dir, recreate=recreate)
    
    # Summary
    summary = {
        'source': source,
        'transcripts_loaded': len(transcripts),
        'chunks_created': len(chunks),
        'vectors_stored': collection.count(),
        'chroma_dir': str(chroma_dir),
    }
    
    print("\n" + "=" * 60)
    print("BUILD COMPLETE")
    print("=" * 60)
    print(f"Source: {summary['source']}")
    print(f"Transcripts loaded: {summary['transcripts_loaded']}")
    print(f"Chunks created: {summary['chunks_created']}")
    print(f"Vectors stored: {summary['vectors_stored']}")
    print(f"ChromaDB location: {summary['chroma_dir']}")
    
    return summary


# ============================================================================
# CLI Interface
# ============================================================================

def main():
    """Main entry point for knowledge base building."""
    import argparse
    
    parser = argparse.ArgumentParser(
        description='Build Seerah knowledge base from transcripts'
    )
    parser.add_argument(
        '--source',
        choices=['huggingface', 'local'],
        default='huggingface',
        help='Data source: huggingface (recommended) or local JSON files'
    )
    parser.add_argument(
        '--transcripts-dir',
        default=str(TRANSCRIPTS_DIR),
        help='Directory containing local transcript JSON files (only for --source local)'
    )
    parser.add_argument(
        '--chroma-dir',
        default=str(CHROMA_DB_DIR),
        help='Directory for ChromaDB persistence'
    )
    parser.add_argument(
        '--recreate',
        action='store_true',
        help='Recreate the knowledge base from scratch'
    )
    
    args = parser.parse_args()
    
    build_knowledge_base(
        source=args.source,
        transcripts_dir=Path(args.transcripts_dir),
        chroma_dir=Path(args.chroma_dir),
        recreate=args.recreate
    )


if __name__ == "__main__":
    main()
