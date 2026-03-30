from django.contrib import admin
from .models import Agent

@admin.register(Agent)
class AgentAdmin(admin.ModelAdmin):
    list_display = ('name', 'description', 'role', 'scope', 'base_model')
    search_fields = ('name', 'description')
    list_filter = ('role', 'scope')