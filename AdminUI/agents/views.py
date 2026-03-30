from django.shortcuts import render, get_object_or_404
from django.http import JsonResponse
from .models import Agent
from .serializers import AgentSerializer

def agent_list(request):
    agents = Agent.objects.all()
    return render(request, 'agents/agent_list.html', {'agents': agents})

def agent_detail(request, pk):
    agent = get_object_or_404(Agent, pk=pk)
    return render(request, 'agents/agent_detail.html', {'agent': agent})

def agent_create(request):
    if request.method == 'POST':
        serializer = AgentSerializer(data=request.POST)
        if serializer.is_valid():
            serializer.save()
            return JsonResponse(serializer.data, status=201)
    return render(request, 'agents/agent_form.html')

def agent_update(request, pk):
    agent = get_object_or_404(Agent, pk=pk)
    if request.method == 'POST':
        serializer = AgentSerializer(agent, data=request.POST)
        if serializer.is_valid():
            serializer.save()
            return JsonResponse(serializer.data)
    return render(request, 'agents/agent_form.html', {'agent': agent})

def agent_delete(request, pk):
    agent = get_object_or_404(Agent, pk=pk)
    agent.delete()
    return JsonResponse({'message': 'Agent deleted successfully'}, status=204)