

from django.shortcuts import render
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import ensure_csrf_cookie
from datetime import datetime
import json
import os

# Import FAQ engine
from .faq_engine import get_faq_engine, initialize_faq_engine


# Initialize FAQ engine on module load
FAQ_CSV_PATH = os.path.join(os.path.dirname(__file__), 'data', 'chatbot_faq.csv')
if os.path.exists(FAQ_CSV_PATH):
    initialize_faq_engine(FAQ_CSV_PATH)
    print(f"✅ FAQ Engine initialized with {FAQ_CSV_PATH}")
else:
    print(f"⚠️ FAQ CSV not found at {FAQ_CSV_PATH}")


@ensure_csrf_cookie
def home(request):
    """
    Render the home page with chatbot widget
    """
    context = {}
    return render(request, 'chatbot/home.html', context)


@require_http_methods(["GET", "POST"])
def chatbot_api(request):
    """
    Handle chatbot API requests
    Supports both POST (messages) and GET (categories)
    """
    
    # GET request - Return categories and FAQ data
    if request.method == "GET":
        action = request.GET.get('action', '')
        
        if action == 'get_categories':
            return get_categories_api()
        
        # Default GET response
        return JsonResponse({
            'error': 'Invalid action'
        }, status=400)
    
    # POST request - Handle messages
    try:
        # Parse request body
        data = json.loads(request.body)
        user_message = data.get('message', '').strip()
        message_history = data.get('history', [])
        
        # Validation
        if not user_message:
            return JsonResponse({
                'error': 'Message cannot be empty'
            }, status=400)
        
        if len(user_message) > 1000:
            return JsonResponse({
                'error': 'Message too long (max 1000 characters)'
            }, status=400)
        
        # Generate response
        bot_response = generate_response(user_message, message_history)
        
        # Return response
        return JsonResponse({
            'response': bot_response,
            'timestamp': datetime.now().isoformat()
        })
        
    except json.JSONDecodeError:
        return JsonResponse({
            'error': 'Invalid JSON format'
        }, status=400)
        
    except Exception as e:
        print(f"❌ Error in chatbot_api: {e}")
        return JsonResponse({
            'error': 'An error occurred processing your message'
        }, status=500)


def get_categories_api():
    """
    Return categories and FAQ data for frontend
    """
    try:
        faq_engine = get_faq_engine()
        
        if not faq_engine:
            return JsonResponse({
                'error': 'FAQ engine not initialized'
            }, status=500)
        
        # Get categories from FAQ engine
        categories_data = faq_engine.get_categories_with_questions()
        
        # Format response
        categories = []
        faq_data = {}
        
        for category_name, questions in categories_data.items():
            # Add category to list
            categories.append({
                'name': category_name,
                'display_name': format_category_display_name(category_name),
                'count': len(questions)
            })
            
            # Add questions to FAQ data
            faq_data[category_name] = [
                {
                    'q': q.get('button_label', q.get('faq_title', '')),
                    'question': q.get('question', ''),
                    'id': q.get('id', '')
                }
                for q in questions
            ]
        
        # Sort categories by their order in CSV (if available)
        categories.sort(key=lambda x: get_category_order(x['name']))
        
        return JsonResponse({
            'categories': categories,
            'faq_data': faq_data
        })
        
    except Exception as e:
        print(f"❌ Error in get_categories_api: {e}")
        return JsonResponse({
            'error': 'Failed to load categories'
        }, status=500)


def format_category_display_name(category_name):
    """
    Format category name for display
    Examples:
        "Getting started" -> "Getting Started"
        "Data & identifiers" -> "Data & IDs"
    """
    # Custom short names for UI
    short_names = {
        'Data & identifiers': 'Data & IDs',
        'Versioning & citation': 'Citation',
        'Using the website': 'Using Website',
        'Contributing lists': 'Contributing',
        'FAIR & licensing': 'FAIR',
        'Troubleshooting': 'Help',
        'About the project': 'About',
    }
    
    return short_names.get(category_name, category_name.title())


def get_category_order(category_name):
    """
    Return sort order for category
    """
    order = {
        'Getting started': 1,
        'Using the website': 2,
        'Data & identifiers': 3,
        'Versioning & citation': 4,
        'Integrations': 5,
        'Contributing lists': 6,
        'FAIR & licensing': 7,
        'Troubleshooting': 8,
        'About the project': 9,
    }
    return order.get(category_name, 99)


def generate_response(user_message: str, history: list) -> str:
    """
    Generate intelligent response using FAQ engine
    """
    # Get FAQ engine
    faq_engine = get_faq_engine()
    
    # Try FAQ matching first
    if faq_engine:
        result = faq_engine.get_answer(user_message, confidence_threshold=0.4)
        
        if result:
            faq = result['faq']
            confidence = result['confidence']
            
            # High confidence - give full answer
            if confidence > 0.7:
                response = result['answer']
                
                # Add related links if available
                links = result.get('related_links', [])
                if links and links[0]:
                    response += "\n\n📎 **Related links:**"
                    for link in links[:2]:
                        if link.strip():
                            response += f"\n• {link.strip()}"
                
                return response
            
            # Medium confidence - give short answer and ask
            elif confidence > 0.5:
                return f"{faq.get('short_answer', faq.get('answer', ''))}\n\nWould you like more details?"
            
            # Low confidence - suggest the topic
            else:
                return f"I found information about: **{faq.get('faq_title', 'this topic')}**. Is this what you're looking for?"
    
    # Fallback responses
    message_lower = user_message.lower()
    
    # Greetings
    if any(word in message_lower for word in ['hello', 'hi', 'hey', 'greetings']):
        return ("Hello! 👋 I'm your FAQ Assistant. I can help you with various questions. "
                "Choose a category below or type your question.")
    
    # Help
    elif any(word in message_lower for word in ['help', 'guide']):
        return ("I can help you find answers to common questions. "
                "You can:\n"
                "• Click a category to browse questions\n"
                "• Type your question directly\n"
                "• Ask me anything!")
    
    # Default fallback
    return ("I'm not sure about that. Could you try:\n"
            "• Choosing a category from the buttons below\n"
            "• Rephrasing your question\n"
            "• Being more specific")



def get_categories_api():
    """
    Return categories with icons and FAQ data for frontend
    """
    try:
        faq_engine = get_faq_engine()
        
        if not faq_engine:
            return JsonResponse({
                'error': 'FAQ engine not initialized'
            }, status=500)
        
        # Get categories from FAQ engine
        categories_data = faq_engine.get_categories_with_questions()
        
        # Format response
        categories = []
        faq_data = {}
        category_icons = {}  # Store icons by category
        
        for category_name, questions in categories_data.items():
            # Extract icon from first question in category (all should have same icon)
            icon = None
            if questions:
                icon = questions[0].get('category_icon', '●')  # Default to ●
            
            # Store icon
            category_icons[category_name] = icon or '●'
            
            # Add category to list
            categories.append({
                'name': category_name,
                'display_name': format_category_display_name(category_name),
                'count': len(questions),
                'icon': icon or '●'  # Include icon in response
            })
            
            # Add questions to FAQ data
            faq_data[category_name] = [
                {
                    'q': q.get('button_label', q.get('faq_title', '')),
                    'question': q.get('question', ''),
                    'id': q.get('id', '')
                }
                for q in questions
            ]
        
        # Sort categories by their order in CSV
        categories.sort(key=lambda x: get_category_order(x['name']))
        
        return JsonResponse({
            'categories': categories,
            'faq_data': faq_data
        })
        
    except Exception as e:
        print(f"❌ Error in get_categories_api: {e}")
        import traceback
        traceback.print_exc()
        return JsonResponse({
            'error': 'Failed to load categories'
        }, status=500)