# chatbot/views.py
"""
NORMAN SLE Chatbot Views - With Intelligent FAQ Support
"""

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
FAQ_CSV_PATH = os.path.join(os.path.dirname(__file__), 'data', 'norman_sle_chatbot_faq.csv')
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
    # Get FAQ engine for quick buttons
    faq_engine = get_faq_engine()
    quick_buttons = []
    categories = []
    
    if faq_engine:
        quick_buttons = faq_engine.get_quick_buttons(top_n=6)
        categories = faq_engine.get_categories()
    
    context = {
        'quick_buttons': quick_buttons,
        'categories': categories,
    }
    
    return render(request, 'chatbot/home.html', context)


@require_http_methods(["POST"])
def chatbot_api(request):
    """
    Handle chatbot API requests with intelligent FAQ matching
    """
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


def generate_response(user_message: str, history: list) -> str:
    """
    Generate intelligent response using FAQ engine
    
    Args:
        user_message: User's message
        history: Conversation history
        
    Returns:
        Bot response text
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
                if links and links[0]:  # Check if not empty
                    response += "\n\n📎 **Related links:**"
                    for link in links[:2]:  # Max 2 links
                        if link.strip():
                            response += f"\n• {link.strip()}"
                
                return response
            
            # Medium confidence - give short answer and ask
            elif confidence > 0.5:
                return f"{faq.get('short_answer', faq.get('answer', ''))}\n\nWould you like more details?"
            
            # Low confidence - suggest the topic
            else:
                return f"I found information about: **{faq.get('faq_title', 'this topic')}**. Is this what you're looking for?"
    
    # Fallback to keyword-based responses
    message_lower = user_message.lower()
    
    # Greetings
    if any(word in message_lower for word in ['hello', 'hi', 'hey', 'greetings']):
        return ("Hello! 👋 I'm the NORMAN SLE Assistant. I can help you with:\n\n"
                "🔍 **Chemical searches** - Find compounds by name, CAS, InChIKey\n"
                "📊 **Database queries** - Access suspect lists and data\n"
                "❓ **FAQ** - Answer questions about NORMAN-SLE\n\n"
                "What would you like to know?")
    
    # Help
    elif any(word in message_lower for word in ['help', 'guide', 'how to']):
        return ("I can assist you with:\n\n"
                "**✨ Quick Actions:**\n"
                "• Search by CAS number\n"
                "• Query molecular formulas\n"
                "• Find recent database additions\n"
                "• Learn about SMILES notation\n\n"
                "**📚 Categories:**\n"
                "• Getting started with NORMAN-SLE\n"
                "• Using the website\n"
                "• Data & identifiers\n"
                "• Contributing lists\n\n"
                "Just ask me a question!")
    
    # About NORMAN
    elif 'norman' in message_lower and any(word in message_lower for word in ['what', 'about', 'is']):
        return ("**NORMAN-SLE** (Suspect List Exchange) is a community-driven platform for sharing "
                "suspect lists used in high-resolution mass spectrometry screening.\n\n"
                "It provides:\n"
                "• 🗃️ Curated suspect lists for environmental screening\n"
                "• 🔗 FAIR identifiers (SMILES, InChI, CAS, DTXSID)\n"
                "• 📖 Versioned lists with DOIs on Zenodo\n"
                "• 🔄 Integration with PubChem and CompTox\n\n"
                "Visit: https://www.norman-network.com/nds/SLE/")
    
    # Search/CAS related
    elif any(word in message_lower for word in ['search', 'find', 'cas', 'chemical']):
        return ("To search for chemicals in NORMAN-SLE:\n\n"
                "1️⃣ **By CAS number** - Use the exact CAS registry number\n"
                "2️⃣ **By name** - Search chemical names or synonyms\n"
                "3️⃣ **By InChIKey** - For precise structural matching\n"
                "4️⃣ **By formula** - Molecular formula searches\n\n"
                "You can browse lists at: https://www.norman-network.com/nds/SLE/")
    
    # Database/lists
    elif any(word in message_lower for word in ['database', 'list', 'data']):
        return ("NORMAN-SLE hosts **suspect lists** - curated collections of chemicals for "
                "environmental screening.\n\n"
                "**Available resources:**\n"
                "• 📋 Individual suspect lists (S-numbered)\n"
                "• 🗄️ NORMAN SusDat (merged database)\n"
                "• 📚 Zenodo repository with DOIs\n"
                "• 🔗 PubChem & CompTox integration\n\n"
                "Each list includes identifiers, references, and downloadable files (CSV/XLSX).")
    
    # SMILES
    elif 'smiles' in message_lower:
        return ("**SMILES** (Simplified Molecular Input Line Entry System) is a text notation "
                "for chemical structures.\n\n"
                "**Example:** Water = O, Ethanol = CCO, Benzene = c1ccccc1\n\n"
                "In NORMAN-SLE, SMILES are provided for most compounds to enable:\n"
                "• Structure searches\n"
                "• In silico predictions\n"
                "• Database cross-referencing\n\n"
                "Many lists include both SMILES and InChI formats.")
    
    # Identifiers
    elif any(word in message_lower for word in ['identifier', 'inchi', 'dtxsid', 'pubchem']):
        return ("NORMAN-SLE lists include multiple chemical identifiers:\n\n"
                "**Structural:**\n"
                "• SMILES & InChI/InChIKey\n"
                "• Molecular formula\n\n"
                "**Database IDs:**\n"
                "• CAS Registry Number\n"
                "• PubChem CID\n"
                "• DTXSID (CompTox)\n"
                "• ChemSpider ID\n\n"
                "These enable cross-database searches and data integration.")
    
    # Download/access
    elif any(word in message_lower for word in ['download', 'access', 'get', 'file']):
        return ("You can download NORMAN-SLE lists from:\n\n"
                "**Main website:**\n"
                "https://www.norman-network.com/nds/SLE/\n\n"
                "**Zenodo (with DOIs):**\n"
                "https://zenodo.org/communities/norman-sle/\n\n"
                "**Formats available:**\n"
                "• CSV/XLSX (full lists)\n"
                "• InChIKey-only files\n"
                "• Companion documentation\n\n"
                "All data is open access!")
    
    # Contributing
    elif any(word in message_lower for word in ['contribute', 'submit', 'add', 'my list']):
        return ("We welcome contributions! 🎉\n\n"
                "**To submit a suspect list:**\n"
                "1️⃣ Prepare your list with required identifiers\n"
                "2️⃣ Include references/documentation\n"
                "3️⃣ Contact NORMAN-SLE maintainers\n\n"
                "**Required fields:**\n"
                "• Chemical names\n"
                "• At least one structural identifier (SMILES/InChI)\n"
                "• Data source/rationale\n\n"
                "Contact: norman-sle@norman-network.com")
    
    # Thank you
    elif any(word in message_lower for word in ['thank', 'thanks', 'appreciate']):
        return "You're welcome! 😊 Feel free to ask if you have more questions about NORMAN-SLE!"
    
    # Default - didn't understand
    else:
        return (f'I\'m not sure about "{user_message[:50]}..." \n\n'
                "I can help you with:\n"
                "• What is NORMAN-SLE?\n"
                "• How to search for chemicals\n"
                "• Understanding identifiers (CAS, SMILES, InChI)\n"
                "• Downloading suspect lists\n"
                "• Contributing your own lists\n\n"
                "Try asking one of these questions!")


def get_quick_buttons(request):
    """
    API endpoint to get quick action buttons
    """
    faq_engine = get_faq_engine()
    
    if faq_engine:
        buttons = faq_engine.get_quick_buttons(top_n=8)
        return JsonResponse({'buttons': buttons})
    
    return JsonResponse({'buttons': []})


def get_categories(request):
    """
    API endpoint to get FAQ categories
    """
    faq_engine = get_faq_engine()
    
    if faq_engine:
        categories = faq_engine.get_categories()
        return JsonResponse({'categories': categories})
    
    return JsonResponse({'categories': []})


def search_category(request, category):
    """
    API endpoint to search FAQs by category
    """
    faq_engine = get_faq_engine()
    
    if faq_engine:
        results = faq_engine.search_by_category(category)
        return JsonResponse({
            'category': category,
            'results': [
                {
                    'id': faq.get('id'),
                    'title': faq.get('faq_title'),
                    'question': faq.get('question'),
                    'short_answer': faq.get('short_answer'),
                } for faq in results
            ]
        })
    
    return JsonResponse({'results': []})