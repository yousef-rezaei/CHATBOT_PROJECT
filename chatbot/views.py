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

# FAQ CSV path
FAQ_CSV_PATH = os.path.join(os.path.dirname(__file__), 'data', 'chatbot_faq.csv')


@ensure_csrf_cookie
def home(request):
    """Render the home page with chatbot widget"""
    return render(request, 'chatbot/index.html', {})

import json
import time
import os
from datetime import datetime
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
# from django.views.decorators.csrf import csrf_exempt

# Import your handlers
# from chatbot.faq.faq_handler import get_faq_handler
# from chatbot.pdf_rag.pdf_rag_handler import get_pdf_rag_handler
from chatbot.sql.sql_agent import get_sql_agent

FAQ_CSV_PATH = 'chatbot/faq/data/chatbot_faq.csv'


def get_categories_api():
    """Return FAQ categories for frontend"""
    # Your existing get_categories_api code
    pass


@require_http_methods(["GET", "POST"])
def chatbot_api(request):
    
    if request.method == "GET":
        action = request.GET.get('action', '')
        if action == 'get_categories':
            return get_categories_api()
        return JsonResponse({'error': 'Invalid action'}, status=400)
    
    # POST - Handle user questions
    request_start = time.time()
    faq_time = 0
    
    # ✅ NEW: Track tier attempts
    tier_attempts = []
    
    try:
        data = json.loads(request.body)
        user_message = data.get('message', '').strip()
        skip_tier = data.get('skip_tier', 0)
        
        if not user_message:
            return JsonResponse({'error': 'Message cannot be empty'}, status=400)
        
        if len(user_message) > 1000:
            return JsonResponse({'error': 'Message too long'}, status=400)
        
        print(f"\n{'='*60}")
        print(f"📨 Query: '{user_message[:50]}...' (skip_tier={skip_tier})")
        print(f"{'='*60}")
        
        # ============================================================
        # TIER 1: FAQ HANDLER
        # ============================================================
        if skip_tier < 1:
            # ✅ Track attempt
            tier_attempts.append({
                'tier': 1,
                'tier_name': 'FAQ',
                'status': 'searching',
                'message': 'Searching FAQ...',
                'icon': '🔍'
            })
            
            faq_start = time.time()
            faq_handler = get_faq_handler(FAQ_CSV_PATH)
            
            if faq_handler:
                faq_result = faq_handler.answer(user_message, threshold=0.6)
                faq_time = time.time() - faq_start
                
                if faq_result['found']:
                    total_time = time.time() - request_start
                    
                    # ✅ Mark as success
                    tier_attempts[-1]['status'] = 'success'
                    tier_attempts[-1]['message'] = 'Found in FAQ'
                    
                    print(f"✅ TIER 1 (FAQ): Match found (similarity: {faq_result['similarity']:.3f})")
                    
                    return JsonResponse({
                        'response': faq_result['answer'],
                        'type': 'faq',
                        'tier': 1,
                        'tier_name': 'FAQ',
                        'similarity': faq_result['similarity'],
                        'confidence': faq_result['confidence'],
                        'can_retry': True,
                        'next_tier': 'PDF Documents',
                        'tier_attempts': tier_attempts,  # ✅ Send progress
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
                    # ✅ Mark as not found
                    tier_attempts[-1]['status'] = 'not_found'
                    tier_attempts[-1]['message'] = 'Not found in FAQ'
                    
                    print(f"⏭️ TIER 1 (FAQ): No match (best: {faq_result.get('similarity', 0):.3f})")
        
        # ============================================================
        # TIER 2: PDF RAG HANDLER
        # ============================================================
        if skip_tier < 2:
            # ✅ Track attempt
            tier_attempts.append({
                'tier': 2,
                'tier_name': 'PDF Documents',
                'status': 'searching',
                'message': 'Scanning documents...',
                'icon': '📚'
            })
            
            print(f"📚 Trying TIER 2: PDF RAG...")
            
            try:
                rag_start = time.time()
                rag_handler = get_pdf_rag_handler(use_llm=True)
                
                rag_result = rag_handler.answer(user_message, top_k=5, threshold=0.5)
                rag_time = time.time() - rag_start
                
                if rag_result['found']:
                    total_time = time.time() - request_start
                    
                    # ✅ Mark as success
                    tier_attempts[-1]['status'] = 'success'
                    tier_attempts[-1]['message'] = 'Found in documents'
                    
                    print(f"✅ TIER 2 (PDF RAG): Answer generated (similarity: {rag_result.get('top_similarity', 0):.3f})")
                    
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
                        'tier_attempts': tier_attempts,  # ✅ Send progress
                        'timing': {
                            'faq_ms': faq_time * 1000 if skip_tier < 1 else 0,
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
                    # ✅ Mark as not found
                    tier_attempts[-1]['status'] = 'not_found'
                    tier_attempts[-1]['message'] = 'Not found in documents'
                    
                    print(f"⏭️ TIER 2 (PDF RAG): No match (best: {rag_result.get('top_similarity', 0):.3f})")
                    
            except Exception as e:
                # ✅ Mark as error
                tier_attempts[-1]['status'] = 'error'
                tier_attempts[-1]['message'] = f'Error: {str(e)[:50]}'
                
                print(f"❌ TIER 2 (PDF RAG): Error - {e}")
        
        # ============================================================
        # TIER 3: SQL AGENT
        # ============================================================
        if skip_tier < 3:
            # ✅ Track attempt
            tier_attempts.append({
                'tier': 3,
                'tier_name': 'Chemical Database',
                'status': 'searching',
                'message': 'Querying database...',
                'icon': '🗄️'
            })
            
            print(f"🗄️ Trying TIER 3: SQL Agent...")
            
            try:
                sql_start = time.time()
                sql_agent = get_sql_agent()
                
                sql_result = sql_agent.answer(user_message)
                sql_time = time.time() - sql_start
                
                if sql_result and isinstance(sql_result, dict):
                    has_results = sql_result.get('result_count', 0) > 0
                    
                    if has_results:
                        total_time = time.time() - request_start
                        
                        # ✅ Mark as success
                        tier_attempts[-1]['status'] = 'success'
                        tier_attempts[-1]['message'] = f'Found {sql_result.get("result_count", 0)} results'
                        
                        print(f"✅ TIER 3 (SQL): {sql_result.get('result_count', 0)} results found")
                        
                        return JsonResponse({
                            'response': sql_result['answer'],
                            'type': 'sql_agent',
                            'tier': 3,
                            'tier_name': 'Chemical Database',
                            'sql_query': sql_result.get('sql_query'),
                            'result_count': sql_result.get('result_count', 0),
                            'can_retry': True,
                            'next_tier': 'AI Assistant',
                            'tier_attempts': tier_attempts,  # ✅ Send progress
                            'timing': {
                                'faq_ms': faq_time * 1000 if skip_tier < 1 else 0,
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
                        # ✅ Mark as not found
                        tier_attempts[-1]['status'] = 'not_found'
                        tier_attempts[-1]['message'] = 'Query not relevant for database'
                        
                        print(f"⏭️ TIER 3 (SQL): No results returned")
                else:
                    # ✅ Mark as invalid
                    tier_attempts[-1]['status'] = 'not_found'
                    tier_attempts[-1]['message'] = 'Invalid result'
                    
                    print(f"⏭️ TIER 3 (SQL): Invalid result - {sql_result}")
                    
            except Exception as e:
                # ✅ Mark as error
                tier_attempts[-1]['status'] = 'error'
                tier_attempts[-1]['message'] = f'Error: {str(e)[:50]}'
                
                print(f"❌ TIER 3 (SQL): Error - {e}")
        
        # ============================================================
        # TIER 4: LLM FALLBACK (FINAL TIER)
        # ============================================================
        # ✅ Track attempt
        tier_attempts.append({
            'tier': 4,
            'tier_name': 'AI Assistant',
            'status': 'searching',
            'message': 'Generating answer...',
            'icon': '🤖'
        })
        
        print(f"🤖 Trying TIER 4: LLM Fallback...")
        
        try:
            from openai import OpenAI
            
            client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))
            
            llm_start = time.time()
            
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "You are a helpful assistant for the NORMAN Suspect List Exchange platform. "
                            "Provide helpful, concise responses about environmental chemistry, "
                            "chemical databases, and suspect screening. "
                            "If you don't know something specific, suggest checking the NORMAN website."
                        )
                    },
                    {
                        "role": "user",
                        "content": user_message
                    }
                ],
                temperature=0.7,
                max_tokens=400
            )
            
            answer = response.choices[0].message.content.strip()
            
            # Calculate cost
            input_tokens = response.usage.prompt_tokens
            output_tokens = response.usage.completion_tokens
            cost = (input_tokens * 0.00015 + output_tokens * 0.0006) / 1000
            
            llm_time = time.time() - llm_start
            total_time = time.time() - request_start
            
            # ✅ Mark as success
            tier_attempts[-1]['status'] = 'success'
            tier_attempts[-1]['message'] = 'Generated response'
            
            print(f"✅ TIER 4 (LLM): Response generated (cost: ${cost:.6f})")
            
            return JsonResponse({
                'response': answer,
                'type': 'llm_fallback',
                'tier': 4,
                'tier_name': 'AI Assistant',
                'can_retry': False,
                'next_tier': None,
                'tier_attempts': tier_attempts,  # ✅ Send progress
                'timing': {
                    'faq_ms': faq_time * 1000 if skip_tier < 1 else 0,
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
            # ✅ Mark as error
            tier_attempts[-1]['status'] = 'error'
            tier_attempts[-1]['message'] = f'Error: {str(e)[:50]}'
            
            print(f"❌ TIER 4 (LLM): Error - {e}")
            
            # ============================================================
            # ABSOLUTE FALLBACK
            # ============================================================
            total_time = time.time() - request_start
            
            return JsonResponse({
                'response': (
                    "I'm having trouble answering that question. Please try:\n\n"
                    "• **Rephrasing your question** - Be more specific\n"
                    "• **Browsing FAQ categories** - Find related topics\n"
                    "• **Checking spelling** - Make sure terms are correct\n\n"
                    "Or ask me something else!"
                ),
                'type': 'error',
                'tier': 0,
                'tier_name': 'Error',
                'can_retry': False,
                'next_tier': None,
                'tier_attempts': tier_attempts,  # ✅ Send progress
                'timing': {
                    'faq_ms': faq_time * 1000 if skip_tier < 1 else 0,
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
        print(f"❌ Error in chatbot_api: {exc}")
        import traceback
        traceback.print_exc()
        return JsonResponse({'error': 'Error processing message'}, status=500)

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
        
        # TODO: Store in database
        # Feedback.objects.create(**feedback_data)
        
        return JsonResponse({
            'status': 'success',
            'message': 'Feedback recorded',
            'timestamp': datetime.now().isoformat()
        })
        
    except Exception as e:
        print(f"❌ Error recording feedback: {e}")
        return JsonResponse({'error': str(e)}, status=500)