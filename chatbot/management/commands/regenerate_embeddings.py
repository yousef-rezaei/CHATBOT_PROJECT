# File 7: chatbot/management/commands/regenerate_embeddings.py
"""
Django Management Command
Manually regenerate FAQ embeddings
"""

from django.core.management.base import BaseCommand
from chatbot.views import get_semantic_router


class Command(BaseCommand):
    help = 'Regenerate FAQ embeddings (clears cache and rebuilds)'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--force',
            action='store_true',
            help='Force regeneration even if cache is valid',
        )
    
    def handle(self, *args, **options):
        self.stdout.write("=" * 60)
        self.stdout.write(self.style.SUCCESS('Regenerating FAQ Embeddings'))
        self.stdout.write("=" * 60)
        
        try:
            router = get_semantic_router()
            
            if not router:
                self.stdout.write(self.style.ERROR('❌ Router not initialized'))
                return
            
            # Show cache info before
            cache_info = router.get_cache_info()
            if cache_info['exists']:
                self.stdout.write(f"Current cache:")
                self.stdout.write(f"  FAQs: {cache_info['count']}")
                self.stdout.write(f"  Model: {cache_info['model_version']}")
                self.stdout.write(f"  Created: {cache_info['created_at']}")
            
            # Regenerate
            self.stdout.write("\n🔄 Regenerating...")
            router.reload()
            
            # Show cache info after
            cache_info = router.get_cache_info()
            self.stdout.write("\n" + "=" * 60)
            self.stdout.write(self.style.SUCCESS('✅ Regeneration Complete!'))
            self.stdout.write("=" * 60)
            self.stdout.write(f"FAQs: {cache_info['count']}")
            self.stdout.write(f"Dimensions: {cache_info['dimensions']}")
            self.stdout.write(f"File size: {cache_info['file_size_kb']:.1f} KB")
            self.stdout.write(f"Cache file: {cache_info['file_path']}")
            
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'❌ Error: {e}'))
            import traceback
            traceback.print_exc()