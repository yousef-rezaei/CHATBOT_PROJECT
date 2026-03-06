# chatbot/management/commands/build_pdf_rag.py

from django.core.management.base import BaseCommand
from chatbot.rag.pdf_vector_store import get_pdf_vector_store
import os


class Command(BaseCommand):
    help = 'Build PDF RAG vector store from documents folder'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--folder',
            type=str,
            default='chatbot/documents',
            help='Folder containing PDF files'
        )
        
        parser.add_argument(
            '--chunk-size',
            type=int,
            default=500,
            help='Size of text chunks'
        )
    
    def handle(self, *args, **options):
        folder = options['folder']
        chunk_size = options['chunk_size']
        
        self.stdout.write(self.style.SUCCESS('\n' + '='*60))
        self.stdout.write(self.style.SUCCESS('📄 Building PDF RAG Vector Store'))
        self.stdout.write(self.style.SUCCESS('='*60 + '\n'))
        
        self.stdout.write(f"📁 PDF Folder: {folder}")
        self.stdout.write(f"📏 Chunk Size: {chunk_size} characters")
        
        # Build vector store
        vector_store = get_pdf_vector_store()
        
        try:
            vector_store.build_from_pdfs(folder, chunk_size=chunk_size)
            
            self.stdout.write(self.style.SUCCESS('\n' + '='*60))
            self.stdout.write(self.style.SUCCESS('✅ PDF RAG Built Successfully!'))
            self.stdout.write(self.style.SUCCESS('='*60))
            self.stdout.write(f"\n📈 Statistics:")
            self.stdout.write(f"   - Chunks indexed: {len(vector_store.chunks):,}")
            self.stdout.write(f"   - Embeddings shape: {vector_store.embeddings.shape}")
            self.stdout.write(f"   - Cache location: {vector_store.cache_dir}\n")
            
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'\n❌ Error: {e}'))
            import traceback
            traceback.print_exc()
            raise