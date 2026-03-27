from django.shortcuts import render
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import ensure_csrf_cookie
from datetime import datetime
import json
import os
import time
from .faq_handler import get_faq_handler
from .rag.pdf_rag_handler import get_pdf_rag_handler 
from .sql.sql_agent import get_sql_agent
from .memory_manager import get_memory_manager  
from .llm_router import get_llm_router
from .logger import ChatbotLogger  # ← NEW: Import logger

# FAQ CSV path
FAQ_CSV_PATH = os.path.join(os.path.dirname(__file__), 'faq', 'data', 'chatbot_faq.csv')


@ensure_csrf_cookie
def home(request):
    """Render the home page with chatbot widget"""
    return render(request, 'chatbot/index.html', {})
@ensure_csrf_cookie
def analytics_dashboard(request):
    """Render the analytics dashboard"""
    return render(request, 'chatbot/analytics_dashboard.html', {})

@require_http_methods(["GET", "POST"])
def chatbot_api(request):
    """
    Main chatbot API with conversation memory and smart routing
    
    Routing logic:
    1. First question → Sequential tiers (FAQ→RAG→SQL→LLM) - NO LLM router
    2. FAQ button click → Direct to FAQ - NO LLM router
    3. Has history → LLM router decides tier (including follow-up detection)
    4. Negative feedback → Continue from next tier
    5. Follow-up detected → Retrieve from memory
    6. Explicit database intent → Override and force SQL tier
    """
    
    if request.method == "GET":
        action = request.GET.get('action', '')
        if action == 'get_categories':
            return get_categories_api()
        return JsonResponse({'error': 'Invalid action'}, status=400)
    
    # POST - Handle user questions
    request_start = time.time()
    faq_time = 0
    tier_attempts = []
    
    # ============================================================
    # NEW: Initialize logger
    # ============================================================
    user_ip = request.META.get('REMOTE_ADDR')
    user_agent = request.META.get('HTTP_USER_AGENT', '')
    logger = None
    
    try:
        # ============================================================
        # PARSE REQUEST
        # ============================================================
        data = json.loads(request.body)
        user_message = data.get('message', '').strip()
        skip_tier = data.get('skip_tier', 0)
        is_faq_button = data.get('is_faq_button', False)
        
        # Validate
        if not user_message:
            return JsonResponse({'error': 'Message cannot be empty'}, status=400)
        
        if len(user_message) > 1000:
            return JsonResponse({'error': 'Message too long'}, status=400)
        
        # ============================================================
        # SETUP SESSION & MEMORY
        # ============================================================
        if not request.session.session_key:
            request.session.create()
        session_id = request.session.session_key
        
        # ============================================================
        # NEW: Create logger with session
        # ============================================================
        logger = ChatbotLogger(session_id, user_ip, user_agent)
        
        memory = get_memory_manager()
        has_history = memory.has_history(session_id)
        
        print(f"\n{'='*60}")
        print(f"📨 Query: '{user_message[:50]}...'")
        print(f"💭 History: {len(memory.get_history(session_id))} exchanges")
        print(f"🔘 FAQ Button: {is_faq_button}")
        print(f"👎 Skip Tier: {skip_tier}")
        print(f"{'='*60}")
        
        # ============================================================
        # NEW: Log query
        # ============================================================
        logger.log_query(user_message, len(memory.get_history(session_id)), is_faq_button, skip_tier)
        
        # ============================================================
        # ROUTING DECISION
        # ============================================================
        start_tier = 1  # Default: start from FAQ
        routing = None
        
        if skip_tier > 0:
            # ✅ CASE 1: Negative feedback - continue from next tier
            start_tier = skip_tier + 1
            print(f"👎 Negative feedback → Starting from Tier {start_tier} (sequential)")
            
            # NEW: Log routing
            logger.log_routing('negative_feedback', tier=start_tier)
            
        elif is_faq_button:
            # ✅ CASE 2: FAQ button clicked - go directly to FAQ (no LLM)
            start_tier = 1
            print(f"🔘 FAQ button → Direct to FAQ Tier 1 (no LLM router)")
            
            # NEW: Log routing
            logger.log_routing('faq_button', tier=1, is_followup=False)
            
        elif not has_history:
            # ✅ CASE 3: First question - use sequential tiers (no LLM)
            start_tier = 1
            print(f"🆕 First question → Sequential tiers (no LLM router)")
            
            # NEW: Log routing
            logger.log_routing('first_question', tier=1, is_followup=False)
            
        else:
            # ✅ CASE 4: Has history - use LLM router
            print(f"🧠 Has history → Using LLM router...")
            
            try:
                router = get_llm_router()
                history_context = memory.format_for_llm(session_id)
                
                routing = router.route(user_message, history_context)
                
                # Check if follow-up
                if routing.get('is_followup'):
                    print(f"🔄 Follow-up detected: {routing.get('reasoning')}")
                    start_tier = 0  # Special marker for follow-up
                    
                    # NEW: Log follow-up
                    logger.log_followup('llm_router_detected', routing.get('reasoning', ''))
                    logger.log_routing('llm_router', tier=0, is_followup=True, reasoning=routing.get('reasoning'))
                else:
                    start_tier = routing.get('tier', 1)
                    print(f"✅ LLM router recommended: Tier {start_tier}")
                    
                    # NEW: Log routing
                    logger.log_routing('llm_router', tier=start_tier, is_followup=False, reasoning=routing.get('reasoning'))
                
            except Exception as e:
                print(f"⚠️ LLM router error: {e}, defaulting to Tier 1")
                start_tier = 1
                
                # NEW: Log error
                if logger:
                    logger.log_error(0, f"LLM router error: {str(e)}")
        
        # ============================================================
        # 🎯 EXPLICIT DATABASE INTENT OVERRIDE (FIXED!)
        # ============================================================
        database_keywords = [
            'search in database', 'search database', 'query database',
            'find in database', 'database search', 'in the database',
            'how many', 'count', 'list all', 'give me all',
            'find all', 'search for', 'find compounds', 'find chemicals',
            'how many exist', 'do we have', 'are there', 'you can search',
            'search it', 'look it up', 'check database'
        ]
        
        # "show all" keywords - separate handling for follow-ups
        followup_keywords = ['show all', 'display all', 'list them all', 'all of them', 'show them all']
        
        user_lower = user_message.lower()
        
        # Check for explicit database intent (excluding follow-up keywords)
        explicit_database_intent = any(keyword in user_lower for keyword in database_keywords)
        
        # Check for "show all" style keywords
        is_followup_style = any(keyword in user_lower for keyword in followup_keywords)
        
        # ✅ FIX: Only override if NOT a follow-up (start_tier != 0)
        if explicit_database_intent and start_tier != 0:
            print(f"🎯 OVERRIDE: Explicit database search intent detected!")
            matched_keywords = [k for k in database_keywords if k in user_lower]
            print(f"   Keywords found: {matched_keywords}")
            print(f"   ✅ Forcing Tier 3 (SQL) for database search")
            start_tier = 3  # Force SQL tier
            
            # NEW: Log override
            logger.log_override(matched_keywords, forced_tier=3)
            
        elif is_followup_style and start_tier != 0:
            # "show all" detected but NOT a follow-up by LLM router
            # This means it's a new query, so force SQL
            print(f"🎯 OVERRIDE: 'Show all' style query detected (not a follow-up)")
            print(f"   ✅ Forcing Tier 3 (SQL) for database search")
            start_tier = 3
            
            # NEW: Log override
            logger.log_override(followup_keywords, forced_tier=3)
        
        # If start_tier == 0 (follow-up), do NOT override - let it proceed to follow-up handler
        
        # ============================================================
        # HANDLE FOLLOW-UP QUESTIONS (only if NOT overridden)
        # ============================================================
        if start_tier == 0:  # Follow-up detected and NOT overridden
            print(f"🔄 Processing follow-up request...")
            
            # NEW: Log follow-up processing
            logger.log_followup('processing', 'Retrieving from memory')
            
            last_exchange = memory.get_last_exchange(session_id)
            
            if last_exchange:
                last_tier = last_exchange.get('tier')
                metadata = last_exchange.get('metadata', {})
                
                print(f"   Last tier: {last_tier}")
                print(f"   Has metadata: {bool(metadata)}")
                
                # CASE 1: Follow-up to SQL results
                if last_tier == 3 and 'results' in metadata:
                    print(f"   ✅ Retrieving SQL results from memory")
                    
                    # NEW: Start and complete tier 0
                    logger.start_tier(0, 'Follow-up')
                    
                    results = metadata['results']
                    main_term = metadata.get('main_term', 'compounds')
                    synonyms = metadata.get('synonyms', [])
                    
                    # Format ALL stored results
                    answer = format_all_sql_results(results, main_term, synonyms)
                    
                    # NEW: Complete tier
                    logger.complete_tier(
                        tier=0,
                        status='success',
                        result_count=len(results),
                        tier_name='Follow-up',
                        response_type='followup_sql'
                    )
                    
                    # Store this follow-up in memory
                    memory.add_exchange(
                        session_id,
                        user_message,
                        answer,
                        tier=3,
                        metadata={'type': 'followup', 'parent_tier': 3}
                    )
                    
                    total_time = time.time() - request_start
                    
                    # NEW: Save to database
                    if logger:
                        bot_message_id = logger.save(user_message, answer)
                        print(f"💾 Saved to database (message_id: {bot_message_id})")
                    
                    return JsonResponse({
                        'response': answer,
                        'type': 'followup_sql',
                        'tier': 3,
                        'tier_name': 'Chemical Database (Follow-up)',
                        'result_count': len(results),
                        'can_retry': False,
                        'next_tier': None,
                        'timing': {
                            'total_ms': total_time * 1000
                        },
                        'cost': {
                            'total': 0.0  # No cost for retrieval
                        },
                        'timestamp': datetime.now().isoformat()
                    })
                
                # CASE 2: Follow-up to other tiers (FAQ, RAG, LLM)
                else:
                    print(f"   ℹ️ Follow-up to tier {last_tier}, using LLM with context")
                    
                    # NEW: Start tier
                    logger.start_tier(0, 'Follow-up')
                    
                    # Use LLM with full context
                    from openai import OpenAI
                    client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))
                    
                    history_context = memory.format_for_llm(session_id)
                    
                    response = client.chat.completions.create(
                        model="gpt-4o-mini",
                        messages=[
                            {
                                "role": "system",
                                "content": "You are a helpful assistant. Answer follow-up questions based on the conversation context."
                            },
                            {
                                "role": "user",
                                "content": f"""Previous conversation:
{history_context}
Follow-up question: {user_message}
Answer based on the context above."""
                            }
                        ],
                        temperature=0.3,
                        max_tokens=400
                    )
                    
                    answer = response.choices[0].message.content.strip()
                    
                    # Calculate cost
                    input_tokens = response.usage.prompt_tokens
                    output_tokens = response.usage.completion_tokens
                    cost = (input_tokens * 0.00015 + output_tokens * 0.0006) / 1000
                    
                    # NEW: Complete tier
                    logger.complete_tier(
                        tier=0,
                        status='success',
                        cost=cost,
                        tier_name='Follow-up',
                        response_type='followup_llm'
                    )
                    
                    # Store in memory
                    memory.add_exchange(
                        session_id,
                        user_message,
                        answer,
                        tier=4,
                        metadata={'type': 'followup', 'parent_tier': last_tier}
                    )
                    
                    total_time = time.time() - request_start
                    
                    # NEW: Save to database
                    if logger:
                        bot_message_id = logger.save(user_message, answer)
                        print(f"💾 Saved to database (message_id: {bot_message_id})")
                    
                    return JsonResponse({
                        'response': answer,
                        'type': 'followup_llm',
                        'tier': 4,
                        'tier_name': 'AI Assistant (Follow-up)',
                        'can_retry': False,
                        'next_tier': None,
                        'timing': {
                            'total_ms': total_time * 1000
                        },
                        'cost': {
                            'llm': cost,
                            'total': cost
                        },
                        'timestamp': datetime.now().isoformat()
                    })
            
            else:
                # No previous exchange, treat as new question
                print(f"   ⚠️ No previous exchange found, treating as new question")
                start_tier = 1
        
        # ============================================================
        # TIER 1: FAQ HANDLER
        # ============================================================
        if start_tier <= 1:
            tier_attempts.append({
                'tier': 1,
                'tier_name': 'FAQ',
                'status': 'searching',
                'message': 'Searching FAQ...',
                'icon': '🔍'
            })
            
            # NEW: Start tier timing
            logger.start_tier(1, 'FAQ')
            
            faq_start = time.time()
            faq_handler = get_faq_handler(FAQ_CSV_PATH)
            
            if faq_handler:
                faq_result = faq_handler.answer(user_message, threshold=0.7)
                faq_time = time.time() - faq_start
                
                if faq_result['found']:
                    # NEW: Complete tier
                    logger.complete_tier(
                        tier=1,
                        status='success',
                        similarity=faq_result.get('similarity'),
                        result_count=1,
                        tier_name='FAQ',
                        response_type='faq'
                    )
                    
                    # ✅ Store in memory
                    memory.add_exchange(
                        session_id,
                        user_message,
                        faq_result['answer'],
                        tier=1
                    )
                    
                    total_time = time.time() - request_start
                    
                    tier_attempts[-1]['status'] = 'success'
                    tier_attempts[-1]['message'] = 'Found in FAQ'
                    
                    print(f"✅ TIER 1 (FAQ): Match found (similarity: {faq_result['similarity']:.3f})")
                    
                    # NEW: Save to database
                    if logger:
                        bot_message_id = logger.save(user_message, faq_result['answer'])
                        print(f"💾 Saved to database (message_id: {bot_message_id})")
                    
                    return JsonResponse({
                        'response': faq_result['answer'],
                        'type': 'faq',
                        'tier': 1,
                        'tier_name': 'FAQ',
                        'similarity': faq_result['similarity'],
                        'confidence': faq_result['confidence'],
                        'can_retry': True,
                        'next_tier': 'PDF Documents',
                        'tier_attempts': tier_attempts,
                        'timing': {
                            'faq_ms': faq_time * 1000,
                            'total_ms': total_time * 1000
                        },
                        'cost': {
                            'total': 0.0
                        },
                        'timestamp': datetime.now().isoformat()
                    })
                else:
                    # NEW: Complete tier
                    logger.complete_tier(
                        tier=1,
                        status='not_found',
                        similarity=faq_result.get('similarity', 0)
                    )
                    
                    tier_attempts[-1]['status'] = 'not_found'
                    tier_attempts[-1]['message'] = 'Not found in FAQ'
                    
                    print(f"⏭️ TIER 1 (FAQ): No match (best: {faq_result.get('similarity', 0):.3f})")
        
        # ============================================================
        # TIER 2: PDF RAG HANDLER
        # ============================================================
        if start_tier <= 2:
            tier_attempts.append({
                'tier': 2,
                'tier_name': 'PDF Documents',
                'status': 'searching',
                'message': 'Scanning documents...',
                'icon': '📚'
            })
            
            print(f"📚 Trying TIER 2: PDF RAG...")
            
            # NEW: Start tier timing
            logger.start_tier(2, 'PDF RAG')
            
            try:
                rag_start = time.time()
                rag_handler = get_pdf_rag_handler(use_llm=True)
                
                rag_result = rag_handler.answer(user_message, top_k=5, threshold=0.5)
                rag_time = time.time() - rag_start
                
                if rag_result['found']:
                    # NEW: Complete tier
                    logger.complete_tier(
                        tier=2,
                        status='success',
                        similarity=rag_result.get('top_similarity'),
                        result_count=len(rag_result.get('sources', [])),
                        cost=rag_result['cost']['total_cost'],
                        tier_name='PDF RAG',
                        response_type='pdf_rag'
                    )
                    
                    # ✅ Store in memory
                    memory.add_exchange(
                        session_id,
                        user_message,
                        rag_result['answer'],
                        tier=2
                    )
                    
                    total_time = time.time() - request_start
                    
                    tier_attempts[-1]['status'] = 'success'
                    tier_attempts[-1]['message'] = 'Found in documents'
                    
                    print(f"✅ TIER 2 (PDF RAG): Answer generated (similarity: {rag_result.get('top_similarity', 0):.3f})")
                    
                    # NEW: Save to database
                    if logger:
                        bot_message_id = logger.save(user_message, rag_result['answer'])
                        print(f"💾 Saved to database (message_id: {bot_message_id})")
                    
                    return JsonResponse({
                        'response': rag_result['answer'],
                        'type': 'pdf_rag',
                        'tier': 2,
                        'tier_name': 'PDF Documents',
                        'sources': rag_result.get('sources', [])[:3],
                        'similarity': rag_result.get('top_similarity', 0),
                        'answer_method': rag_result.get('answer_method', 'template'),
                        'can_retry': True,
                        'next_tier': 'Chemical Database',
                        'tier_attempts': tier_attempts,
                        'timing': {
                            'faq_ms': faq_time * 1000 if start_tier <= 1 else 0,
                            'rag_search_ms': rag_result['timing']['search_ms'],
                            'rag_generation_ms': rag_result['timing']['generation_ms'],
                            'rag_total_ms': rag_result['timing']['total_ms'],
                            'total_ms': total_time * 1000
                        },
                        'cost': {
                            'llm': rag_result['cost']['llm_cost'],
                            'total': rag_result['cost']['total_cost']
                        },
                        'timestamp': datetime.now().isoformat()
                    })
                else:
                    # NEW: Complete tier
                    logger.complete_tier(
                        tier=2,
                        status='not_found',
                        similarity=rag_result.get('top_similarity', 0)
                    )
                    
                    tier_attempts[-1]['status'] = 'not_found'
                    tier_attempts[-1]['message'] = 'Not found in documents'
                    
                    print(f"⏭️ TIER 2 (PDF RAG): No match (best: {rag_result.get('top_similarity', 0):.3f})")
                    
            except Exception as e:
                # NEW: Log error
                logger.log_error(2, str(e))
                logger.complete_tier(tier=2, status='error')
                
                tier_attempts[-1]['status'] = 'error'
                tier_attempts[-1]['message'] = f'Error: {str(e)[:50]}'
                
                print(f"❌ TIER 2 (PDF RAG): Error - {e}")
        
        # ============================================================
        # TIER 3: SQL AGENT
        # ============================================================
        if start_tier <= 3:
            tier_attempts.append({
                'tier': 3,
                'tier_name': 'Chemical Database',
                'status': 'searching',
                'message': 'Querying database...',
                'icon': '🗄️'
            })
            
            print(f"🗄️ Trying TIER 3: SQL Agent...")
            
            # NEW: Start tier timing
            logger.start_tier(3, 'SQL Agent')
            
            try:
                sql_start = time.time()
                sql_agent = get_sql_agent()
                
                sql_result = sql_agent.answer(user_message)
                sql_time = time.time() - sql_start
                
                if sql_result and isinstance(sql_result, dict):
                    has_results = sql_result.get('result_count', 0) > 0
                    
                    if has_results:
                        # NEW: Complete tier
                        logger.complete_tier(
                            tier=3,
                            status='success',
                            result_count=sql_result.get('result_count'),
                            sql_query=sql_result.get('sql_query'),
                            main_term=sql_result.get('main_term'),
                            synonyms=sql_result.get('synonyms'),
                            cost=sql_result['cost']['total'],
                            tier_name='SQL Agent',
                            response_type='sql_agent'
                        )
                        
                        # ✅ Store in memory WITH results metadata
                        memory.add_exchange(
                            session_id,
                            user_message,
                            sql_result['answer'],
                            tier=3,
                            metadata={
                                'sql_query': sql_result.get('sql_query'),
                                'results': sql_result.get('results', [])[:20],  # Store top 20
                                'main_term': sql_result.get('main_term'),
                                'synonyms': sql_result.get('synonyms')
                            }
                        )
                        
                        total_time = time.time() - request_start
                        
                        tier_attempts[-1]['status'] = 'success'
                        tier_attempts[-1]['message'] = f'Found {sql_result.get("result_count", 0)} results'
                        
                        print(f"✅ TIER 3 (SQL): {sql_result.get('result_count', 0)} results found")
                        
                        # NEW: Save to database
                        if logger:
                            bot_message_id = logger.save(user_message, sql_result['answer'])
                            print(f"💾 Saved to database (message_id: {bot_message_id})")
                        
                        return JsonResponse({
                            'response': sql_result['answer'],
                            'type': 'sql_agent',
                            'tier': 3,
                            'tier_name': 'Chemical Database',
                            'sql_query': sql_result.get('sql_query'),
                            'result_count': sql_result.get('result_count', 0),
                            'can_retry': True,
                            'next_tier': 'AI Assistant',
                            'tier_attempts': tier_attempts,
                            'timing': {
                                'faq_ms': faq_time * 1000 if start_tier <= 1 else 0,
                                'sql_generation_ms': sql_result['timing']['generation_ms'],
                                'sql_execution_ms': sql_result['timing']['execution_ms'],
                                'sql_formatting_ms': sql_result['timing']['formatting_ms'],
                                'sql_total_ms': sql_result['timing']['total_ms'],
                                'total_ms': total_time * 1000
                            },
                            'cost': {
                                'sql_generation': sql_result['cost']['generation'],
                                'sql_formatting': sql_result['cost']['formatting'],
                                'total': sql_result['cost']['total']
                            },
                            'timestamp': datetime.now().isoformat()
                        })
                    else:
                        # NEW: Complete tier
                        logger.complete_tier(tier=3, status='not_found')
                        
                        tier_attempts[-1]['status'] = 'not_found'
                        tier_attempts[-1]['message'] = 'Query not relevant for database'
                        
                        print(f"⏭️ TIER 3 (SQL): No results returned")
                else:
                    # NEW: Complete tier
                    logger.complete_tier(tier=3, status='not_found')
                    
                    tier_attempts[-1]['status'] = 'not_found'
                    tier_attempts[-1]['message'] = 'Invalid result'
                    
                    print(f"⏭️ TIER 3 (SQL): Invalid result")
                    
            except Exception as e:
                # NEW: Log error
                logger.log_error(3, str(e))
                logger.complete_tier(tier=3, status='error')
                
                tier_attempts[-1]['status'] = 'error'
                tier_attempts[-1]['message'] = f'Error: {str(e)[:50]}'
                
                print(f"❌ TIER 3 (SQL): Error - {e}")
        
        # ============================================================
        # TIER 4: LLM FALLBACK (FINAL TIER)
        # ============================================================
        tier_attempts.append({
            'tier': 4,
            'tier_name': 'AI Assistant',
            'status': 'searching',
            'message': 'Generating answer...',
            'icon': '🤖'
        })
        
        print(f"🤖 Trying TIER 4: LLM Fallback...")
        
        # NEW: Start tier timing
        logger.start_tier(4, 'LLM Fallback')
        
        try:
            from openai import OpenAI
            
            client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))
            
            llm_start = time.time()
            
            # ✅ Include conversation context if available
            history_context = memory.format_for_llm(session_id)
            
            system_prompt = """You are a helpful assistant for the NORMAN Suspect List Exchange platform. 
Provide helpful, concise responses about environmental chemistry, chemical databases, and suspect screening. 
If you don't know something specific, suggest checking the NORMAN website."""
            
            if history_context:
                user_prompt = f"""Previous conversation:
{history_context}
Current question: {user_message}"""
            else:
                user_prompt = user_message
            
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.7,
                max_tokens=400
            )
            
            answer = response.choices[0].message.content.strip()
            
            # ✅ Store in memory
            memory.add_exchange(
                session_id,
                user_message,
                answer,
                tier=4
            )
            
            # Calculate cost
            input_tokens = response.usage.prompt_tokens
            output_tokens = response.usage.completion_tokens
            cost = (input_tokens * 0.00015 + output_tokens * 0.0006) / 1000
            
            # NEW: Complete tier
            logger.complete_tier(
                tier=4,
                status='success',
                cost=cost,
                tier_name='LLM Fallback',
                response_type='llm_fallback'
            )
            
            llm_time = time.time() - llm_start
            total_time = time.time() - request_start
            
            tier_attempts[-1]['status'] = 'success'
            tier_attempts[-1]['message'] = 'Generated response'
            
            print(f"✅ TIER 4 (LLM): Response generated (cost: ${cost:.6f})")
            
            # NEW: Save to database
            if logger:
                bot_message_id = logger.save(user_message, answer)
                print(f"💾 Saved to database (message_id: {bot_message_id})")
            
            return JsonResponse({
                'response': answer,
                'type': 'llm_fallback',
                'tier': 4,
                'tier_name': 'AI Assistant',
                'can_retry': False,
                'next_tier': None,
                'tier_attempts': tier_attempts,
                'timing': {
                    'faq_ms': faq_time * 1000 if start_tier <= 1 else 0,
                    'llm_ms': llm_time * 1000,
                    'total_ms': total_time * 1000
                },
                'cost': {
                    'llm': cost,
                    'total': cost
                },
                'timestamp': datetime.now().isoformat()
            })
            
        except Exception as e:
            # NEW: Log error
            if logger:
                logger.log_error(4, str(e))
                logger.complete_tier(tier=4, status='error')
            
            tier_attempts[-1]['status'] = 'error'
            tier_attempts[-1]['message'] = f'Error: {str(e)[:50]}'
            
            print(f"❌ TIER 4 (LLM): Error - {e}")
            
            # ============================================================
            # ABSOLUTE FALLBACK
            # ============================================================
            total_time = time.time() - request_start
            
            fallback_response = (
                "I'm having trouble answering that question. Please try:\n\n"
                "• **Rephrasing your question** - Be more specific\n"
                "• **Browsing FAQ categories** - Find related topics\n"
                "• **Checking spelling** - Make sure terms are correct\n\n"
                "Or ask me something else!"
            )
            
            # NEW: Save error to database
            if logger:
                bot_message_id = logger.save(user_message, fallback_response)
                print(f"💾 Saved error to database (message_id: {bot_message_id})")
            
            return JsonResponse({
                'response': fallback_response,
                'type': 'error',
                'tier': 0,
                'tier_name': 'Error',
                'can_retry': False,
                'next_tier': None,
                'tier_attempts': tier_attempts,
                'timing': {
                    'faq_ms': faq_time * 1000 if start_tier <= 1 else 0,
                    'total_ms': total_time * 1000
                },
                'cost': {
                    'total': 0.0
                },
                'timestamp': datetime.now().isoformat()
            })
        
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)
    except Exception as exc:
        # NEW: Log exception
        if logger:
            logger.log_error(0, str(exc), {'traceback': str(exc)})
        
        print(f"❌ Error in chatbot_api: {exc}")
        import traceback
        traceback.print_exc()
        return JsonResponse({'error': 'Error processing message'}, status=500)


# ============================================================
# HELPER FUNCTION: FORMAT SQL RESULTS
# ============================================================
def format_all_sql_results(results: list, main_term: str, synonyms: list) -> str:
    """
    Format ALL SQL results for follow-up display (NO TRUNCATION)
    
    Args:
        results: List of result dicts from SQL query
        main_term: Main search term
        synonyms: List of synonym terms
        
    Returns:
        Formatted markdown string with ALL results
    """
    
    if not results:
        return f"No results found for **{main_term}**."
    
    # Separate by priority if available
    exact_matches = []
    synonym_matches = []
    
    for result in results:
        priority = result.get('match_priority', 10)
        
        if priority <= 2:  # Exact or starts with user term
            exact_matches.append(result)
        else:
            synonym_matches.append(result)
    
    # Build answer
    answer_parts = []
    
    # Header
    total = len(results)
    if synonyms:
        answer_parts.append(
            f"📋 **All {total} results for '{main_term}'**\n"
            f"(including synonyms: {', '.join(synonyms[:5])})"
        )
    else:
        answer_parts.append(f"📋 **All {total} results for '{main_term}'**")
    
    answer_parts.append("")  # Blank line
    
    # ============================================================
    # EXACT MATCHES - SHOW ALL (NO LIMIT)
    # ============================================================
    if exact_matches:
        answer_parts.append(f"**✓ Exact matches ({len(exact_matches)}):**")
        answer_parts.append("")
        
        for i, r in enumerate(exact_matches, 1):
            name = r.get('name', 'N/A')
            cas = r.get('cas', 'N/A')
            mass = r.get('mass_num', 'N/A')
            
            answer_parts.append(f"{i}. **{name}**")
            
            # Add details on same line if available
            details = []
            if cas and cas not in ['N/A', 'None', None]:
                details.append(f"CAS: {cas}")
            if mass and mass not in ['N/A', 'None', None]:
                details.append(f"Mass: {mass} Da")
            
            if details:
                answer_parts.append(f"   • {' | '.join(details)}")
    
    # ============================================================
    # SYNONYM/RELATED MATCHES - SHOW ALL (NO LIMIT)
    # ============================================================
    if synonym_matches:
        if exact_matches:
            answer_parts.append("")  # Separator between sections
        
        answer_parts.append(f"**~ Related compounds ({len(synonym_matches)}):**")
        answer_parts.append("")
        
        for i, r in enumerate(synonym_matches, 1):
            name = r.get('name', 'N/A')
            cas = r.get('cas', 'N/A')
            mass = r.get('mass_num', 'N/A')
            
            answer_parts.append(f"{i}. {name}")
            
            # Add details
            details = []
            if cas and cas not in ['N/A', 'None', None]:
                details.append(f"CAS: {cas}")
            if mass and mass not in ['N/A', 'None', None]:
                details.append(f"Mass: {mass} Da")
            
            if details:
                answer_parts.append(f"   • {' | '.join(details)}")
    
    # ============================================================
    # FOOTER
    # ============================================================
    answer_parts.append("")
    answer_parts.append(f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    answer_parts.append(f"**Total: {total} compounds**")
    
    return "\n".join(answer_parts)


# ============================================================
# EXISTING HELPER FUNCTIONS
# ============================================================
def get_categories_api():
    """Return FAQ categories with icons from CSV"""
    faq_handler = get_faq_handler(FAQ_CSV_PATH)
    
    if not faq_handler:
        return JsonResponse({'error': 'FAQ handler not initialized'}, status=500)
    
    # Group FAQs by category
    categories_dict = {}
    category_icons = {}
    
    for faq in faq_handler.faq_data:
        category = faq.get('category_lvl1', 'General')
        
        if category not in category_icons:
            category_icons[category] = faq.get('category_icon', '📁')
        
        if category not in categories_dict:
            categories_dict[category] = []
        
        categories_dict[category].append({
            'q': faq.get('button_label', faq.get('question', '')),
            'question': faq.get('question', ''),
            'id': faq.get('id', ''),
            'short_answer': faq.get('short_answer', '')
        })
    
    # Format categories for frontend
    categories = []
    for category_name, questions in categories_dict.items():
        categories.append({
            'name': category_name,
            'display_name': category_name,
            'count': len(questions),
            'icon': category_icons.get(category_name, '📁')
        })
    
    # Sort by category order
    category_order = {
        'Getting started': 1,
        'Using the website': 2,
        'Versioning & citation': 3,
        'Data & identifiers': 4,
        'FAIR & licensing': 5,
        'Integrations': 6,
        'Contributing lists': 7,
        'About the project': 8,
        'Troubleshooting': 9,
    }
    
    categories.sort(key=lambda x: category_order.get(x['name'], 99))
    
    return JsonResponse({
        'categories': categories,
        'faq_data': categories_dict
    })


@require_http_methods(["GET"])
def debug_categories(request):
    """Debug: Shows all FAQs and their categories"""
    faq_handler = get_faq_handler(FAQ_CSV_PATH)
    
    if not faq_handler:
        return JsonResponse({'error': 'FAQ handler not initialized'}, status=500)
    
    category_counts = {}
    faq_list = []
    
    for faq in faq_handler.faq_data:
        category = faq.get('category_lvl1', 'MISSING')
        question = faq.get('question', '')
        
        if category not in category_counts:
            category_counts[category] = 0
        category_counts[category] += 1
        
        faq_list.append({
            'id': faq.get('id', ''),
            'question': question[:80],
            'category': category
        })
    
    return JsonResponse({
        'total_faqs': len(faq_handler.faq_data),
        'category_counts': category_counts,
        'all_faqs': faq_list
    }, json_dumps_params={'indent': 2})


@require_http_methods(["POST"])
def chatbot_feedback(request):
    """Store user feedback with full context"""
    try:
        data = json.loads(request.body)
        
        feedback_data = {
            'helpful': data.get('helpful'),
            'tier': data.get('tier'),
            'tier_name': data.get('tier_name'),
            'type': data.get('type'),
            'timestamp': data.get('timestamp'),
            'user_session': request.session.session_key
        }
        
        print(f"\n{'='*60}")
        print(f"📊 USER FEEDBACK RECEIVED")
        print(f"{'='*60}")
        print(f"   Helpful: {feedback_data['helpful']}")
        print(f"   Tier: {feedback_data['tier']} ({feedback_data['tier_name']})")
        print(f"   Type: {feedback_data['type']}")
        print(f"{'='*60}\n")
        
        # TODO: Update message feedback in database
        # from .models import ChatMessage
        # message_id = data.get('message_id')
        # if message_id:
        #     ChatMessage.objects.filter(id=message_id).update(
        #         helpful=feedback_data['helpful'],
        #         feedback_timestamp=datetime.now()
        #     )
        
        return JsonResponse({
            'status': 'success',
            'message': 'Feedback recorded',
            'timestamp': datetime.now().isoformat()
        })
        
    except Exception as e:
        print(f"❌ Error recording feedback: {e}")
        return JsonResponse({'error': str(e)}, status=500)