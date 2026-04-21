# test_supabase.py
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'meta_chatbot.settings')
django.setup()

from dashboard.services.supabase_service import get_supabase_users, get_supabase_admin

def test():
    print("🔄 Test de connexion à Supabase...")
    
    try:
        # Tester directement l'appel API
        supabase = get_supabase_admin()
        response = supabase.auth.admin.list_users()
        
        print(f"📊 Type de réponse : {type(response)}")
        
        # Vérifier la structure exacte
        if isinstance(response, list):
            print(f"✅ La réponse est une liste de {len(response)} éléments")
            users = response
        elif hasattr(response, 'users'):
            print(f"✅ La réponse a un attribut 'users' avec {len(response.users)} éléments")
            users = response.users
        else:
            print(f"❌ Structure inattendue : {response}")
            users = []
        
        print(f"\n📊 {len(users)} utilisateur(s) trouvé(s)")
        for user in users:
            print(f"   - {user.email} ({user.id})")
            
    except Exception as e:
        print(f"❌ Erreur : {e}")

if __name__ == "__main__":
    test()