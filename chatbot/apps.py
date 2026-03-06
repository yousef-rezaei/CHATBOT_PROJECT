from django.apps import AppConfig


class ChatbotConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'chatbot'
    
    def ready(self):
        """Called when Django starts"""
        
        # Initialize FAQ handler
        try:
            import os
            from .faq_handler import get_faq_handler
            
            csv_path = os.path.join(
                os.path.dirname(__file__),
                'data',
                'chatbot_faq.csv'
            )
            
            if os.path.exists(csv_path):
                get_faq_handler(csv_path)
                print("✅ FAQ Handler initialized")
            else:
                print(f"⚠️ FAQ CSV not found: {csv_path}")
        except Exception as e:
            print(f"⚠️ Failed to initialize FAQ handler: {e}")
        
        # Initialize RAG vector store (NEW!)
        try:
            from .rag.pdf_vector_store import get_pdf_vector_store
        
            vector_store = get_pdf_vector_store()
            
            # Try to load from cache
            if vector_store.load_from_cache():
                print("✅ RAG Vector Store initialized")
            else:
                print("⚠️ RAG cache not found. Run: python manage.py build_rag")
                
        except Exception as e:
            print(f"⚠️ Failed to initialize RAG: {e}")