"""
Content Guardrails Module

This module provides content moderation for the Seerah Q&A application.
It implements a two-tier approach:

Tier 1 - Block: Offensive, hateful, or clearly inappropriate content
Tier 2 - Redirect: Off-topic questions gently steered back to Seerah

The guardrails run BEFORE the RAG pipeline to save compute and provide
appropriate responses without searching the knowledge base.
"""

import re
import sys
from pathlib import Path
from typing import Optional
from dataclasses import dataclass
from enum import Enum

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

import google.generativeai as genai
from config.settings import GEMINI_API_KEY, LLM_MODEL

# Configure Gemini
genai.configure(api_key=GEMINI_API_KEY)


class ContentAction(Enum):
    """Actions the guardrail can take."""
    ALLOW = "allow"          # Question is appropriate, proceed with RAG
    BLOCK = "block"          # Offensive content, refuse politely
    REDIRECT = "redirect"    # Off-topic, suggest Seerah topics


@dataclass
class GuardrailResult:
    """Result of content moderation check."""
    action: ContentAction
    message: Optional[str] = None  # Response message if blocked/redirected
    reason: Optional[str] = None   # Internal reason for logging


class ContentGuardrails:
    """
    Content moderation system for the Seerah Q&A application.
    
    Uses a fast keyword-based pre-filter followed by LLM classification
    for edge cases. Designed to be respectful while maintaining focus
    on the Seerah knowledge base.
    """
    
    # Tier 1: Offensive content patterns (fast keyword filter)
    BLOCKED_PATTERNS = [
        # Profanity and slurs (keeping list minimal but effective)
        r'\b(fuck|shit|damn|ass|bitch|bastard|crap)\b',
        r'\b(nigger|faggot|retard|spic|chink|kike)\b',
        # Hate speech indicators
        r'\b(kill\s+(all\s+)?(muslims?|jews?|christians?|hindus?))\b',
        r'\b(death\s+to)\b',
        r'\b(terrorist|terrorism)\s+(is\s+)?(good|great|awesome)\b',
        # Sexually explicit
        r'\b(porn|xxx|nude|naked|sex\s+with)\b',
        # Violence incitement
        r'\b(how\s+to\s+(kill|murder|bomb|attack))\b',
    ]
    
    # Compile patterns for efficiency
    _blocked_regex = None
    
    # Polite block messages
    BLOCK_MESSAGES = [
        "I'm here to help you learn about the blessed life of Prophet Muhammad ﷺ. "
        "Let's keep our conversation respectful and focused on beneficial knowledge. "
        "What would you like to know about the Seerah?",
    ]
    
    # Redirect message template
    REDIRECT_MESSAGE = (
        "This platform is dedicated to exploring the Seerah (biography) of "
        "Prophet Muhammad ﷺ based on Shaykh Yasir Qadhi's comprehensive lecture series.\n\n"
        "I'd be happy to help you learn about topics such as:\n"
        "• The Prophet's ﷺ early life and family\n"
        "• The revelation and early Islam in Makkah\n"
        "• The Hijrah and establishment of Madinah\n"
        "• Key battles and events\n"
        "• The Prophet's ﷺ character and teachings\n"
        "• His companions and family members\n\n"
        "What aspect of the Seerah interests you?"
    )
    
    # Topics related to Seerah/Islam (for relevance checking)
    RELEVANT_KEYWORDS = [
        'prophet', 'muhammad', 'mohammed', 'pbuh', 'seerah', 'sirah',
        'islam', 'muslim', 'quran', 'hadith', 'sunnah',
        'makkah', 'mecca', 'madinah', 'medina', 'hijrah', 'migration',
        'companion', 'sahaba', 'sahabi', 'sahabah',
        'battle', 'badr', 'uhud', 'khandaq', 'trench', 'hunayn', 'tabuk',
        'khadijah', 'aisha', 'fatimah', 'ali', 'umar', 'uthman', 'abu bakr',
        'quraish', 'quraysh', 'revelation', 'jibreel', 'gabriel',
        'yasir qadhi', 'shaykh', 'sheikh', 'lecture',
        'isra', 'miraj', 'night journey', 'ascension',
        'treaty', 'hudaybiyyah', 'conquest', 'fath',
        'wife', 'wives', 'children', 'family',
        'miracle', 'sign', 'ayah', 'verse',
        'prayer', 'salah', 'fasting', 'ramadan', 'hajj', 'zakat',
        'allah', 'god', 'lord', 'creator',
        'angel', 'jannah', 'paradise', 'afterlife',
        'birth', 'death', 'life', 'biography', 'history',
    ]
    
    def __init__(self):
        """Initialize the guardrails system."""
        self._compile_patterns()
        self._model = None
    
    @classmethod
    def _compile_patterns(cls):
        """Compile regex patterns for efficiency."""
        if cls._blocked_regex is None:
            combined = '|'.join(cls.BLOCKED_PATTERNS)
            cls._blocked_regex = re.compile(combined, re.IGNORECASE)
    
    @property
    def model(self) -> genai.GenerativeModel:
        """Lazy-load Gemini model for classification."""
        if self._model is None:
            self._model = genai.GenerativeModel(LLM_MODEL)
        return self._model
    
    def check_content(self, query: str) -> GuardrailResult:
        """
        Check user query for appropriateness.
        
        This is the main entry point for content moderation.
        Runs fast keyword check first, then LLM classification if needed.
        
        Args:
            query: User's question/message
            
        Returns:
            GuardrailResult indicating action to take
        """
        # Normalize query
        query_lower = query.lower().strip()
        
        # Empty or very short queries
        if len(query_lower) < 3:
            return GuardrailResult(
                action=ContentAction.REDIRECT,
                message="Please ask a question about the Seerah of Prophet Muhammad ﷺ.",
                reason="Query too short"
            )
        
        # Tier 1: Fast keyword-based blocking
        block_result = self._check_blocked_content(query_lower)
        if block_result:
            return block_result
        
        # Check for obvious relevance (fast path)
        if self._is_obviously_relevant(query_lower):
            return GuardrailResult(action=ContentAction.ALLOW)
        
        # Tier 2: LLM-based classification for edge cases
        return self._classify_with_llm(query)
    
    def _check_blocked_content(self, query_lower: str) -> Optional[GuardrailResult]:
        """
        Fast keyword-based check for offensive content.
        
        Args:
            query_lower: Lowercased query string
            
        Returns:
            GuardrailResult if blocked, None otherwise
        """
        if self._blocked_regex.search(query_lower):
            return GuardrailResult(
                action=ContentAction.BLOCK,
                message=self.BLOCK_MESSAGES[0],
                reason="Matched blocked pattern"
            )
        return None
    
    def _is_obviously_relevant(self, query_lower: str) -> bool:
        """
        Quick check if query is obviously about Seerah/Islam.
        
        Args:
            query_lower: Lowercased query string
            
        Returns:
            True if query contains relevant keywords
        """
        for keyword in self.RELEVANT_KEYWORDS:
            if keyword in query_lower:
                return True
        return False
    
    def _classify_with_llm(self, query: str) -> GuardrailResult:
        """
        Use LLM to classify ambiguous queries.
        
        Args:
            query: Original user query
            
        Returns:
            GuardrailResult based on LLM classification
        """
        classification_prompt = f"""You are a content moderator for an Islamic educational app about the Seerah (biography) of Prophet Muhammad ﷺ.

Classify the following user query into one of these categories:
1. RELEVANT - Related to Islamic history, Prophet Muhammad, his companions, early Islam, or the Seerah lecture series
2. OFF_TOPIC - Not related to Seerah/Islam but not offensive (e.g., asking about weather, sports, coding)
3. INAPPROPRIATE - Offensive, disrespectful, or harmful content

User query: "{query}"

Respond with ONLY one word: RELEVANT, OFF_TOPIC, or INAPPROPRIATE"""

        try:
            response = self.model.generate_content(
                classification_prompt,
                generation_config=genai.GenerationConfig(
                    temperature=0.1,  # Low temperature for consistent classification
                    max_output_tokens=20,
                )
            )
            
            classification = response.text.strip().upper()
            
            if 'INAPPROPRIATE' in classification:
                return GuardrailResult(
                    action=ContentAction.BLOCK,
                    message=self.BLOCK_MESSAGES[0],
                    reason="LLM classified as inappropriate"
                )
            elif 'OFF_TOPIC' in classification:
                return GuardrailResult(
                    action=ContentAction.REDIRECT,
                    message=self.REDIRECT_MESSAGE,
                    reason="LLM classified as off-topic"
                )
            else:
                # RELEVANT or any other response - allow it
                return GuardrailResult(action=ContentAction.ALLOW)
                
        except Exception as e:
            # If classification fails, allow the query (fail open for usability)
            # The RAG system will handle it appropriately
            return GuardrailResult(
                action=ContentAction.ALLOW,
                reason=f"Classification error: {e}"
            )


# Singleton instance
_guardrails = None


def get_guardrails() -> ContentGuardrails:
    """Get the singleton ContentGuardrails instance."""
    global _guardrails
    if _guardrails is None:
        _guardrails = ContentGuardrails()
    return _guardrails


def check_query(query: str) -> GuardrailResult:
    """
    Convenience function to check a query.
    
    Args:
        query: User's question
        
    Returns:
        GuardrailResult with action and optional message
    """
    return get_guardrails().check_content(query)
