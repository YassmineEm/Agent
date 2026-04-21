from django.urls import path
from . import views
from .views import chatbots_sql_list

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

    # Test endpoints for agents
    path('chatbot/<int:pk>/test/sql/', views.test_sql_agent, name='test_sql_agent'),
    path('chatbot/<int:pk>/test/rag/', views.test_rag_agent, name='test_rag_agent'),

    path('api/chatbots/', views.list_chatbots, name='list_chatbots'),
    path('api/chatbots/<int:chat_id>/', views.chatbot_config, name='chatbot_config'),

    path('api/chatbots/sql/', chatbots_sql_list, name='chatbots-sql-list'),

    # ── User Management
    path('users/', views.user_list, name='user_list'),
    path('user/<str:user_id>/', views.user_detail, name='user_detail'),
    path('user/<str:user_id>/sync-supabase/', views.sync_user_supabase, name='sync_user_supabase'),
    path('user/<str:user_id>/add-chatbot/', views.user_add_chatbot, name='user_add_chatbot'),
    path('user/<str:user_id>/remove-chatbot/<int:chatbot_id>/', views.user_remove_chatbot, name='user_remove_chatbot'),
]