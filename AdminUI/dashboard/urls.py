from django.urls import path
from . import views

app_name = 'dashboard'

urlpatterns = [
    path('', views.index, name='index'),
    path('chatbot/create/', views.chatbot_create, name='chatbot_create'),
    path('chatbot/<int:pk>/', views.chatbot_detail, name='chatbot_detail'),
    path('chatbot/<int:pk>/edit/', views.chatbot_edit, name='chatbot_edit'),
    path('chatbot/<int:pk>/delete/', views.chatbot_delete, name='chatbot_delete'),
    
    # HTMX endpoints for dynamic rows
    path('htmx/add-sql-row/', views.add_sql_row, name='add_sql_row'),
    path('htmx/add-action-row/', views.add_action_row, name='add_action_row'),
    path('chatbot/<int:pk>/rag/upload/', views.rag_upload_document, name='rag_upload_document'),
]