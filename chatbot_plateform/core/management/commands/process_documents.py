from django.core.management.base import BaseCommand
from core.models import Document
from chatbot_runtime.rag_pipeline.pipeline import RAGPipeline


class Command(BaseCommand):
    help = "Traite tous les documents non indexés dans Qdrant"

    def handle(self, *args, **kwargs):
        pipeline = RAGPipeline()
        docs     = Document.objects.filter(is_processed=False)

        self.stdout.write(f"📄 {docs.count()} document(s) à traiter...")

        ok, ko = 0, 0
        for doc in docs:
            success = pipeline.process_document(doc)
            if success:
                ok += 1
            else:
                ko += 1

        self.stdout.write(f"\n✅ {ok} traités | ❌ {ko} erreurs")