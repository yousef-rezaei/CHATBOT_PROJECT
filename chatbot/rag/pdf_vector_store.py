from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity
import numpy as np
import pickle
import os
from pathlib import Path

try:
    import PyPDF2
except ImportError:
    print("⚠️ PyPDF2 not installed. Run: pip install PyPDF2")


class PDFVectorStore:
     
    def __init__(self, cache_dir='cache/pdf_rag'):
        self.cache_dir = cache_dir
        self.embeddings_file = os.path.join(cache_dir, 'pdf_embeddings.npy')
        self.metadata_file = os.path.join(cache_dir, 'pdf_metadata.pkl')
        
        self.model = SentenceTransformer('BAAI/bge-base-en-v1.5')
        
        self.embeddings = None
        self.chunks = []  # List of {text, source, page, chunk_id}
    
    def build_from_pdfs(self, pdf_folder: str, chunk_size: int = 500):
      
        print(f"🔄 Building PDF vector store from: {pdf_folder}")
        
        pdf_files = list(Path(pdf_folder).glob('*.pdf'))
        
        if not pdf_files:
            print(f"⚠️ No PDF files found in {pdf_folder}")
            return
        
        print(f"📚 Found {len(pdf_files)} PDF files")
        
        all_texts = []
        all_chunks = []
        
        for pdf_path in pdf_files:
            print(f"   Processing: {pdf_path.name}")
            
            try:
                # Extract text from PDF
                with open(pdf_path, 'rb') as file:
                    pdf_reader = PyPDF2.PdfReader(file)
                    
                    for page_num, page in enumerate(pdf_reader.pages, 1):
                        text = page.extract_text()
                        
                        if not text.strip():
                            continue
                        
                        # Split into chunks
                        chunks = self._split_into_chunks(text, chunk_size)
                        
                        for chunk_idx, chunk_text in enumerate(chunks):
                            all_texts.append(chunk_text)
                            all_chunks.append({
                                'text': chunk_text,
                                'source': pdf_path.name,
                                'page': page_num,
                                'chunk_id': f"{pdf_path.stem}_p{page_num}_c{chunk_idx}"
                            })
                
                print(f"      ✅ Extracted {len([c for c in all_chunks if c['source'] == pdf_path.name])} chunks")
                
            except Exception as e:
                print(f"      ❌ Error processing {pdf_path.name}: {e}")
        
        if not all_texts:
            print("❌ No text extracted from PDFs")
            return
        
        # Generate embeddings
        print(f"\n🧮 Generating embeddings for {len(all_texts)} chunks...")
        self.embeddings = self.model.encode(
            all_texts,
            show_progress_bar=True,
            convert_to_numpy=True,
            batch_size=32
        )
        
        self.chunks = all_chunks
        
        print(f"✅ Created embeddings: shape {self.embeddings.shape}")
        
        # Save to cache
        self._save_cache()
    
    def _split_into_chunks(self, text: str, chunk_size: int) -> list:
        """Split text into overlapping chunks"""
        # Split by sentences/paragraphs for better context
        sentences = text.replace('\n', ' ').split('. ')
        
        chunks = []
        current_chunk = ""
        
        for sentence in sentences:
            if len(current_chunk) + len(sentence) < chunk_size:
                current_chunk += sentence + ". "
            else:
                if current_chunk:
                    chunks.append(current_chunk.strip())
                current_chunk = sentence + ". "
        
        if current_chunk:
            chunks.append(current_chunk.strip())
        
        return chunks
    
    def load_from_cache(self):
        """Load pre-built embeddings from cache"""
        if not os.path.exists(self.embeddings_file):
            return False
        
        print("📦 Loading PDF embeddings from cache...")
        self.embeddings = np.load(self.embeddings_file)
        
        with open(self.metadata_file, 'rb') as f:
            self.chunks = pickle.load(f)
        
        print(f"✅ Loaded {len(self.chunks)} PDF chunks")
        return True
    
    def _save_cache(self):
        """Save embeddings to cache"""
        os.makedirs(self.cache_dir, exist_ok=True)
        
        np.save(self.embeddings_file, self.embeddings)
        
        with open(self.metadata_file, 'wb') as f:
            pickle.dump(self.chunks, f)
        
        print("💾 PDF embeddings cached")
    
    def search(self, query: str, top_k: int = 3):
     
        if self.embeddings is None:
            raise ValueError("PDF vector store not initialized")
        
        # Convert query to embedding
        query_embedding = self.model.encode(query, convert_to_numpy=True)
        
        # Calculate similarities
        similarities = cosine_similarity(
            [query_embedding],
            self.embeddings
        )[0]
        
        # Get top-k indices
        top_indices = np.argsort(similarities)[::-1][:top_k]
        
        # Return chunks with scores
        results = []
        for idx in top_indices:
            results.append({
                'chunk': self.chunks[idx],
                'similarity': float(similarities[idx])
            })
        
        return results


# Global instance
_pdf_vector_store = None


def get_pdf_vector_store():
    """Get or create PDF vector store instance"""
    global _pdf_vector_store
    if _pdf_vector_store is None:
        _pdf_vector_store = PDFVectorStore()
    return _pdf_vector_store