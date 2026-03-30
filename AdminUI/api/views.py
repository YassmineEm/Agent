from rest_framework import viewsets
from rest_framework.response import Response
from .serializers import AgentSerializer
from agents.models import Agent

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