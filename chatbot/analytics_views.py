# ============================================================
# NEW FILE: chatbot/analytics_views.py
# ============================================================
#
# Action: CREATE this new file in chatbot/analytics_views.py
#
# These are the API endpoints to retrieve logged data
# ============================================================

from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.core.paginator import Paginator
from django.db.models import Count, Sum, Avg
from datetime import datetime, timedelta

from .models import ChatSession, ChatMessage, TierAttempt, RoutingLog, SystemLog


@require_http_methods(["GET"])
def list_sessions(request):
    """
    GET /api/analytics/sessions/
    
    Query params:
    - page: int (default 1)
    - per_page: int (default 20)
    - from_date: YYYY-MM-DD
    - to_date: YYYY-MM-DD
    
    Returns list of sessions with basic info
    """
    page = int(request.GET.get('page', 1))
    per_page = min(int(request.GET.get('per_page', 20)), 100)
    from_date = request.GET.get('from_date')
    to_date = request.GET.get('to_date')
    
    # Build query
    sessions = ChatSession.objects.all()
    
    if from_date:
        sessions = sessions.filter(started_at__gte=from_date)
    if to_date:
        sessions = sessions.filter(started_at__lte=to_date)
    
    # Paginate
    paginator = Paginator(sessions, per_page)
    page_obj = paginator.get_page(page)
    
    return JsonResponse({
        'total': paginator.count,
        'page': page,
        'per_page': per_page,
        'total_pages': paginator.num_pages,
        'sessions': [
            {
                'session_id': s.session_id,
                'user_ip': s.user_ip,
                'started_at': s.started_at.isoformat(),
                'last_activity': s.last_activity.isoformat(),
                'total_messages': s.total_messages,
                'total_cost': float(s.total_cost),
                'is_active': s.is_active
            }
            for s in page_obj
        ]
    })


@require_http_methods(["GET"])
def get_session_detail(request, session_id):
    """
    GET /api/analytics/sessions/<session_id>/
    
    Returns complete session with all messages and their logs
    """
    try:
        session = ChatSession.objects.get(session_id=session_id)
    except ChatSession.DoesNotExist:
        return JsonResponse({'error': 'Session not found'}, status=404)
    
    messages = ChatMessage.objects.filter(session=session).prefetch_related(
        'tier_attempts', 'routing_logs', 'system_logs'
    )
    
    return JsonResponse({
        'session': {
            'session_id': session.session_id,
            'user_ip': session.user_ip,
            'user_agent': session.user_agent,
            'started_at': session.started_at.isoformat(),
            'last_activity': session.last_activity.isoformat(),
            'total_messages': session.total_messages,
            'total_cost': float(session.total_cost),
            'is_active': session.is_active
        },
        'messages': [
            {
                'id': msg.id,
                'type': msg.message_type,
                'content': msg.content,
                'timestamp': msg.timestamp.isoformat(),
                
                # User message fields
                'is_faq_button': msg.is_faq_button if msg.message_type == 'user' else None,
                'skip_tier': msg.skip_tier if msg.message_type == 'user' else None,
                
                # Bot message fields
                'tier': msg.tier,
                'tier_name': msg.tier_name,
                'response_type': msg.response_type,
                'similarity_score': msg.similarity_score,
                'result_count': msg.result_count,
                'response_time_ms': msg.response_time_ms,
                'cost': float(msg.cost) if msg.cost else None,
                
                # Feedback
                'helpful': msg.helpful,
                'feedback_timestamp': msg.feedback_timestamp.isoformat() if msg.feedback_timestamp else None,
                
                # Related logs
                'routing_logs': [
                    {
                        'routing_type': rl.routing_type,
                        'recommended_tier': rl.recommended_tier,
                        'is_followup': rl.is_followup,
                        'reasoning': rl.reasoning,
                        'override_applied': rl.override_applied,
                        'override_keywords': rl.override_keywords,
                        'history_length': rl.history_length
                    }
                    for rl in msg.routing_logs.all()
                ],
                
                'tier_attempts': [
                    {
                        'tier': ta.tier,
                        'status': ta.status,
                        'duration_ms': ta.duration_ms,
                        'similarity': ta.similarity,
                        'result_count': ta.result_count,
                        'sql_query': ta.sql_query,
                        'main_term': ta.main_term,
                        'synonyms': ta.synonyms,
                        'total_cost': float(ta.total_cost) if ta.total_cost else None
                    }
                    for ta in msg.tier_attempts.all()
                ],
                
                'system_logs': [
                    {
                        'log_type': sl.log_type,
                        'timestamp': sl.timestamp.isoformat(),
                        'description': sl.description,
                        'details': sl.details
                    }
                    for sl in msg.system_logs.all()
                ]
            }
            for msg in messages
        ]
    })


@require_http_methods(["GET"])
def get_message_console_logs(request, message_id):
    """
    GET /api/analytics/messages/<message_id>/console/
    
    Returns console-style logs for a specific message
    (recreates the console output you see in terminal)
    """
    try:
        message = ChatMessage.objects.prefetch_related(
            'routing_logs', 'tier_attempts', 'system_logs'
        ).get(id=message_id)
    except ChatMessage.DoesNotExist:
        return JsonResponse({'error': 'Message not found'}, status=404)
    
    # Get the user message before this bot message
    user_message = ChatMessage.objects.filter(
        session=message.session,
        message_type='user',
        timestamp__lt=message.timestamp
    ).order_by('-timestamp').first()
    
    # Build console-style output
    console_lines = []
    console_lines.append("=" * 60)
    
    if user_message:
        console_lines.append(f"📨 Query: '{user_message.content[:50]}...'")
        
        # Get routing log
        routing_log = user_message.routing_logs.first()
        if routing_log:
            console_lines.append(f"💭 History: {routing_log.history_length} exchanges")
            console_lines.append(f"🔘 FAQ Button: {user_message.is_faq_button}")
            console_lines.append(f"👎 Skip Tier: {user_message.skip_tier}")
            console_lines.append("=" * 60)
            
            # Routing decision
            if routing_log.routing_type == 'first_question':
                console_lines.append("🆕 First question → Sequential tiers (no LLM router)")
            elif routing_log.routing_type == 'llm_router':
                console_lines.append("🧠 Has history → Using LLM router...")
                console_lines.append(f"🧭 LLM Router: Tier {routing_log.recommended_tier} (Follow-up: {routing_log.is_followup})")
                if routing_log.reasoning:
                    console_lines.append(f"   Reasoning: {routing_log.reasoning}")
            elif routing_log.routing_type == 'faq_button':
                console_lines.append("🔘 FAQ button clicked → Direct to FAQ")
            
            # Override
            if routing_log.override_applied:
                console_lines.append("🎯 OVERRIDE: Explicit database search intent detected!")
                console_lines.append(f"   Keywords found: {routing_log.override_keywords}")
                console_lines.append(f"   ✅ Forcing Tier {routing_log.recommended_tier} (SQL)")
    
    console_lines.append("=" * 60)
    
    # Tier attempts
    for attempt in message.tier_attempts.all():
        tier_name = dict(TierAttempt.TIER_CHOICES).get(attempt.tier, f"Tier {attempt.tier}")
        console_lines.append(f"🗄️ Trying TIER {attempt.tier}: {tier_name}...")
        
        # SQL specific logs
        if attempt.tier == 3 and attempt.sql_query:
            console_lines.append("=" * 60)
            console_lines.append(f"🤖 Smart SQL Agent Query: {user_message.content if user_message else ''}")
            console_lines.append("=" * 60)
            console_lines.append("📊 SQL Relevance: ✅ YES" if attempt.status == 'success' else "📊 SQL Relevance: ❌ NO")
            if attempt.main_term:
                console_lines.append(f"🎯 Main term: {attempt.main_term}")
            if attempt.synonyms:
                console_lines.append(f"🔄 Synonyms: {attempt.synonyms}")
            if attempt.result_count:
                console_lines.append(f"✅ Found {attempt.result_count} results")
        
        # Result
        if attempt.status == 'success':
            console_lines.append(f"✅ TIER {attempt.tier} ({tier_name}): {attempt.result_count or 'Answer'} found")
        elif attempt.status == 'not_found':
            console_lines.append(f"⏭️ TIER {attempt.tier} ({tier_name}): No match")
        elif attempt.status == 'error':
            console_lines.append(f"❌ TIER {attempt.tier} ({tier_name}): Error")
        
        if attempt.duration_ms:
            console_lines.append(f"⏱️  Duration: {attempt.duration_ms}ms")
        if attempt.total_cost:
            console_lines.append(f"💰 Cost: ${float(attempt.total_cost):.6f}")
    
    console_lines.append("=" * 60)
    
    return JsonResponse({
        'message_id': message_id,
        'console_output': '\n'.join(console_lines),
        'console_lines': console_lines
    })


@require_http_methods(["GET"])
def get_stats(request):
    """
    GET /api/analytics/stats/
    
    Returns overall statistics
    """
    
    # Session stats
    total_sessions = ChatSession.objects.count()
    active_sessions = ChatSession.objects.filter(is_active=True).count()
    
    # Message stats
    message_stats = ChatMessage.objects.filter(message_type='bot').aggregate(
        total=Count('id'),
        avg_response_time=Avg('response_time_ms'),
        total_cost=Sum('cost')
    )
    
    # Tier distribution
    tier_distribution = {}
    tier_counts = ChatMessage.objects.filter(
        message_type='bot'
    ).values('tier').annotate(count=Count('id'))
    
    for item in tier_counts:
        if item['tier'] is not None:
            tier_distribution[f"tier_{item['tier']}"] = item['count']
    
    # Response type distribution
    response_type_counts = ChatMessage.objects.filter(
        message_type='bot'
    ).values('response_type').annotate(count=Count('id')).order_by('-count')
    
    response_type_distribution = {
        item['response_type']: item['count']
        for item in response_type_counts
        if item['response_type']
    }
    
    # Feedback stats - FIXED
    helpful_count = ChatMessage.objects.filter(
        message_type='bot',
        helpful=True
    ).count()
    
    not_helpful_count = ChatMessage.objects.filter(
        message_type='bot',
        helpful=False
    ).count()
    
    total_feedback = helpful_count + not_helpful_count
    
    feedback_stats = {
        'total_feedback': total_feedback,
        'helpful': helpful_count,
        'not_helpful': not_helpful_count
    }
    
    satisfaction_rate = 0
    if feedback_stats['total_feedback'] > 0:
        satisfaction_rate = (feedback_stats['helpful'] / feedback_stats['total_feedback'] * 100)
    
    # Recent activity (last 24 hours)
    last_24h = datetime.now() - timedelta(hours=24)
    recent_activity = {
        'sessions': ChatSession.objects.filter(started_at__gte=last_24h).count(),
        'messages': ChatMessage.objects.filter(timestamp__gte=last_24h, message_type='user').count()
    }
    
    return JsonResponse({
        'sessions': {
            'total': total_sessions,
            'active': active_sessions
        },
        'messages': {
            'total': message_stats['total'],
            'avg_response_time_ms': int(message_stats['avg_response_time'] or 0),
            'total_cost': float(message_stats['total_cost'] or 0)
        },
        'tier_distribution': tier_distribution,
        'response_type_distribution': response_type_distribution,
        'feedback': {
            'total': feedback_stats['total_feedback'],
            'helpful': feedback_stats['helpful'],
            'not_helpful': feedback_stats['not_helpful'],
            'satisfaction_rate': round(satisfaction_rate, 2)
        },
        'recent_activity_24h': recent_activity
    })


@require_http_methods(["GET"])
def search_logs(request):
    """
    GET /api/analytics/search/
    
    Query params:
    - q: search query
    - tier: filter by tier (0-4)
    - status: filter by status (success, not_found, error)
    - from_date: YYYY-MM-DD
    - to_date: YYYY-MM-DD
    
    Search through messages and return matching results
    """
    query = request.GET.get('q', '')
    tier = request.GET.get('tier')
    status = request.GET.get('status')
    from_date = request.GET.get('from_date')
    to_date = request.GET.get('to_date')
    
    messages = ChatMessage.objects.filter(message_type='bot')
    
    if query:
        # Search in user messages
        user_messages = ChatMessage.objects.filter(
            message_type='user',
            content__icontains=query
        ).values_list('session_id', flat=True)
        
        messages = messages.filter(session__in=user_messages)
    
    if tier is not None:
        messages = messages.filter(tier=int(tier))
    
    if from_date:
        messages = messages.filter(timestamp__gte=from_date)
    
    if to_date:
        messages = messages.filter(timestamp__lte=to_date)
    
    # Get tier attempts if status filter
    if status:
        message_ids = TierAttempt.objects.filter(
            status=status
        ).values_list('message_id', flat=True)
        messages = messages.filter(id__in=message_ids)
    
    messages = messages.order_by('-timestamp')[:50]
    
    results = []
    for msg in messages:
        user_msg = ChatMessage.objects.filter(
            session=msg.session,
            message_type='user',
            timestamp__lt=msg.timestamp
        ).order_by('-timestamp').first()
        
        results.append({
            'message_id': msg.id,
            'session_id': msg.session.session_id,
            'timestamp': msg.timestamp.isoformat(),
            'user_query': user_msg.content if user_msg else None,
            'tier': msg.tier,
            'tier_name': msg.tier_name,
            'response_type': msg.response_type,
            'cost': float(msg.cost) if msg.cost else None
        })
    
    return JsonResponse({
        'total': len(results),
        'results': results
    })


# Import models for Q objects
from django.db import models