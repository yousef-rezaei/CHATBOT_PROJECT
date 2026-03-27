# ============================================================
# FIXED: chatbot/logger.py
# ============================================================
# Replace your existing chatbot/logger.py with this version
# Fixes: Timezone warnings by using timezone.now() instead of datetime.now()
# ============================================================

import time
from datetime import datetime
from decimal import Decimal
from typing import Optional, Dict, List, Any
from django.utils import timezone  # ← CHANGED: Use Django's timezone
from .models import ChatSession, ChatMessage, RoutingLog, TierAttempt, SystemLog


class ChatbotLogger:
    """
    Captures and stores all chatbot logs
    
    Usage in views.py:
        logger = ChatbotLogger(session_id)
        logger.log_query(user_message, history_length, is_faq_button, skip_tier)
        logger.log_routing('first_question', tier=1)
        logger.start_tier(1, 'FAQ')
        # ... tier processing ...
        logger.complete_tier(1, 'success', similarity=0.85, result_count=1)
        logger.save(user_message, bot_response)
    """
    
    def __init__(self, session_id: str, user_ip: str = None, user_agent: str = None):
        self.session_id = session_id
        self.user_ip = user_ip
        self.user_agent = user_agent
        self.start_time = time.time()
        
        # Query context
        self.user_message = None
        self.history_length = 0
        self.is_faq_button = False
        self.skip_tier = 0
        
        # Routing info
        self.routing_type = None
        self.recommended_tier = None
        self.is_followup = False
        self.routing_reasoning = None
        self.override_applied = False
        self.override_keywords = []
        
        # Tier tracking
        self.tier_starts = {}  # {tier: start_time}
        self.tier_attempts = []  # List of tier attempt data
        
        # Final result
        self.final_tier = None
        self.final_tier_name = None
        self.final_response_type = None
        self.final_cost = 0
        self.final_similarity = None
        self.final_result_count = None
        
        # All logs
        self.logs = []
    
    def log_query(self, message: str, history_length: int, is_faq_button: bool, skip_tier: int):
        """Log incoming query"""
        self.user_message = message
        self.history_length = history_length
        self.is_faq_button = is_faq_button
        self.skip_tier = skip_tier
        
        self._add_log('info', 'Query received', {
            'message': message[:100],
            'history_length': history_length,
            'is_faq_button': is_faq_button,
            'skip_tier': skip_tier
        })
    
    def log_routing(self, routing_type: str, tier: int = None, 
                   is_followup: bool = False, reasoning: str = None):
        """Log routing decision"""
        self.routing_type = routing_type
        self.recommended_tier = tier
        self.is_followup = is_followup
        self.routing_reasoning = reasoning
        
        self._add_log('routing', f'{routing_type} → Tier {tier}', {
            'routing_type': routing_type,
            'recommended_tier': tier,
            'is_followup': is_followup,
            'reasoning': reasoning
        })
    
    def log_override(self, keywords: List[str], forced_tier: int):
        """Log database intent override"""
        self.override_applied = True
        self.override_keywords = keywords
        self.recommended_tier = forced_tier
        
        self._add_log('override', f'Database override → Tier {forced_tier}', {
            'keywords': keywords,
            'forced_tier': forced_tier
        })
    
    def log_followup(self, detection_type: str, details: str):
        """Log follow-up detection"""
        self._add_log('followup', detection_type, {
            'detection_type': detection_type,
            'details': details
        })
    
    def start_tier(self, tier: int, tier_name: str):
        """Start timing a tier attempt"""
        self.tier_starts[tier] = time.time()
        
        self._add_log('tier_attempt', f'Starting Tier {tier}: {tier_name}', {
            'tier': tier,
            'tier_name': tier_name,
            'status': 'started'
        })
    
    def complete_tier(self, tier: int, status: str, 
                     similarity: float = None, result_count: int = None,
                     sql_query: str = None, main_term: str = None,
                     synonyms: List[str] = None, cost: float = None,
                     tier_name: str = None, response_type: str = None):
        """Complete a tier attempt"""
        
        # Calculate duration
        duration_ms = None
        if tier in self.tier_starts:
            duration_ms = int((time.time() - self.tier_starts[tier]) * 1000)
        
        # Store tier attempt
        self.tier_attempts.append({
            'tier': tier,
            'status': status,
            'duration_ms': duration_ms,
            'similarity': similarity,
            'result_count': result_count,
            'sql_query': sql_query,
            'main_term': main_term,
            'synonyms': synonyms,
            'total_cost': cost
        })
        
        # If success, update final result
        if status == 'success':
            self.final_tier = tier
            self.final_tier_name = tier_name
            self.final_response_type = response_type
            self.final_similarity = similarity
            self.final_result_count = result_count
            if cost:
                self.final_cost += cost
        
        self._add_log('tier_attempt', f'Tier {tier} completed: {status}', {
            'tier': tier,
            'status': status,
            'duration_ms': duration_ms,
            'similarity': similarity,
            'result_count': result_count,
            'cost': cost
        })
    
    def log_error(self, tier: int, error_message: str, details: Dict = None):
        """Log an error"""
        self._add_log('error', f'Tier {tier} error: {error_message}', {
            'tier': tier,
            'error': error_message,
            'details': details or {}
        })
    
    def _add_log(self, log_type: str, description: str, details: Dict):
        """Internal: Add a log entry"""
        self.logs.append({
            'log_type': log_type,
            'timestamp': timezone.now(),  # ← FIXED: Use timezone.now()
            'description': description,
            'details': details
        })
    
    def save(self, user_message: str, bot_response: str) -> int:
        """
        Save all logs to database
        
        Returns:
            bot_message_id: ID of the bot message
        """
        
        # Calculate total response time
        response_time_ms = int((time.time() - self.start_time) * 1000)
        
        # Get or create session
        session, created = ChatSession.objects.get_or_create(
            session_id=self.session_id,
            defaults={
                'user_ip': self.user_ip,
                'user_agent': self.user_agent,
                'is_active': True
            }
        )
        
        # Save user message
        user_msg = ChatMessage.objects.create(
            session=session,
            message_type='user',
            content=user_message,
            is_faq_button=self.is_faq_button,
            skip_tier=self.skip_tier
        )
        
        # Save bot response
        bot_msg = ChatMessage.objects.create(
            session=session,
            message_type='bot',
            content=bot_response,
            tier=self.final_tier,
            tier_name=self.final_tier_name,
            response_type=self.final_response_type,
            response_time_ms=response_time_ms,
            cost=Decimal(str(self.final_cost)) if self.final_cost else None,
            similarity_score=self.final_similarity,
            result_count=self.final_result_count
        )
        
        # Save routing log
        if self.routing_type:
            RoutingLog.objects.create(
                message=user_msg,
                routing_type=self.routing_type,
                recommended_tier=self.recommended_tier,
                is_followup=self.is_followup,
                reasoning=self.routing_reasoning,
                override_applied=self.override_applied,
                override_keywords=self.override_keywords,
                history_length=self.history_length
            )
        
        # Save tier attempts
        for attempt in self.tier_attempts:
            TierAttempt.objects.create(
                message=bot_msg,
                tier=attempt['tier'],
                status=attempt['status'],
                duration_ms=attempt.get('duration_ms'),
                similarity=attempt.get('similarity'),
                result_count=attempt.get('result_count'),
                sql_query=attempt.get('sql_query'),
                main_term=attempt.get('main_term'),
                synonyms=attempt.get('synonyms'),
                total_cost=Decimal(str(attempt['total_cost'])) if attempt.get('total_cost') else None
            )
        
        # Save system logs
        for log in self.logs:
            SystemLog.objects.create(
                message=bot_msg,
                log_type=log['log_type'],
                timestamp=log['timestamp'],  # Already timezone-aware
                description=log['description'],
                details=log['details']
            )
        
        # Update session stats
        session.total_messages += 2  # user + bot
        if self.final_cost:
            session.total_cost += Decimal(str(self.final_cost))
        session.save()
        
        return bot_msg.id
    
    def print_console_summary(self):
        """Print a summary to console (keeps existing console output)"""
        response_time_ms = int((time.time() - self.start_time) * 1000)
        print(f"✅ Logged: Tier {self.final_tier} | {self.final_response_type} | {response_time_ms}ms | ${self.final_cost:.6f}")