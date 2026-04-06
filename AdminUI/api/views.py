from rest_framework import viewsets
from rest_framework.response import Response
from .serializers import AgentSerializer
from agents.models import Agent
from django.http import JsonResponse
from dashboard.models import Chatbot

class AgentViewSet(viewsets.ModelViewSet):
    queryset = Agent.objects.all()
    serializer_class = AgentSerializer

    def list(self, request):
        agents = self.get_queryset()
        serializer = self.get_serializer(agents, many=True)
        return Response(serializer.data)

    def retrieve(self, request, pk=None):
        agent = self.get_object()
        serializer = self.get_serializer(agent)
        return Response(serializer.data)

    def create(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        return Response(serializer.data, status=201)

    def update(self, request, pk=None):
        agent = self.get_object()
        serializer = self.get_serializer(agent, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)
        return Response(serializer.data)

    def destroy(self, request, pk=None):
        agent = self.get_object()
        self.perform_destroy(agent)
        return Response(status=204)


    def chatbots_sql_list(request):
        """
        Retourne UNIQUEMENT les chatbots avec sql_enabled=True
        ET au moins une sql_connection active.
        """
        chatbots = (
            Chatbot.objects
            .filter(sql_enabled=True, is_active=True)
            .prefetch_related('sql_connections')
        )

        result = []
        for bot in chatbots:
            active_dbs = bot.sql_connections.filter(is_active=True)
            if not active_dbs.exists():
                continue  # sql_enabled mais aucune DB configurée → on ignore

            result.append({
                "chatbot_id": str(bot.id),
                "chatbot_name": bot.name,
                "model_name": bot.sql_llm or bot.base_model,
                "databases": [
                    {
                        "db_id": db.db_id,          # property : chatbot_name_db_name
                        "db_name": db.db_name,
                        "connection_uri": db.connection_string,
                    }
                    for db in active_dbs
                ]
            })

        return JsonResponse({"chatbots": result})