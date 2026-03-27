from django.apps import AppConfig

class ChatbotConfig(AppConfig):
    name = "core"              

    def ready(self):
        import core.signals   