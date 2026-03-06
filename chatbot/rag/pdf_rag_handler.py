"""
PDF RAG Handler - Answers questions using PDF documents
UPDATED: Better LLM prompt for author extraction
"""
import os
import time
from .pdf_vector_store import get_pdf_vector_store


class PDFRAGHandler:
    """
    Handles RAG queries for PDF documents
    """
    
    def __init__(self, use_llm=True):
        """
        Initialize PDF RAG handler
        
        Args:
            use_llm: Try LLM generation, fallback to template
        """
        self.vector_store = get_pdf_vector_store()
        self.use_llm = use_llm
        
        if self.use_llm:
            self.api_key = os.getenv('OPENAI_API_KEY')
            if self.api_key:
                print("✅ OpenAI API key found - LLM enabled")
            else:
                print("⚠️ No OpenAI API key - Using template mode")
                self.use_llm = False
    
    def answer(self, user_question: str, top_k: int = 3, threshold: float = 0.5):
        """
        Answer user question using PDF documents
        
        Args:
            user_question: User's question
            top_k: Number of PDF chunks to retrieve
            threshold: Minimum similarity
            
        Returns:
            dict with 'found', 'answer', 'sources', 'timing', 'cost'
        """
        start_time = time.time()
        
        print(f"\n{'='*60}")
        print(f"📄 PDF RAG Query: {user_question}")
        print(f"   Threshold: {threshold}")
        print(f"{'='*60}")
        
        # Step 1: Search PDF chunks
        try:
            results = self.vector_store.search(user_question, top_k=top_k)
        except Exception as e:
            print(f"❌ PDF search failed: {e}")
            return self._error_response()
        
        search_time = time.time() - start_time
        
        # Step 2: Check threshold
        if not results or results[0]['similarity'] < threshold:
            print(f"❌ No relevant content found")
            print(f"   Best similarity: {results[0]['similarity']:.3f}" if results else "No results")
            print(f"   Threshold: {threshold}")
            return self._no_results_response(search_time)
        
        # Step 3: Found relevant content!
        print(f"✅ Found {len(results)} relevant sections:")
        for i, r in enumerate(results, 1):
            chunk = r['chunk']
            print(f"   {i}. {chunk['source']} (page {chunk['page']}, similarity: {r['similarity']:.3f})")
        
        # Step 4: Format context
        gen_start = time.time()
        context = self._format_context(results)
        
        # Step 5: Generate answer
        llm_cost = 0.0
        answer_method = "template"
        
        if self.use_llm and self.api_key:
            print("🤖 Attempting LLM generation...")
            llm_answer = self._generate_llm_answer(user_question, context)
            
            if llm_answer:
                answer = llm_answer
                llm_cost = 0.0001
                answer_method = "llm"
                print("✅ LLM generation successful")
            else:
                answer = self._generate_template_answer(results)
                answer_method = "template_fallback"
                print("⚠️ LLM failed, using template")
        else:
            answer = self._generate_template_answer(results)
            print("📝 Using template (no LLM)")
        
        generation_time = time.time() - gen_start
        total_time = time.time() - start_time
        
        print(f"✅ Answer generated via {answer_method}")
        print(f"⏱️  Timing: search={search_time*1000:.0f}ms, gen={generation_time*1000:.0f}ms, total={total_time*1000:.0f}ms")
        print(f"💰 Cost: ${llm_cost:.6f}")
        print(f"{'='*60}\n")
        
        return {
            'found': True,
            'answer': answer,
            'answer_method': answer_method,
            'sources': [r['chunk'] for r in results],
            'top_similarity': results[0]['similarity'],
            'timing': {
                'search_ms': search_time * 1000,
                'generation_ms': generation_time * 1000,
                'total_ms': total_time * 1000
            },
            'cost': {
                'llm_cost': llm_cost,
                'total_cost': llm_cost
            }
        }
    
    def _format_context(self, results):
        """Format PDF chunks into context"""
        context_parts = []
        
        for i, result in enumerate(results, 1):
            chunk = result['chunk']
            context_parts.append(
                f"[Source {i}: {chunk['source']}, Page {chunk['page']}]\n"
                f"{chunk['text']}"
            )
        
        return "\n\n".join(context_parts)
    
    def _generate_llm_answer(self, question, context):
        """
        Generate answer using LLM with improved prompt for author extraction
        
        ✨ NEW: Better prompt that handles author questions properly
        """
        try:
            from openai import OpenAI
            
            client = OpenAI(api_key=self.api_key)
            
            # ✅ IMPROVED PROMPT - Better for extracting authors and detailed information
            prompt = f"""You are a research assistant helping users understand the NORMAN Suspect List Exchange (NORMAN-SLE) scientific paper.

Context from the paper:
{context}

User Question: {question}

Instructions:
1. **For questions about AUTHORS or CONTRIBUTORS:**
   - Extract ALL names you find (format: FirstName LastName)
   - Include affiliations if mentioned (e.g., "University of Luxembourg")
   - If you see "et al." or "over X contributors", include that
   - Look for patterns like: "authored by", "contributors", names followed by institutions
   - Example good answer: "The paper was authored by John Smith (MIT), Jane Doe (Stanford), and over 50 other contributors from institutions worldwide."

2. **For questions about PUBLICATION details:**
   - Include journal name, year, volume, DOI if present
   - Mention if it's open access

3. **For questions about CONTENT:**
   - Provide comprehensive answers with specific details
   - Include numbers, dates, and technical terms
   - Cite the source page if relevant

4. **If the context does NOT contain the answer:**
   - Say: "The provided excerpts do not contain information about [topic]"
   - Suggest what information IS available

5. **Formatting:**
   - Use clear paragraphs
   - Use **bold** for key terms
   - Keep it conversational but informative

Answer:"""
            
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {
                        "role": "system", 
                        "content": "You are a helpful research assistant specialized in extracting information from scientific papers. You are thorough and extract all relevant details, especially names and affiliations when asked about authors."
                    },
                    {
                        "role": "user", 
                        "content": prompt
                    }
                ],
                temperature=0.2,  # ✅ Lower temperature for more factual responses
                max_tokens=600,    # ✅ Increased for longer author lists
            )
            
            return response.choices[0].message.content.strip()
            
        except Exception as e:
            print(f"⚠️ LLM error: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    def _generate_template_answer(self, results):
        """Generate template answer"""
        top = results[0]['chunk']
        
        answer = f"**From: {top['source']} (Page {top['page']})**\n\n"
        answer += f"{top['text'][:500]}...\n\n"
        
        if len(results) > 1:
            answer += "**Related sections:**\n"
            for r in results[1:]:
                answer += f"• {r['chunk']['source']} (Page {r['chunk']['page']})\n"
        
        return answer
    
    def _no_results_response(self, search_time):
        """Return no results response"""
        return {
            'found': False,
            'answer': (
                "I couldn't find relevant information in the documents.\n\n"
                "Try:\n"
                "• Rephrasing your question\n"
                "• Being more specific\n"
                "• Browsing FAQ categories"
            ),
            'sources': [],
            'timing': {
                'search_ms': search_time * 1000,
                'generation_ms': 0,
                'total_ms': search_time * 1000
            },
            'cost': {
                'llm_cost': 0.0,
                'total_cost': 0.0
            }
        }
    
    def _error_response(self):
        """Return error response"""
        return {
            'found': False,
            'answer': "Error searching documents. Please try again.",
            'sources': [],
            'timing': {'search_ms': 0, 'generation_ms': 0, 'total_ms': 0},
            'cost': {'llm_cost': 0.0, 'total_cost': 0.0}
        }


# Global instance
_pdf_rag_handler = None


def get_pdf_rag_handler(use_llm=True):
    """Get or create PDF RAG handler instance"""
    global _pdf_rag_handler
    if _pdf_rag_handler is None:
        _pdf_rag_handler = PDFRAGHandler(use_llm=use_llm)
    return _pdf_rag_handler