from functools import wraps
from django.http import HttpResponseForbidden

def require_role(*roles):
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            try:
                user_role = request.user.userprofile.role
                if user_role not in roles:
                    return HttpResponseForbidden("Accès interdit")
            except:
                return HttpResponseForbidden("Accès interdit")
            return view_func(request, *args, **kwargs)
        return wrapper
    return decorator

# Utilisation dans views.py
@require_role('admin', 'editor')
def create_chatbot(request): ...

@require_role('admin')
def manage_users(request): ...