# Chunking Strategy for Seerah Knowledge Base

This document explains the chunking approach used to process the Seerah lecture transcripts for the RAG system.

## Why Chunking Matters

Chunking is critical for RAG performance:

- **Too large chunks**: Diluted context, wasted tokens, less relevant results
- **Too small chunks**: Missing context, incomplete information
- **Poor boundaries**: Split sentences, broken concepts

## Our Approach: Segment-Based Chunking with Overlap

We use a **segment-based chunking strategy** that:
1. Respects natural transcript segments (from YouTube captions)
2. Groups segments until reaching target token count
3. Creates overlap between chunks for context continuity
4. Preserves timestamp metadata for source citations

## Configuration

```python
# In config/settings.py
CHUNK_SIZE = 500       # Target tokens per chunk
CHUNK_OVERLAP = 50     # Overlap tokens between chunks
MIN_CHUNK_SIZE = 100   # Minimum tokens for valid chunk
```

## Algorithm Overview

```
Input: Transcript segments with timestamps
       [{text: "...", start: 0.0, duration: 5.2}, ...]

Step 1: Initialize empty chunk
Step 2: Add segments until reaching CHUNK_SIZE tokens
Step 3: Save chunk with start/end timestamps
Step 4: Keep last CHUNK_OVERLAP tokens for next chunk
Step 5: Repeat until all segments processed

Output: List of chunks with metadata
        [{text: "...", start_time: 0.0, end_time: 45.2, video_id: "..."}, ...]
```

## Detailed Algorithm

```python
def chunk_by_segments(segments, target_tokens=500, overlap_tokens=50):
    chunks = []
    current_chunk_segments = []
    current_tokens = 0
    overlap_segments = []
    
    for segment in segments:
        segment_tokens = estimate_tokens(segment['text'])
        
        # If adding this segment exceeds target, create chunk
        if current_tokens + segment_tokens > target_tokens and current_chunk_segments:
            # Build chunk from current segments
            chunk = {
                'text': ' '.join(s['text'] for s in current_chunk_segments),
                'start_time': current_chunk_segments[0]['start'],
                'end_time': current_chunk_segments[-1]['start'] + 
                           current_chunk_segments[-1]['duration']
            }
            chunks.append(chunk)
            
            # Calculate overlap segments for next chunk
            overlap_segments = []
            overlap_count = 0
            for seg in reversed(current_chunk_segments):
                seg_tokens = estimate_tokens(seg['text'])
                if overlap_count + seg_tokens <= overlap_tokens:
                    overlap_segments.insert(0, seg)
                    overlap_count += seg_tokens
                else:
                    break
            
            # Start new chunk with overlap
            current_chunk_segments = overlap_segments.copy()
            current_tokens = overlap_count
        
        # Add current segment
        current_chunk_segments.append(segment)
        current_tokens += segment_tokens
    
    # Don't forget the last chunk
    if current_chunk_segments:
        chunks.append(build_chunk(current_chunk_segments))
    
    return chunks
```

## Why This Approach?

### 1. Respecting Transcript Segments

YouTube transcripts come with natural segments (usually 3-10 seconds each):

```json
[
  {"text": "Bismillah Ar-Rahman Ar-Raheem", "start": 0.0, "duration": 2.5},
  {"text": "Today we continue our discussion", "start": 2.5, "duration": 3.2},
  {"text": "of the early life of the Prophet", "start": 5.7, "duration": 2.8}
]
```

These segments often align with natural speech patterns, making them good building blocks.

### 2. Token-Based Sizing

We target ~500 tokens per chunk because:
- Small enough for precise retrieval
- Large enough to contain complete thoughts
- Fits well within embedding model limits
- Allows multiple chunks in LLM context

### 3. Overlap for Continuity

Overlapping chunks prevent information loss at boundaries:

```
Chunk 1: "...the Prophet received revelation at age 40. This was in the cave of Hira..."
                                                       ↓ overlap starts here
Chunk 2: "This was in the cave of Hira, where he would spend many nights in contemplation..."
```

Without overlap, a question about "where did the Prophet receive revelation" might miss the connection.

### 4. Timestamp Preservation

Each chunk keeps timestamps for source citations:

```python
{
    'text': "The Battle of Badr was the first major...",
    'video_id': "abc123",
    'title': "Lecture 45 - The Battle of Badr",
    'playlist_index': 45,
    'start_time': 1234.5,  # 20:34
    'end_time': 1289.2     # 21:29
}
```

This enables direct links to the relevant video moment.

## Fallback: Sentence-Based Chunking

When segments aren't available, we fall back to sentence-based chunking:

```python
def chunk_full_text(text, target_tokens=500, overlap_tokens=50):
    sentences = split_into_sentences(text)
    
    chunks = []
    current_sentences = []
    current_tokens = 0
    
    for sentence in sentences:
        sentence_tokens = estimate_tokens(sentence)
        
        if current_tokens + sentence_tokens > target_tokens and current_sentences:
            chunks.append(' '.join(current_sentences))
            
            # Calculate overlap
            overlap_sentences = get_overlap_sentences(current_sentences, overlap_tokens)
            current_sentences = overlap_sentences
            current_tokens = sum(estimate_tokens(s) for s in overlap_sentences)
        
        current_sentences.append(sentence)
        current_tokens += sentence_tokens
    
    return chunks
```

## Token Estimation

We use a simple but effective approximation:

```python
def estimate_tokens(text: str) -> int:
    """~4 characters per token is a reasonable estimate for English."""
    return len(text) // 4
```

For more precision, you could use `tiktoken`:

```python
import tiktoken

encoder = tiktoken.get_encoding("cl100k_base")

def estimate_tokens(text: str) -> int:
    return len(encoder.encode(text))
```

## Chunk Metadata

Each chunk carries metadata for retrieval and citation:

```python
{
    'id': 'abc123_0042',           # Unique identifier
    'text': '...',                  # Chunk content
    'video_id': 'abc123',           # YouTube video ID
    'title': 'Lecture 45...',       # Video title
    'playlist_index': 45,           # Position in playlist
    'chunk_index': 42,              # Position within video
    'start_time': 1234.5,           # Start timestamp (seconds)
    'end_time': 1289.2              # End timestamp (seconds)
}
```

## Chunk Statistics (Expected)

For the 104-video Seerah series:

| Metric | Estimated Value |
|--------|-----------------|
| Total videos | 104 |
| Average video length | ~90 minutes |
| Average transcript words | ~13,500 |
| Chunks per video | ~100-150 |
| **Total chunks** | ~10,000-15,000 |

## Quality Considerations

### Good Chunks

```
"Abu Talib, the Prophet's uncle, provided crucial protection during the 
early years of Islam. Without his tribal support, the Quraysh would have 
been able to harm the Prophet directly. Despite not accepting Islam himself, 
Abu Talib's love for his nephew was unwavering."
```

- Complete thought
- Self-contained context
- Clear subject matter

### Bad Chunks

```
"and then he said that the Prophet. Abu Talib was his uncle and he"
```

- Sentence fragments
- Missing context
- Unclear subject

## Optimization Tips

### 1. Adjust Chunk Size for Your Use Case

```python
# For detailed Q&A (recommended)
CHUNK_SIZE = 500
CHUNK_OVERLAP = 50

# For broader topic search
CHUNK_SIZE = 800
CHUNK_OVERLAP = 100

# For precise fact retrieval
CHUNK_SIZE = 300
CHUNK_OVERLAP = 30
```

### 2. Consider Semantic Chunking

For more advanced chunking, consider semantic boundaries:

```python
def semantic_chunk(text):
    """Chunk based on topic changes, not just size."""
    paragraphs = text.split('\n\n')
    
    chunks = []
    current_chunk = []
    
    for para in paragraphs:
        if should_start_new_chunk(current_chunk, para):
            chunks.append(' '.join(current_chunk))
            current_chunk = []
        current_chunk.append(para)
    
    return chunks
```

### 3. Handle Special Cases

```python
# Skip intro/outro segments
def is_valid_segment(segment):
    text = segment['text'].lower()
    skip_phrases = ['subscribe', 'like and share', 'next video']
    return not any(phrase in text for phrase in skip_phrases)

# Filter before chunking
segments = [s for s in segments if is_valid_segment(s)]
```

## Testing Your Chunks

```python
def analyze_chunks(chunks):
    sizes = [estimate_tokens(c['text']) for c in chunks]
    
    print(f"Total chunks: {len(chunks)}")
    print(f"Avg tokens: {sum(sizes) / len(sizes):.0f}")
    print(f"Min tokens: {min(sizes)}")
    print(f"Max tokens: {max(sizes)}")
    
    # Check for problematic chunks
    small_chunks = [c for c in chunks if estimate_tokens(c['text']) < 100]
    print(f"Very small chunks (<100 tokens): {len(small_chunks)}")

# Run analysis
chunks = chunk_all_transcripts(transcripts)
analyze_chunks(chunks)
```

## Future Improvements

1. **Hierarchical chunking**: Create multi-level chunks (paragraph → section → lecture)
2. **Topic-aware chunking**: Use NLP to detect topic boundaries
3. **Speaker diarization**: Chunk by speaker changes (for Q&A portions)
4. **Cross-reference linking**: Link related chunks across videos
