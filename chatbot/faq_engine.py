import csv
import re
from difflib import SequenceMatcher
from typing import List, Dict, Optional, Tuple
import os


class FAQEngine:
    """
    Intelligent FAQ matching engine with keyword search and semantic similarity
    """
    
    def __init__(self, csv_path: str = None):
        """
        Initialize FAQ engine with CSV data
        
        Args:
            csv_path: Path to FAQ CSV file
        """
        self.faqs = []
        self.keywords_index = {}
        
        if csv_path and os.path.exists(csv_path):
            self.load_csv(csv_path)
    
    def load_csv(self, csv_path: str) -> None:
        """
        Load FAQ data from CSV file
        
        Args:
            csv_path: Path to CSV file
        """
        try:
            with open(csv_path, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                self.faqs = list(reader)
            
            # Build keyword index for fast search
            self._build_keyword_index()
            
            print(f"✅ Loaded {len(self.faqs)} FAQ entries")
            
        except Exception as e:
            print(f"❌ Error loading FAQ CSV: {e}")
            self.faqs = []
    
    def _build_keyword_index(self) -> None:
        """
        Build inverted index for fast keyword lookup
        """
        self.keywords_index = {}
        
        for idx, faq in enumerate(self.faqs):
            # Only process active FAQs
            if faq.get('is_active', 'TRUE').upper() == 'TRUE':
                # Extract keywords from keywords field
                keywords = faq.get('keywords', '').lower().split(';')
                
                # Also add words from question and title
                question_words = self._extract_keywords(faq.get('question', ''))
                title_words = self._extract_keywords(faq.get('faq_title', ''))
                
                all_keywords = keywords + question_words + title_words
                
                # Index each keyword
                for keyword in all_keywords:
                    keyword = keyword.strip()
                    if keyword and len(keyword) > 2:  # Skip very short words
                        if keyword not in self.keywords_index:
                            self.keywords_index[keyword] = []
                        self.keywords_index[keyword].append(idx)
    
    def _extract_keywords(self, text: str) -> List[str]:
        """
        Extract meaningful keywords from text
        
        Args:
            text: Input text
            
        Returns:
            List of keywords
        """
        # Remove punctuation and split
        text = re.sub(r'[^\w\s-]', ' ', text.lower())
        words = text.split()
        
        # Filter out common stop words
        stop_words = {
            'the', 'is', 'are', 'was', 'were', 'a', 'an', 'and', 'or', 'but',
            'in', 'on', 'at', 'to', 'for', 'of', 'with', 'by', 'from', 'as',
            'this', 'that', 'these', 'those', 'what', 'which', 'who', 'when',
            'where', 'why', 'how', 'do', 'does', 'did', 'can', 'could', 'should',
            'would', 'i', 'you', 'he', 'she', 'it', 'we', 'they'
        }
        
        return [w for w in words if w not in stop_words and len(w) > 2]
    
    def _calculate_similarity(self, str1: str, str2: str) -> float:
        """
        Calculate similarity between two strings (0.0 to 1.0)
        
        Args:
            str1: First string
            str2: Second string
            
        Returns:
            Similarity score
        """
        return SequenceMatcher(None, str1.lower(), str2.lower()).ratio()
    
    def search_by_keywords(self, user_query: str, top_n: int = 5) -> List[Tuple[Dict, float]]:
        """
        Search FAQs using keyword matching
        
        Args:
            user_query: User's question
            top_n: Number of top results to return
            
        Returns:
            List of (faq, score) tuples
        """
        query_keywords = self._extract_keywords(user_query)
        
        # Score each FAQ
        faq_scores = {}
        
        for keyword in query_keywords:
            # Exact match
            if keyword in self.keywords_index:
                for faq_idx in self.keywords_index[keyword]:
                    faq_scores[faq_idx] = faq_scores.get(faq_idx, 0) + 2.0
            
            # Partial match (fuzzy)
            for indexed_keyword, faq_indices in self.keywords_index.items():
                if keyword in indexed_keyword or indexed_keyword in keyword:
                    sim = self._calculate_similarity(keyword, indexed_keyword)
                    if sim > 0.7:  # 70% similarity threshold
                        for faq_idx in faq_indices:
                            faq_scores[faq_idx] = faq_scores.get(faq_idx, 0) + sim
        
        # Get top N FAQs
        sorted_faqs = sorted(
            faq_scores.items(), 
            key=lambda x: x[1], 
            reverse=True
        )[:top_n]
        
        return [(self.faqs[idx], score) for idx, score in sorted_faqs]
    
    def search_by_question_similarity(self, user_query: str, top_n: int = 5) -> List[Tuple[Dict, float]]:
        """
        Search FAQs by comparing user query to stored questions
        
        Args:
            user_query: User's question
            top_n: Number of top results to return
            
        Returns:
            List of (faq, score) tuples
        """
        results = []
        
        for faq in self.faqs:
            if faq.get('is_active', 'TRUE').upper() != 'TRUE':
                continue
            
            question = faq.get('question', '')
            title = faq.get('faq_title', '')
            
            # Calculate similarity to both question and title
            q_sim = self._calculate_similarity(user_query, question)
            t_sim = self._calculate_similarity(user_query, title)
            
            # Use the higher similarity
            score = max(q_sim, t_sim)
            
            if score > 0.3:  # Minimum threshold
                results.append((faq, score))
        
        # Sort by score and return top N
        results.sort(key=lambda x: x[1], reverse=True)
        return results[:top_n]
    
    def search_by_category(self, category: str) -> List[Dict]:
        """
        Get all FAQs in a category
        
        Args:
            category: Category name
            
        Returns:
            List of FAQs
        """
        results = []
        category_lower = category.lower()
        
        for faq in self.faqs:
            if faq.get('is_active', 'TRUE').upper() != 'TRUE':
                continue
            
            cat1 = faq.get('category_lvl1', '').lower()
            cat2 = faq.get('category_lvl2', '').lower()
            
            if category_lower in cat1 or category_lower in cat2:
                results.append(faq)
        
        return results
    
    def get_answer(self, user_query: str, confidence_threshold: float = 0.5) -> Optional[Dict]:
        """
        Get best answer for user query
        
        Args:
            user_query: User's question
            confidence_threshold: Minimum confidence to return answer
            
        Returns:
            Best matching FAQ or None
        """
        # Try keyword search first (usually faster and more accurate)
        keyword_results = self.search_by_keywords(user_query, top_n=3)
        
        # Try question similarity search
        similarity_results = self.search_by_question_similarity(user_query, top_n=3)
        
        # Combine results
        all_results = {}
        
        for faq, score in keyword_results:
            faq_id = faq.get('id')
            all_results[faq_id] = all_results.get(faq_id, 0) + score * 1.5  # Weight keywords higher
        
        for faq, score in similarity_results:
            faq_id = faq.get('id')
            all_results[faq_id] = all_results.get(faq_id, 0) + score
        
        # Get best match
        if all_results:
            best_faq_id = max(all_results, key=all_results.get)
            best_score = all_results[best_faq_id]
            
            # Normalize score (rough estimate)
            normalized_score = min(best_score / 5.0, 1.0)
            
            if normalized_score >= confidence_threshold:
                # Find the FAQ
                for faq in self.faqs:
                    if faq.get('id') == best_faq_id:
                        return {
                            'faq': faq,
                            'confidence': normalized_score,
                            'answer': faq.get('answer', faq.get('short_answer', '')),
                            'related_links': faq.get('related_links', '').split(';')
                        }
        
        return None
    
    def get_categories(self) -> List[str]:
        """
        Get all unique categories
        
        Returns:
            List of category names
        """
        categories = set()
        
        for faq in self.faqs:
            if faq.get('is_active', 'TRUE').upper() == 'TRUE':
                cat1 = faq.get('category_lvl1', '').strip()
                if cat1:
                    categories.add(cat1)
        
        return sorted(list(categories))
    
    def get_quick_buttons(self, top_n: int = 6) -> List[Dict]:
        """
        Get quick action buttons (high priority FAQs)
        
        Args:
            top_n: Number of buttons to return
            
        Returns:
            List of button data
        """
        buttons = []
        
        for faq in self.faqs:
            if faq.get('is_active', 'TRUE').upper() != 'TRUE':
                continue
            
            priority = faq.get('priority', 'low').lower()
            if priority == 'high':
                buttons.append({
                    'id': faq.get('id'),
                    'label': faq.get('button_label', faq.get('faq_title', '')),
                    'category': faq.get('category_lvl1', ''),
                    'order': int(faq.get('top_button_order', 999))
                })
        
        # Sort by order
        buttons.sort(key=lambda x: x['order'])
        
        return buttons[:top_n]
    
    def get_categories_with_questions(self):
        """Get all categories with their questions"""
        categories = {}
        
        for faq in self.faqs:
            category = faq.get('category_lvl1', 'Other')
            
            if category not in categories:
                categories[category] = []
            
            categories[category].append(faq)
        
        # Sort questions within each category
        for category in categories:
            categories[category].sort(
                key=lambda x: int(x.get('sub_button_order', 999))
            )
        
        return categories


# Global FAQ engine instance
faq_engine = None


def initialize_faq_engine(csv_path: str) -> FAQEngine:
    """
    Initialize global FAQ engine
    
    Args:
        csv_path: Path to FAQ CSV file
        
    Returns:
        FAQ engine instance
    """
    global faq_engine
    faq_engine = FAQEngine(csv_path)
    return faq_engine


def get_faq_engine() -> Optional[FAQEngine]:
    """
    Get global FAQ engine instance
    
    Returns:
        FAQ engine or None
    """
    return faq_engine

