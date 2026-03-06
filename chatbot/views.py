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
    return render(request, 'chatbot/home.html', {})

@require_http_methods(["GET", "POST"])
def chatbot_api(request):
    """Handle chatbot API with 3-tier system + retry support"""
    
    if request.method == "GET":
        action = request.GET.get('action', '')
        if action == 'get_categories':
            return get_categories_api()
        return JsonResponse({'error': 'Invalid action'}, status=400)
    
    # POST - Handle user questions
    request_start = time.time()
    
    try:
        data = json.loads(request.body)
        user_message = data.get('message', '').strip()
        skip_tier = data.get('skip_tier', 0)  # ← NEW: Which tier to skip
        
        if not user_message:
            return JsonResponse({'error': 'Message cannot be empty'}, status=400)
        
        if len(user_message) > 1000:
            return JsonResponse({'error': 'Message too long'}, status=400)
        
        # TIER 1: Try FAQ first (unless skipped)
        if skip_tier < 1:
            faq_start = time.time()
            faq_handler = get_faq_handler(FAQ_CSV_PATH)
            
            if not faq_handler:
                return JsonResponse({'error': 'FAQ system not available'}, status=500)
            
            faq_result = faq_handler.answer(user_message, threshold=0.6)
            faq_time = time.time() - faq_start
            
            if faq_result['found']:
                total_time = time.time() - request_start
                
                return JsonResponse({
                    'response': faq_result['answer'],
                    'type': 'faq',
                    'tier': 1,
                    'similarity': faq_result['similarity'],
                    'confidence': faq_result['confidence'],
                    'can_retry': True,  # ← NEW: Enable retry
                    'timing': {
                        'faq_ms': faq_time * 1000,
                        'total_ms': total_time * 1000
                    },
                    'cost': {
                        'total': 0.0
                    },
                    'timestamp': datetime.now().isoformat()
                })
        
        # TIER 2: Try PDF RAG (unless skipped)
        if skip_tier < 2:
            print(f"📚 FAQ didn't match or skipped (skip_tier={skip_tier}), trying PDF RAG...")
            
            try:
                rag_start = time.time()
                rag_handler = get_pdf_rag_handler(use_llm=True)
                
                rag_result = rag_handler.answer(user_message, top_k=5, threshold=0.5)
                rag_time = time.time() - rag_start
                
                if rag_result['found']:
                    total_time = time.time() - request_start
                    
                    return JsonResponse({
                        'response': rag_result['answer'],
                        'type': 'pdf_rag',
                        'tier': 2,
                        'sources': rag_result.get('sources', [])[:3],
                        'similarity': rag_result.get('top_similarity', 0),
                        'answer_method': rag_result.get('answer_method', 'template'),
                        'can_retry': False,  
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
                    
            except Exception as e:
                print(f"⚠️ PDF RAG error: {e}")
                import traceback
                traceback.print_exc()
        
        # TIER 3: Try SQL Agent
        print(f"🤖 PDF RAG didn't match or skipped (skip_tier={skip_tier}), trying SQL Agent...")
        
        try:
            sql_start = time.time()
            sql_agent = get_sql_agent()
            
            sql_result = sql_agent.answer(user_message)
            sql_time = time.time() - sql_start
            
            total_time = time.time() - request_start
            
            return JsonResponse({
                'response': sql_result['answer'],
                'type': 'sql_agent',
                'tier': 3,
                'sql_query': sql_result.get('sql_query'),
                'result_count': sql_result.get('result_count', 0),
                'can_retry': False,  # ← NEW: No retry after Tier 3
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
            
        except Exception as e:
            print(f"⚠️ SQL Agent error: {e}")
            import traceback
            traceback.print_exc()
            
            # Final fallback
            total_time = time.time() - request_start
            
            return JsonResponse({
                'response': (
                    "I'm not sure how to answer that. Try:\n"
                    "• Browsing FAQ categories\n"
                    "• Being more specific\n"
                    "• Checking spelling"
                ),
                'type': 'unknown',
                'tier': 0,
                'can_retry': False,
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
    """
    Return FAQ categories with icons from CSV
    """
    faq_handler = get_faq_handler(FAQ_CSV_PATH)
    
    if not faq_handler:
        return JsonResponse({'error': 'FAQ handler not initialized'}, status=500)
    
    # Group FAQs by category
    categories_dict = {}
    category_icons = {}  # Store icons
    
    for faq in faq_handler.faq_data:
        # Use category_lvl1 from CSV
        category = faq.get('category_lvl1', 'General')
        
        # Store icon for this category
        if category not in category_icons:
            category_icons[category] = faq.get('category_icon', '📁')
        
        if category not in categories_dict:
            categories_dict[category] = []
        
        # Use button_label (full text) instead of truncated question
        categories_dict[category].append({
            'q': faq.get('button_label', faq.get('question', '')),  # Full button text
            'question': faq.get('question', ''),  # Full question for embedding
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
            'icon': category_icons.get(category_name, '📁')  # Use CSV icon
        })
    
    # Sort by category order (as in CSV)
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
    """
    Debug: http://localhost:8000/debug-categories/
    Shows all FAQs and their categories
    """
    faq_handler = get_faq_handler(FAQ_CSV_PATH)
    
    if not faq_handler:
        return JsonResponse({'error': 'FAQ handler not initialized'}, status=500)
    
    # Count FAQs per category
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
    """Track user feedback"""
    try:
        data = json.loads(request.body)
        helpful = data.get('helpful')
        tier = data.get('tier')
        message_type = data.get('type')
        
        # Log to database or file
        print(f"📊 Feedback: helpful={helpful}, tier={tier}, type={message_type}")
        
        return JsonResponse({'status': 'ok'})
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)