from django.contrib import admin
from django.urls import path, include
from django.contrib.auth import views as auth_views
from django.conf import settings
from django.conf.urls.static import static
from django.views.generic import RedirectView
from core.views import platform_config_api, user_chatbots_api
from django.http import JsonResponse


def health_check(request):                    # ← AJOUTER la fonction ici
    return JsonResponse({"status": "ok", "service": "django"})

urlpatterns = [
    path('health/', health_check, name='health'),
    # Redirection de la racine "/" vers admin
    path('', RedirectView.as_view(url='/admin/', permanent=True)),
    
    # Déconnexion qui redirige vers la page de login
    path('admin/logout/', auth_views.LogoutView.as_view(next_page='/admin/login/'), name='admin_logout'),
    
    # Admin principal
    path('admin/', admin.site.urls),
    # ← NOUVEAU : endpoints internes pour le Auth Gateway
    # ⚠️ Ces routes sont protégées par X-Internal-Secret
    # ⚠️ Nginx doit bloquer /internal/* depuis l'extérieur
    path('internal/config/',                    platform_config_api,  name='platform_config'),
    path('internal/user-chatbots/<str:user_id>/', user_chatbots_api,  name='user_chatbots'),
]

# Servir les fichiers statiques et media en développement
if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)