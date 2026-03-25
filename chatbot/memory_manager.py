from datetime import datetime
from typing import List, Dict, Optional


class ConversationMemory:
    """Manages conversation history with metadata support"""
    
    def __init__(self):
        self.conversations = {}  # session_id -> history
    
    def add_exchange(self, session_id: str, question: str, answer: str, 
                     tier: int, metadata: dict = None):
        
        if session_id not in self.conversations:
            self.conversations[session_id] = []
        
        exchange = {
            'question': question,
            'answer': answer,
            'tier': tier,
            'timestamp': datetime.now().isoformat(),
            'metadata': metadata or {}  # ✅ CRITICAL: Store metadata
        }
        
        self.conversations[session_id].append(exchange)
        
        # Keep only last 4
        self.conversations[session_id] = self.conversations[session_id][-4:]
    
    def get_history(self, session_id: str) -> List[Dict]:
        """Get conversation history"""
        return self.conversations.get(session_id, [])
    
    def get_last_exchange(self, session_id: str) -> Optional[Dict]:
        """
        Get most recent Q&A pair
        
        Returns:
            Last exchange dict or None if no history
        """
        history = self.get_history(session_id)
        return history[-1] if history else None
    
    def has_history(self, session_id: str) -> bool:
        """Check if session has any history"""
        return len(self.get_history(session_id)) > 0
    
    def format_for_llm(self, session_id: str) -> str:
        """
        Format last 4 Q&A for LLM (abbreviated)
        
        Returns:
            Formatted string with Q&A pairs
        """
        
        history = self.get_history(session_id)
        
        if not history:
            return ""
        
        formatted = []
        
        for i, exchange in enumerate(history, 1):
            # Abbreviate long answers to 150 chars
            answer = exchange['answer']
            if len(answer) > 150:
                answer = answer[:150] + "..."
            
            formatted.append(f"Q{i}: {exchange['question']}")
            formatted.append(f"A{i}: {answer}")
        
        return "\n".join(formatted)
    
    def clear_history(self, session_id: str):
        """Clear conversation history for session"""
        if session_id in self.conversations:
            del self.conversations[session_id]


# Global instance
_memory = None


def get_memory_manager():
    """Get or create memory manager singleton"""
    global _memory
    if _memory is None:
        _memory = ConversationMemory()
    return _memory