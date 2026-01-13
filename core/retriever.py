"""
RAG Retriever Module

This module handles the core RAG (Retrieval Augmented Generation) logic:
1. Query the vector database for relevant chunks
2. Build context from retrieved chunks
3. Generate responses using Gemini with memory context
4. Format responses with source citations

This is the main query processing pipeline that ties together:
- Vector store (ChromaDB)
- Embeddings (HuggingFace sentence-transformers - FREE!)
- LLM (Gemini)
- Memory (ChatMemory)
"""

import sys
from pathlib import Path
from typing import Optional
from dataclasses import dataclass

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

import google.generativeai as genai
from sentence_transformers import SentenceTransformer
import chromadb
from chromadb.config import Settings

from config.settings import (
    GEMINI_API_KEY,
    CHROMA_DB_DIR,
    COLLECTION_NAME,
    EMBEDDING_MODEL,
    LLM_MODEL,
    LLM_TEMPERATURE,
    LLM_MAX_TOKENS,
    RETRIEVAL_TOP_K,
    SIMILARITY_THRESHOLD,
    SYSTEM_PROMPT,
)
from core.chat_memory import ChatMemory
from core.guardrails import check_query, ContentAction


# Configure Gemini (for LLM only, embeddings use HuggingFace)
genai.configure(api_key=GEMINI_API_KEY)

# Singleton embedding model
_embedding_model = None


def get_embedding_model() -> SentenceTransformer:
    """Get or initialize the sentence transformer model (singleton pattern)."""
    global _embedding_model
    if _embedding_model is None:
        _embedding_model = SentenceTransformer(EMBEDDING_MODEL)
    return _embedding_model


@dataclass
class RetrievedChunk:
    """Represents a retrieved chunk from the vector store."""
    text: str
    video_id: str
    title: str
    lecture_number: int
    chunk_index: int
    distance: float  # Lower is more similar
    
    @property
    def similarity_score(self) -> float:
        """Convert distance to similarity score (0-1)."""
        # ChromaDB uses L2 distance, convert to similarity
        return 1 / (1 + self.distance)
    
    @property
    def youtube_link(self) -> str:
        """Generate YouTube link (no timestamp since we don't track them)."""
        if self.video_id:
            return f"https://www.youtube.com/watch?v={self.video_id}"
        return ""
    
    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            'video_id': self.video_id,
            'title': self.title,
            'lecture_number': self.lecture_number,
            'youtube_link': self.youtube_link,
            'similarity': self.similarity_score,
        }


@dataclass
class RAGResponse:
    """Represents the response from the RAG system."""
    answer: str
    sources: list[RetrievedChunk]
    query: str
    blocked: bool = False  # True if query was blocked/redirected by guardrails
    
    def to_dict(self) -> dict:
        """Convert to dictionary for storage."""
        return {
            'answer': self.answer,
            'sources': [s.to_dict() for s in self.sources],
            'query': self.query,
            'blocked': self.blocked,
        }


class SeerahRetriever:
    """
    Main RAG retriever for the Seerah knowledge base.
    
    This class handles:
    1. Querying ChromaDB for relevant chunks
    2. Embedding user queries using sentence-transformers
    3. Building context from retrieved chunks
    4. Generating responses using Gemini LLM
    5. Integrating conversation memory
    """
    
    def __init__(
        self,
        chroma_dir: Path = CHROMA_DB_DIR,
        collection_name: str = COLLECTION_NAME
    ):
        """
        Initialize the retriever.
        
        Args:
            chroma_dir: Path to ChromaDB persistence directory
            collection_name: Name of the ChromaDB collection
        """
        self.chroma_dir = Path(chroma_dir)
        self.collection_name = collection_name
        self._client = None
        self._collection = None
        self._model = None
    
    @property
    def client(self) -> chromadb.PersistentClient:
        """Lazy-load ChromaDB client."""
        if self._client is None:
            self._client = chromadb.PersistentClient(
                path=str(self.chroma_dir),
                settings=Settings(anonymized_telemetry=False)
            )
        return self._client
    
    @property
    def collection(self) -> chromadb.Collection:
        """Lazy-load ChromaDB collection."""
        if self._collection is None:
            self._collection = self.client.get_collection(self.collection_name)
        return self._collection
    
    @property
    def model(self) -> genai.GenerativeModel:
        """Lazy-load Gemini model."""
        if self._model is None:
            self._model = genai.GenerativeModel(LLM_MODEL)
        return self._model
    
    def is_ready(self) -> bool:
        """Check if the knowledge base is ready for queries."""
        try:
            count = self.collection.count()
            return count > 0
        except Exception:
            return False
    
    # ========================================================================
    # Query Embedding (HuggingFace - FREE!)
    # ========================================================================
    
    def embed_query(self, query: str) -> list[float]:
        """
        Generate embedding for a query using sentence-transformers.
        
        This runs locally - completely FREE!
        
        Args:
            query: User query text
            
        Returns:
            Embedding vector
        """
        model = get_embedding_model()
        embedding = model.encode(query)
        return embedding.tolist()
    
    # ========================================================================
    # Retrieval
    # ========================================================================
    
    def retrieve(
        self,
        query: str,
        top_k: int = RETRIEVAL_TOP_K,
        min_similarity: float = SIMILARITY_THRESHOLD
    ) -> list[RetrievedChunk]:
        """
        Retrieve relevant chunks from the knowledge base.
        
        Args:
            query: User query text
            top_k: Number of chunks to retrieve
            min_similarity: Minimum similarity threshold
            
        Returns:
            List of RetrievedChunk objects
        """
        # Generate query embedding
        query_embedding = self.embed_query(query)
        
        # Query ChromaDB
        results = self.collection.query(
            query_embeddings=[query_embedding],
            n_results=top_k,
            include=['documents', 'metadatas', 'distances']
        )
        
        chunks = []
        
        if results and results['documents']:
            documents = results['documents'][0]
            metadatas = results['metadatas'][0]
            distances = results['distances'][0]
            
            for doc, meta, dist in zip(documents, metadatas, distances):
                # Support both old schema (playlist_index) and new schema (lecture_number)
                lecture_num = meta.get('lecture_number', meta.get('playlist_index', 0))
                
                chunk = RetrievedChunk(
                    text=doc,
                    video_id=meta.get('video_id', ''),
                    title=meta.get('title', ''),
                    lecture_number=lecture_num,
                    chunk_index=meta.get('chunk_index', 0),
                    distance=dist
                )
                
                # Filter by similarity threshold
                if chunk.similarity_score >= min_similarity:
                    chunks.append(chunk)
        
        return chunks
    
    # ========================================================================
    # Context Building
    # ========================================================================
    
    def build_context(self, chunks: list[RetrievedChunk]) -> str:
        """
        Build context string from retrieved chunks.
        
        Args:
            chunks: List of retrieved chunks
            
        Returns:
            Formatted context string
        """
        if not chunks:
            return "No relevant context found in the knowledge base."
        
        context_parts = []
        
        for i, chunk in enumerate(chunks, 1):
            context_parts.append(
                f"[Source {i}: {chunk.title} (Lecture {chunk.lecture_number})]\n"
                f"{chunk.text}\n"
            )
        
        return "\n".join(context_parts)
    
    # ========================================================================
    # Response Generation
    # ========================================================================
    
    def generate_response(
        self,
        query: str,
        context: str,
        memory_context: str = ""
    ) -> str:
        """
        Generate a response using Gemini.
        
        Args:
            query: User query
            context: Retrieved context from knowledge base
            memory_context: Previous conversation memory
            
        Returns:
            Generated response text
        """
        # Build the full prompt
        prompt_parts = [SYSTEM_PROMPT]
        
        if memory_context:
            prompt_parts.append(f"\n{memory_context}\n")
        
        prompt_parts.append(f"\n=== Knowledge Base Context ===\n{context}")
        prompt_parts.append(f"\n=== Current Question ===\n{query}")
        prompt_parts.append(
            "\nProvide a helpful, accurate answer based on the context. "
            "If the context doesn't contain relevant information, say so honestly."
        )
        
        full_prompt = "\n".join(prompt_parts)
        
        # Generate response
        generation_config = genai.GenerationConfig(
            temperature=LLM_TEMPERATURE,
            max_output_tokens=LLM_MAX_TOKENS,
        )
        
        response = self.model.generate_content(
            full_prompt,
            generation_config=generation_config
        )
        
        return response.text.strip()
    
    # ========================================================================
    # Main Query Pipeline
    # ========================================================================
    
    def query(
        self,
        query: str,
        memory: Optional[ChatMemory] = None,
        top_k: int = RETRIEVAL_TOP_K,
        skip_guardrails: bool = False
    ) -> RAGResponse:
        """
        Process a user query through the full RAG pipeline.
        
        Pipeline:
        0. Check guardrails (block/redirect inappropriate content)
        1. Retrieve relevant chunks from knowledge base
        2. Build context from chunks
        3. Get memory context (if available)
        4. Generate response using Gemini
        5. Return response with sources
        
        Args:
            query: User query text
            memory: Optional ChatMemory for conversation context
            top_k: Number of chunks to retrieve
            skip_guardrails: If True, bypass content moderation
            
        Returns:
            RAGResponse object with answer and sources
        """
        # Step 0: Check guardrails (unless skipped)
        if not skip_guardrails:
            guardrail_result = check_query(query)
            
            if guardrail_result.action != ContentAction.ALLOW:
                # Return the guardrail message without RAG processing
                return RAGResponse(
                    answer=guardrail_result.message or "I can only help with questions about the Seerah.",
                    sources=[],
                    query=query,
                    blocked=True
                )
        
        # Step 1: Retrieve relevant chunks
        chunks = self.retrieve(query, top_k=top_k)
        
        # Step 2: Build context
        context = self.build_context(chunks)
        
        # Step 3: Get memory context
        memory_context = ""
        if memory:
            memory_data = memory.get_memory_context()
            memory_context = memory_data.get('formatted_history', '')
        
        # Step 4: Generate response
        answer = self.generate_response(query, context, memory_context)
        
        # Step 5: Build response object
        return RAGResponse(
            answer=answer,
            sources=chunks,
            query=query,
            blocked=False
        )
    
    def query_with_memory(
        self,
        query: str,
        session_id: int,
        top_k: int = RETRIEVAL_TOP_K
    ) -> RAGResponse:
        """
        Process a query with automatic memory management.
        
        This method:
        1. Creates/loads ChatMemory for the session
        2. Processes the query
        3. Saves both query and response to memory
        
        Args:
            query: User query text
            session_id: Chat session ID
            top_k: Number of chunks to retrieve
            
        Returns:
            RAGResponse object with answer and sources
        """
        # Load memory
        memory = ChatMemory(session_id)
        
        # Process query
        response = self.query(query, memory=memory, top_k=top_k)
        
        # Save to memory
        memory.add_message('user', query)
        memory.add_message(
            'assistant',
            response.answer,
            sources=[s.to_dict() for s in response.sources]
        )
        
        return response


# ============================================================================
# Helper Functions
# ============================================================================

def format_sources_for_display(sources: list[RetrievedChunk]) -> str:
    """
    Format sources for user-friendly display.
    
    Args:
        sources: List of retrieved chunks
        
    Returns:
        Formatted string with source citations
    """
    if not sources:
        return ""
    
    lines = ["**Sources:**"]
    
    # Group by lecture to avoid duplicates
    seen_lectures = set()
    
    for source in sources:
        lecture_key = (source.lecture_number, source.title)
        if lecture_key not in seen_lectures:
            seen_lectures.add(lecture_key)
            
            if source.youtube_link:
                lines.append(
                    f"- [{source.title}]({source.youtube_link}) "
                    f"(Lecture {source.lecture_number})"
                )
            else:
                lines.append(
                    f"- {source.title} (Lecture {source.lecture_number})"
                )
    
    return "\n".join(lines)


def get_retriever() -> SeerahRetriever:
    """
    Get a SeerahRetriever instance.
    
    Returns:
        Configured SeerahRetriever
    """
    return SeerahRetriever()
