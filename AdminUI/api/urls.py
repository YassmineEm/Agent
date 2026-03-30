from django.urls import path
from .views import AgentListView, AgentDetailView, AgentCreateView, AgentUpdateView, AgentDeleteView

urlpatterns = [
    path('agents/', AgentListView.as_view(), name='agent-list'),
    path('agents/<int:pk>/', AgentDetailView.as_view(), name='agent-detail'),
    path('agents/create/', AgentCreateView.as_view(), name='agent-create'),
    path('agents/update/<int:pk>/', AgentUpdateView.as_view(), name='agent-update'),
    path('agents/delete/<int:pk>/', AgentDeleteView.as_view(), name='agent-delete'),
]