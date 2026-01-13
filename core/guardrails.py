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
        # Profanity and slurs
        r'\b(fuck|shit|damn|ass|bitch|bastard|crap|hell)\b',
        r'\b(nigger|faggot|retard|spic|chink|kike)\b',
        # Hate speech indicators
        r'\b(kill\s+(all\s+)?(muslims?|jews?|christians?|hindus?))\b',
        r'\b(death\s+to)\b',
        r'\b(terrorist|terrorism)\s+(is\s+)?(good|great|awesome)\b',
        # Disrespectful content about Prophet or Islam
        r'\b(prophet\s+)?(muhammad|mohammed|pbuh)\s+(is\s+)?(fake|false|liar|pedophile|pedo|rapist|murderer|terrorist)\b',
        r'\b(islam\s+is\s+)?(evil|bad|wrong|violent|terrorist|fake|false)\b',
        r'\b(quran|qur\'?an|koran)\s+(is\s+)?(fake|false|wrong|evil)\b',
        r'\b(muslims?\s+are\s+)?(terrorists?|evil|bad|violent)\b',
        # Sexually explicit
        r'\b(porn|xxx|nude|naked|sex\s+with|sexual)\b',
        # Violence incitement
        r'\b(how\s+to\s+(kill|murder|bomb|attack|hurt|harm))\b',
        r'\b(make\s+(a\s+)?(bomb|weapon|explosive))\b',
        # Attempts to bypass filters (common variations)
        r'\b(f\*ck|f\*\*k|sh\*t|n\*\*\*er|f\*\*\*ot)\b',
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
        classification_prompt = f"""You are a strict content moderator for an Islamic educational app about the Seerah (biography) of Prophet Muhammad ﷺ.

Classify the following user query into one of these categories:

1. RELEVANT - Only if the query is genuinely related to:
   - Islamic history, Prophet Muhammad ﷺ, his companions, early Islam
   - The Seerah lecture series by Shaykh Yasir Qadhi
   - Questions about Islamic teachings, practices, or history in the context of the Seerah

2. OFF_TOPIC - If the query is:
   - Not related to Seerah/Islam but not offensive (e.g., weather, sports, coding, general knowledge)
   - Asking about topics completely unrelated to Islamic history or the Prophet's life

3. INAPPROPRIATE - If the query contains:
   - Disrespectful, offensive, or harmful content about Prophet Muhammad ﷺ, Islam, or Muslims
   - Profanity, hate speech, or discriminatory language
   - Attempts to mock, insult, or defame Islamic beliefs or figures
   - Sexually explicit content
   - Violence incitement
   - Any content that would be inappropriate for an Islamic educational platform

Be STRICT. When in doubt between RELEVANT and OFF_TOPIC, choose OFF_TOPIC. When in doubt between OFF_TOPIC and INAPPROPRIATE, choose INAPPROPRIATE.

User query: "{query}"

Respond with ONLY one word: RELEVANT, OFF_TOPIC, or INAPPROPRIATE"""

        try:
            response = self.model.generate_content(
                classification_prompt,
                generation_config=genai.GenerationConfig(
                    temperature=0.0,  # Zero temperature for maximum consistency
                    max_output_tokens=20,
                )
            )
            
            classification = response.text.strip().upper()
            
            # Be strict: check for inappropriate first, then off-topic
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
            elif 'RELEVANT' in classification:
                # Only allow if explicitly classified as RELEVANT
                return GuardrailResult(action=ContentAction.ALLOW)
            else:
                # Unknown classification - be conservative and redirect
                return GuardrailResult(
                    action=ContentAction.REDIRECT,
                    message=self.REDIRECT_MESSAGE,
                    reason=f"Unclear classification: {classification}"
                )
                
        except Exception as e:
            # If classification fails, be conservative and redirect (fail closed for safety)
            return GuardrailResult(
                action=ContentAction.REDIRECT,
                message=self.REDIRECT_MESSAGE,
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
