from django.db import models

class Agent(models.Model):
    AGENT_TYPE_CHOICES = [
        ('sql', 'SQL Agent'),
        ('rag', 'RAG Agent'),
        ('action', 'Action Agent'),
    ]

    name = models.CharField(max_length=255)
    description = models.TextField()
    agent_type = models.CharField(max_length=10, choices=AGENT_TYPE_CHOICES)
    configuration = models.JSONField()

    def __str__(self):
        return self.name

class SQLAgent(Agent):
    query_template = models.TextField()

class RAGAgent(Agent):
    retrieval_model = models.CharField(max_length=255)

class ActionAgent(Agent):
    action_list = models.JSONField()