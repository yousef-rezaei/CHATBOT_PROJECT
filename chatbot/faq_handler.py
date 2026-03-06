"""
Simple FAQ Handler with DUAL EMBEDDINGS
Embeds both button_label AND full question for maximum coverage
"""

from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity
import numpy as np
import csv
import os


class SimpleFAQHandler:
    """
    FAQ matching with dual embeddings
    Each FAQ has TWO embeddings: button_label + full question
    """
    
    def __init__(self, csv_path: str, cache_dir: str = 'cache'):
        """
        Initialize FAQ handler with dual embeddings
        
        Args:
            csv_path: Path to FAQ CSV file
            cache_dir: Directory for caching embeddings
        """
        self.csv_path = csv_path
        self.cache_dir = cache_dir
        self.embeddings_file = os.path.join(cache_dir, 'faq_embeddings_dual.npy')
        self.metadata_file = os.path.join(cache_dir, 'metadata.json')
        
        print("🔄 Loading FAQ Handler...")
        
        # Load model
        self.model = SentenceTransformer('all-MiniLM-L6-v2')
        print("✅ Model loaded")
        
        # Load FAQs and embeddings
        self.faq_button_labels = []  # Short labels
        self.faq_full_questions = []  # Full questions
        self.faq_data = []
        self.faq_embeddings = None  # Will contain both
        
        self._load_faqs_and_embeddings()
        
        print(f"✅ FAQ Handler ready with {len(self.faq_data)} FAQs (dual embeddings)")
    
    def _load_csv(self):
        """
        Load FAQ data from CSV
        Extract BOTH button_label AND full question
        """
        button_labels = []
        full_questions = []
        data = []
        
        with open(self.csv_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                # Only load active FAQs
                is_active = row.get('is_active', '').strip().upper()
                if is_active in ['TRUE', '1', 'YES']:
                    
                    button_label = row.get('button_label', '')
                    full_question = row.get('question', '')
                    
                    # Need at least one
                    if button_label or full_question:
                        # Use button_label if available, else full_question
                        button_labels.append(button_label if button_label else full_question)
                        full_questions.append(full_question if full_question else button_label)
                        data.append(row)
        
        print(f"✅ Loaded {len(data)} FAQs from {len(set([r.get('category_lvl1', 'General') for r in data]))} categories")
        
        return button_labels, full_questions, data
    
    def _generate_dual_embeddings(self, button_labels, full_questions):
        """
        Generate embeddings for BOTH button_labels and full questions
        
        Returns:
            numpy array with shape (num_faqs * 2, embedding_dim)
            First half: button_label embeddings
            Second half: full question embeddings
        """
        print(f"🧮 Generating DUAL embeddings...")
        print(f"   - {len(button_labels)} button labels")
        print(f"   - {len(full_questions)} full questions")
        
        # Generate embeddings for button labels
        print("   Embedding button labels...")
        button_embeddings = self.model.encode(
            button_labels,
            show_progress_bar=True,
            convert_to_numpy=True
        )
        
        # Generate embeddings for full questions
        print("   Embedding full questions...")
        full_embeddings = self.model.encode(
            full_questions,
            show_progress_bar=True,
            convert_to_numpy=True
        )
        
        # Stack them vertically: [button_embeddings, full_embeddings]
        dual_embeddings = np.vstack([button_embeddings, full_embeddings])
        
        print(f"✅ Generated dual embeddings: shape {dual_embeddings.shape}")
        
        return dual_embeddings
    
    def _load_faqs_and_embeddings(self):
        """Load FAQs and their dual embeddings (cached or generate)"""
        # Load FAQs from CSV
        self.faq_button_labels, self.faq_full_questions, self.faq_data = self._load_csv()
        
        # Check if cache exists and is valid
        if self._cache_is_valid():
            print("📦 Loading dual embeddings from cache...")
            self.faq_embeddings = np.load(self.embeddings_file)
            print(f"✅ Loaded dual embeddings from cache: shape {self.faq_embeddings.shape}")
        else:
            print("🔄 Generating new dual embeddings...")
            self.faq_embeddings = self._generate_dual_embeddings(
                self.faq_button_labels,
                self.faq_full_questions
            )
            self._save_cache()
            print("💾 Dual embeddings cached")
    
    def _cache_is_valid(self):
        """Check if cache exists"""
        return os.path.exists(self.embeddings_file)
    
    def _save_cache(self):
        """Save dual embeddings to cache"""
        os.makedirs(self.cache_dir, exist_ok=True)
        np.save(self.embeddings_file, self.faq_embeddings)
    
    def answer(self, user_question: str, threshold: float = 0.6):
        """
        Answer user question using dual embeddings
        Compares with BOTH button_labels and full questions
        
        Args:
            user_question: User's question
            threshold: Minimum similarity score (0-1)
            
        Returns:
            dict with 'found', 'answer', 'similarity', 'matched_question'
        """
        print(f"\n{'='*60}")
        print(f"❓ User Question: {user_question}")
        print(f"{'='*60}")
        
        # Convert user question to embedding
        user_embedding = self.model.encode(user_question, convert_to_numpy=True)
        
        # Calculate similarities with ALL embeddings (button + full)
        similarities = cosine_similarity(
            [user_embedding],
            self.faq_embeddings
        )[0]
        
        # Split similarities: first half = button labels, second half = full questions
        num_faqs = len(self.faq_data)
        button_sims = similarities[:num_faqs]
        full_sims = similarities[num_faqs:]
        
        # Find best match across BOTH
        best_button_idx = int(np.argmax(button_sims))
        best_full_idx = int(np.argmax(full_sims))
        best_button_score = float(button_sims[best_button_idx])
        best_full_score = float(full_sims[best_full_idx])
        
        # Pick the better match
        if best_button_score >= best_full_score:
            best_idx = best_button_idx
            best_score = best_button_score
            matched_text = self.faq_button_labels[best_idx]
            match_type = "button_label"
        else:
            best_idx = best_full_idx
            best_score = best_full_score
            matched_text = self.faq_full_questions[best_idx]
            match_type = "full_question"
        
        print(f"🔍 Best match similarity: {best_score:.3f}")
        print(f"🔍 Match type: {match_type}")
        print(f"🔍 Matched text: {matched_text[:80]}...")
        print(f"🔍 Threshold: {threshold}")
        
        # Check if above threshold
        if best_score >= threshold:
            faq = self.faq_data[best_idx]
            answer = faq.get('answer', faq.get('short_answer', ''))
            
            # Add related links if available
            links = faq.get('related_links', '')
            if links:
                answer += "\n\n📎 **Related links:**"
                for link in links.split(';')[:2]:
                    link = link.strip()
                    if link:
                        answer += f"\n• {link}"
            
            print(f"✅ Answer found!")
            print(f"{'='*60}\n")
            
            return {
                'found': True,
                'answer': answer,
                'similarity': best_score,
                'matched_question': matched_text,
                'match_type': match_type,
                'confidence': 'high' if best_score >= 0.85 else 'medium'
            }
        else:
            print(f"❌ No match found (similarity too low)")
            print(f"   Button label best: {best_button_score:.3f}")
            print(f"   Full question best: {best_full_score:.3f}")
            print(f"{'='*60}\n")
            
            return {
                'found': False,
                'answer': None,
                'similarity': best_score,
                'matched_question': matched_text,
                'match_type': match_type,
                'confidence': 'low'
            }


# Global instance
_faq_handler = None


def get_faq_handler(csv_path: str = None):
    """Get or create FAQ handler instance"""
    global _faq_handler
    
    if _faq_handler is None and csv_path:
        _faq_handler = SimpleFAQHandler(csv_path)
    
    return _faq_handler