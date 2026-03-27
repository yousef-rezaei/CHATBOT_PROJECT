import os
import json
from openai import OpenAI

class LLMRouter:
    """Routes questions to appropriate tier using LLM with follow-up detection"""
    
    def __init__(self):
        self.client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))
    
    def route(self, question: str, history_context: str) -> dict:
        """
        Decide which tier to use and detect follow-ups
        
        Args:
            question: Current user question
            history_context: Last 4 Q&A formatted
            
        Returns:
            dict with:
                - tier: int (0=followup, 1=FAQ, 2=RAG, 3=SQL, 4=LLM)
                - is_followup: bool
                - reasoning: str
        """
        
        # ============================================
        # STEP 1: Quick pattern-based follow-up detection (FREE!)
        # ============================================
        followup_check = self._quick_followup_check(question)
        if followup_check['is_followup']:
            print(f"🔄 Quick follow-up detected: {followup_check['reasoning']}")
            return followup_check
        


        # ============================================
        # STEP 1.5: Check topic similarity
        # ============================================
        if history_context:
            # Extract last question from history
            history_lines = history_context.split('\n')
            last_q = None
            for line in reversed(history_lines):
                if line.startswith('Q'):
                    last_q = line.split(':', 1)[1].strip() if ':' in line else None
                    break
            
            if last_q:
                is_similar = self._check_topic_similarity(question, last_q)
                if not is_similar:
                    print(f"🔄 New topic detected (not similar to: '{last_q[:30]}...')")
                    # Treat as new question, don't consider history heavily



        # ============================================
        # STEP 2: Use LLM for complex routing
        # ============================================
        try:
            prompt = self._build_routing_prompt(question, history_context)
            
            response = self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {
                        "role": "system",
                        "content": """You are a routing assistant for a chemical database chatbot.

Analyze if the NEW question is truly a follow-up or a COMPLETELY NEW TOPIC.

⚠️ CRITICAL: Most questions are NEW topics, not follow-ups!

A question is ONLY a follow-up if it:
- Uses pronouns referring to previous answer ("them", "those", "it")
- Asks for expansion ("more details", "show all", "continue")
- Clarifies previous question ("I meant X", "specifically Y")
- References specific results ("the first one", "number 3")

A question is NOT a follow-up if it:
- Introduces new chemical names or topics
- Asks "what is X" or "tell me about Y"
- Changes the subject entirely
- Is a complete, standalone question

Examples:
- "What is PFAS?" → NEW question (Tier 4)
- "Tell me about pesticides" → NEW question (Tier 3)
- "Show all" → Follow-up (Tier 0)
- "What about the first result?" → Follow-up (Tier 0)

Tiers:
- Tier 0: FOLLOW-UP (only if explicitly continuing previous answer)
- Tier 1: FAQ (platform/website questions)
- Tier 2: PDF Documents (technical documentation)
- Tier 3: Chemical Database (search/count compounds)
- Tier 4: AI Assistant (explanations, definitions, comparisons)

Respond with JSON:
{
  "tier": 0-4,
  "is_followup": true/false,
  "reasoning": "brief explanation"
}"""
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                response_format={"type": "json_object"},
                temperature=0.2,
                max_tokens=100
            )
            
            
            result = json.loads(response.choices[0].message.content)
            
            tier = result.get('tier', 1)
            is_followup = result.get('is_followup', False)
            reasoning = result.get('reasoning', 'LLM routing')
            
            # Validate tier
            if tier not in [0, 1, 2, 3, 4]:
                tier = 1
            
            print(f"🧭 LLM Router: Tier {tier} (Follow-up: {is_followup})")
            print(f"   Reasoning: {reasoning}")
            
            return {
                'tier': tier,
                'is_followup': is_followup,
                'reasoning': reasoning
            }
            
        except Exception as e:
            print(f"⚠️ Router error: {e}, defaulting to Tier 1")
            return {
                'tier': 1,
                'is_followup': False,
                'reasoning': 'Error fallback'
            }
    
    def _quick_followup_check(self, question: str) -> dict:
        """
        Quick pattern-based follow-up detection (no LLM call)
        
        Returns dict or None
        """
        
        question_lower = question.lower().strip()
        
        # Pattern 1: Explicit "more" requests
        more_patterns = [
            'i want more',
            'show more',
            'give me more',
            'tell me more',
            'more info',
            'more details',
            'more about',
            'need more'
        ]
        
        for pattern in more_patterns:
            if pattern in question_lower:
                return {
                    'tier': 0,
                    'is_followup': True,
                    'reasoning': f'Follow-up phrase: "{pattern}"'
                }
        
        # Pattern 2: "Show all" / "List all" requests
        show_all_patterns = [
            'show all',
            'list all',
            'display all',
            'all of them',
            'all results',
            'complete list',
            'full list'
        ]
        
        for pattern in show_all_patterns:
            if pattern in question_lower:
                return {
                    'tier': 0,
                    'is_followup': True,
                    'reasoning': f'Show all request: "{pattern}"'
                }
        
        # Pattern 3: Clarification phrases
        clarification_patterns = [
            'i mean',
            'i meant',
            'what i meant',
            'to clarify',
            'specifically',
            'i was asking'
        ]
        
        for pattern in clarification_patterns:
            if question_lower.startswith(pattern):
                return {
                    'tier': 0,
                    'is_followup': True,
                    'reasoning': f'Clarification: "{pattern}"'
                }
        
        # Pattern 4: Reference to previous (ONLY standalone pronouns)
        # Don't trigger for "What is it?" or "Tell me about that"
        if question_lower in ['them', 'those', 'these'] and len(question.split()) <= 2:
            return {
                'tier': 0,
                'is_followup': True,
                'reasoning': 'Pronoun reference to previous'
            }
        
        # Pattern 5: Numbered reference
        if question_lower.startswith(('the first', 'the second', 'the last', 'number ')):
            return {
                'tier': 0,
                'is_followup': True,
                'reasoning': 'Reference to specific result'
            }
        
        # Pattern 6: "Expand" / "Continue"
        action_patterns = ['expand', 'continue', 'go on', 'keep going']
        if any(pattern == question_lower for pattern in action_patterns):
            return {
                'tier': 0,
                'is_followup': True,
                'reasoning': f'Action word: "{question_lower}"'
            }
        
        # Not a follow-up
        return {
            'tier': None,
            'is_followup': False,
            'reasoning': None
        }
    

    def _check_topic_similarity(self, new_question: str, last_question: str) -> bool:
        """
        Check if new question is semantically similar to last question
        
        Returns:
            True if similar (potential follow-up), False if different topic
        """
        
        # Simple keyword-based similarity check
        new_words = set(new_question.lower().split())
        last_words = set(last_question.lower().split())
        
        # Remove common words
        stop_words = {'the', 'a', 'an', 'is', 'are', 'what', 'how', 'many', 'do', 'we', 'have', 'tell', 'me', 'about'}
        new_words -= stop_words
        last_words -= stop_words
        
        # Calculate overlap
        overlap = new_words & last_words
        
        # If less than 30% overlap, it's a new topic
        if len(new_words) == 0:
            return True  # Short question, assume related
        
        similarity = len(overlap) / len(new_words)
        
        return similarity > 0.3  # 30% threshold

    def _build_routing_prompt(self, question: str, history: str) -> str:
        """Build routing prompt with context"""
        
        if history:
            return f"""Previous conversation:
{history}

New question: {question}

Analyze if this is a follow-up to the previous conversation or a new question.
Then decide which tier should handle it."""
        else:
            return f"""Question: {question}

This is the first question (no history).
Decide which tier should handle it."""


# Global instance
_router = None

def get_llm_router():
    """Get or create LLM router singleton"""
    global _router
    if _router is None:
        _router = LLMRouter()
    return _router