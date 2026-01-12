"""
Knowledge Base Builder Module

This module handles creating the vector database from transcripts.
It includes:
- Loading transcripts from JSON files
- Semantic chunking with overlap
- Generating embeddings using HuggingFace sentence-transformers (free!)
- Storing in ChromaDB for efficient retrieval

Usage:
    python -m data_pipeline.knowledge_base

See docs/CHUNKING_STRATEGY.md for detailed chunking approach.
"""

import json
import sys
import time
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
# Transcript Loading
# ============================================================================

def load_transcripts(transcripts_dir: Path = TRANSCRIPTS_DIR) -> list[dict]:
    """
    Load all transcript JSON files from the transcripts directory.
    
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
            transcripts.append(data)
    
    print(f"Loaded {len(transcripts)} transcripts")
    return transcripts


# ============================================================================
# Text Tokenization (Simple Approximation)
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


# ============================================================================
# Preprocessing - Merge Fragmented Segments
# ============================================================================

def preprocess_segments(
    segments: list[dict],
    target_duration: float = 60.0,
    min_chars: int = 500
) -> list[dict]:
    """
    Merge fragmented transcript segments into larger, coherent paragraphs.
    
    YouTube auto-captions produce very short segments (~7 words each).
    This function merges them into larger blocks for better chunking.
    
    Args:
        segments: List of transcript segments with 'text', 'start', 'duration'
        target_duration: Target duration in seconds for merged paragraphs (~60s)
        min_chars: Minimum characters per merged paragraph
        
    Returns:
        List of merged paragraph dictionaries with:
        - text: Merged text content
        - start: Start timestamp of first segment
        - end: End timestamp of last segment
    """
    if not segments:
        return []
    
    merged = []
    current_texts = []
    current_start = segments[0].get('start', 0)
    current_duration = 0
    
    for seg in segments:
        seg_text = seg.get('text', '').strip()
        seg_start = seg.get('start', 0)
        seg_duration = seg.get('duration', 0)
        
        if not seg_text:
            continue
        
        current_texts.append(seg_text)
        current_duration = (seg_start + seg_duration) - current_start
        current_chars = sum(len(t) for t in current_texts)
        
        # Create paragraph when we hit target duration or min chars
        if current_duration >= target_duration or current_chars >= min_chars * 2:
            merged_text = ' '.join(current_texts)
            merged.append({
                'text': merged_text,
                'start': current_start,
                'end': seg_start + seg_duration,
            })
            
            # Reset for next paragraph
            current_texts = []
            current_start = seg_start + seg_duration
            current_duration = 0
    
    # Don't forget the last paragraph
    if current_texts:
        last_seg = segments[-1]
        merged.append({
            'text': ' '.join(current_texts),
            'start': current_start,
            'end': last_seg.get('start', 0) + last_seg.get('duration', 0),
        })
    
    return merged


# ============================================================================
# Chunking Strategy
# ============================================================================

def chunk_by_segments(
    segments: list[dict],
    target_tokens: int = CHUNK_SIZE,
    overlap_tokens: int = CHUNK_OVERLAP
) -> list[dict]:
    """
    Create chunks from transcript segments with overlap.
    
    This chunking strategy:
    1. Groups consecutive segments until reaching target token count
    2. Preserves timestamp information for each chunk
    3. Creates overlap with previous chunk for context continuity
    
    Args:
        segments: List of transcript segments with 'text', 'start', 'duration'
        target_tokens: Target tokens per chunk
        overlap_tokens: Overlap tokens between chunks
        
    Returns:
        List of chunk dictionaries with:
        - text: Chunk text content
        - start_time: Start timestamp in seconds
        - end_time: End timestamp in seconds
        - segment_indices: Indices of original segments in this chunk
    """
    if not segments:
        return []
    
    chunks = []
    current_chunk_segments = []
    current_tokens = 0
    overlap_segments = []
    
    for i, segment in enumerate(segments):
        segment_text = segment.get('text', '')
        segment_tokens = estimate_tokens(segment_text)
        
        # If adding this segment exceeds target, create chunk
        if current_tokens + segment_tokens > target_tokens and current_chunk_segments:
            # Build chunk from current segments
            chunk = build_chunk_from_segments(current_chunk_segments, segments)
            chunks.append(chunk)
            
            # Calculate overlap segments
            overlap_segments = []
            overlap_token_count = 0
            for seg in reversed(current_chunk_segments):
                seg_tokens = estimate_tokens(seg.get('text', ''))
                if overlap_token_count + seg_tokens <= overlap_tokens:
                    overlap_segments.insert(0, seg)
                    overlap_token_count += seg_tokens
                else:
                    break
            
            # Start new chunk with overlap
            current_chunk_segments = overlap_segments.copy()
            current_tokens = sum(estimate_tokens(s.get('text', '')) for s in current_chunk_segments)
        
        # Add current segment
        current_chunk_segments.append(segment)
        current_tokens += segment_tokens
    
    # Don't forget the last chunk
    if current_chunk_segments:
        chunk = build_chunk_from_segments(current_chunk_segments, segments)
        chunks.append(chunk)
    
    return chunks


def build_chunk_from_segments(chunk_segments: list[dict], all_segments: list[dict]) -> dict:
    """
    Build a chunk dictionary from a list of segments.
    
    Args:
        chunk_segments: Segments to include in chunk
        all_segments: All segments (for index lookup)
        
    Returns:
        Chunk dictionary
    """
    text = ' '.join(seg.get('text', '') for seg in chunk_segments)
    
    start_time = chunk_segments[0].get('start', 0)
    last_seg = chunk_segments[-1]
    
    # Handle both formats: 'end' (from merged paragraphs) or 'start' + 'duration' (raw segments)
    if 'end' in last_seg:
        end_time = last_seg.get('end', 0)
    else:
        end_time = last_seg.get('start', 0) + last_seg.get('duration', 0)
    
    # Find segment indices
    segment_indices = []
    for seg in chunk_segments:
        try:
            idx = all_segments.index(seg)
            segment_indices.append(idx)
        except ValueError:
            pass
    
    return {
        'text': text,
        'start_time': start_time,
        'end_time': end_time,
        'segment_indices': segment_indices,
    }


def chunk_transcript(transcript: dict) -> list[dict]:
    """
    Chunk a single transcript into retrievable chunks.
    
    Pipeline:
    1. Get raw segments from transcript
    2. Preprocess: merge fragmented segments into paragraphs (~60s each)
    3. Chunk: split paragraphs into ~500 token chunks with overlap
    4. Add metadata to each chunk
    
    Args:
        transcript: Full transcript dictionary with metadata and segments
        
    Returns:
        List of chunk dictionaries with video metadata
    """
    # Get transcript segments
    raw_segments = transcript.get('transcript', {}).get('segments', [])
    
    if not raw_segments:
        # Fallback: chunk the full text if no segments
        full_text = transcript.get('transcript', {}).get('full_text', '')
        if not full_text:
            return []
        
        chunks = chunk_full_text(full_text)
    else:
        # Step 1: Preprocess - merge fragmented segments into larger paragraphs
        # This handles YouTube's short segments (~7 words each)
        merged_paragraphs = preprocess_segments(raw_segments, target_duration=60.0)
        
        # Step 2: Chunk the merged paragraphs
        if merged_paragraphs:
            chunks = chunk_by_segments(merged_paragraphs)
        else:
            # Fallback to full text if preprocessing fails
            full_text = transcript.get('transcript', {}).get('full_text', '')
            chunks = chunk_full_text(full_text) if full_text else []
    
    # Add video metadata to each chunk
    video_metadata = {
        'video_id': transcript.get('video_id', ''),
        'title': transcript.get('title', ''),
        'playlist_index': transcript.get('playlist_index', 0),
    }
    
    for i, chunk in enumerate(chunks):
        chunk['chunk_index'] = i
        chunk.update(video_metadata)
        # Create unique ID for this chunk
        chunk['id'] = f"{video_metadata['video_id']}_{i:04d}"
    
    return chunks


def chunk_full_text(
    text: str,
    target_tokens: int = CHUNK_SIZE,
    overlap_tokens: int = CHUNK_OVERLAP
) -> list[dict]:
    """
    Fallback chunking for full text without segments.
    Uses sentence boundaries for cleaner chunks.
    
    Args:
        text: Full transcript text
        target_tokens: Target tokens per chunk
        overlap_tokens: Overlap tokens between chunks
        
    Returns:
        List of chunk dictionaries
    """
    sentences = split_into_sentences(text)
    
    chunks = []
    current_sentences = []
    current_tokens = 0
    overlap_sentences = []
    
    for sentence in sentences:
        sentence_tokens = estimate_tokens(sentence)
        
        if current_tokens + sentence_tokens > target_tokens and current_sentences:
            # Create chunk
            chunk_text = ' '.join(current_sentences)
            chunks.append({
                'text': chunk_text,
                'start_time': 0,
                'end_time': 0,
            })
            
            # Calculate overlap
            overlap_sentences = []
            overlap_count = 0
            for s in reversed(current_sentences):
                s_tokens = estimate_tokens(s)
                if overlap_count + s_tokens <= overlap_tokens:
                    overlap_sentences.insert(0, s)
                    overlap_count += s_tokens
                else:
                    break
            
            current_sentences = overlap_sentences.copy()
            current_tokens = overlap_count
        
        current_sentences.append(sentence)
        current_tokens += sentence_tokens
    
    # Last chunk
    if current_sentences:
        chunk_text = ' '.join(current_sentences)
        chunks.append({
            'text': chunk_text,
            'start_time': 0,
            'end_time': 0,
        })
    
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
        print(f"  Chunked '{transcript.get('title', 'Unknown')[:40]}...' into {len(chunks)} chunks")
    
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
        metadata={"description": "Seerah lecture transcripts knowledge base"}
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
        print(f"Collection already has {existing_count} documents. Use recreate=True to rebuild.")
        return collection
    
    print(f"Building vector store with {len(chunks)} chunks...")
    
    # Generate embeddings and add to collection in batches
    for batch_chunks, embeddings in create_embeddings(chunks):
        # Prepare data for ChromaDB
        ids = [chunk['id'] for chunk in batch_chunks]
        documents = [chunk['text'] for chunk in batch_chunks]
        metadatas = [
            {
                'video_id': chunk.get('video_id', ''),
                'title': chunk.get('title', ''),
                'playlist_index': chunk.get('playlist_index', 0),
                'chunk_index': chunk.get('chunk_index', 0),
                'start_time': chunk.get('start_time', 0),
                'end_time': chunk.get('end_time', 0),
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
    transcripts_dir: Path = TRANSCRIPTS_DIR,
    chroma_dir: Path = CHROMA_DB_DIR,
    recreate: bool = False
) -> dict:
    """
    Full pipeline to build the knowledge base.
    
    1. Load transcripts from JSON files
    2. Chunk transcripts using semantic chunking
    3. Generate embeddings using Gemini
    4. Store in ChromaDB
    
    Args:
        transcripts_dir: Directory containing transcript JSON files
        chroma_dir: Directory for ChromaDB persistence
        recreate: If True, rebuild the entire knowledge base
        
    Returns:
        Summary dictionary with statistics
    """
    print("=" * 60)
    print("Building Seerah Knowledge Base")
    print("=" * 60)
    
    # Step 1: Load transcripts
    print("\n[1/3] Loading transcripts...")
    transcripts = load_transcripts(transcripts_dir)
    
    if not transcripts:
        print("No transcripts found! Run transcript_fetcher.py first.")
        return {'error': 'No transcripts found'}
    
    # Step 2: Chunk transcripts
    print("\n[2/3] Chunking transcripts...")
    chunks = chunk_all_transcripts(transcripts)
    
    # Step 3: Build vector store (includes embedding)
    print("\n[3/3] Building vector store (this may take a while)...")
    collection = build_vector_store(chunks, chroma_dir, recreate=recreate)
    
    # Summary
    summary = {
        'transcripts_loaded': len(transcripts),
        'chunks_created': len(chunks),
        'vectors_stored': collection.count(),
        'chroma_dir': str(chroma_dir),
    }
    
    print("\n" + "=" * 60)
    print("BUILD COMPLETE")
    print("=" * 60)
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
        '--transcripts-dir',
        default=str(TRANSCRIPTS_DIR),
        help='Directory containing transcript JSON files'
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
        transcripts_dir=Path(args.transcripts_dir),
        chroma_dir=Path(args.chroma_dir),
        recreate=args.recreate
    )


if __name__ == "__main__":
    main()
