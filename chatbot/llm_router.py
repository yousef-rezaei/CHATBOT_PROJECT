"""
LLM Router - Decides which tier to use based on question + history
Enhanced with follow-up detection and context awareness
"""

import os
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

Analyze the question and conversation history to decide:

1. Is this a FOLLOW-UP question? (references previous conversation, asks for "more", "show all", etc.)
2. Which tier should handle it?

Tiers:
- Tier 0: FOLLOW-UP (use previous context/results)
- Tier 1: FAQ (platform questions, how-to guides)
- Tier 2: PDF Documents (technical documentation, methodologies)
- Tier 3: Chemical Database (searching/counting compounds, finding chemicals)
- Tier 4: AI Assistant (complex analysis, comparisons, explanations)

IMPORTANT: If question says "more", "show all", "expand", "continue", "tell me more", "all of them", etc. → Tier 0 (FOLLOW-UP)

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
            
            import json
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
        
        # Pattern 4: Reference to previous (pronouns)
        if question_lower in ['them', 'those', 'these', 'it', 'that']:
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