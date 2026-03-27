from pathlib import Path
from dotenv import load_dotenv
import os

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = os.getenv('SECRET_KEY', 'django-insecure-x+7u_#i(&2+3z442p8%l!6vwwrontztb!0sk^5*uo4ka@wwcxo')
AUTH_GATEWAY_URL    = os.getenv("AUTH_GATEWAY_URL",    "http://auth-gateway:9000")
INTERNAL_API_SECRET = os.getenv("INTERNAL_API_SECRET", "change_me_in_production")

DEBUG = True
OLLAMA_URL  = "https://baker-spoken-directive-exactly.trycloudflare.com"
QDRANT_HOST = "localhost"
QDRANT_PORT = 6333
QDRANT_COLLECTION = "allogaz_docs"

EMBED_MODEL = "qwen3:8b" 

ALLOWED_HOSTS = [
    "127.0.0.1",
    "localhost",
    "host.docker.internal",
    ".trycloudflare.com",
]

CSRF_TRUSTED_ORIGINS = [
    "https://*.trycloudflare.com",
]

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'rest_framework',
    'nested_admin',
    'core',
]



MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'chatbot_plateform.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

# CORRECTION: Configuration STATIC et MEDIA
STATIC_URL = '/static/'
STATICFILES_DIRS = [BASE_DIR / 'static']  # Dossier pour les fichiers statiques en dev
STATIC_ROOT = BASE_DIR / 'staticfiles'     # Dossier pour collectstatic

MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

WSGI_APPLICATION = 'chatbot_plateform.wsgi.application'

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': os.getenv('DB_NAME', 'chatbot_db'),
        'USER': os.getenv('DB_USER', 'chatbot_user'),
        'PASSWORD': os.getenv('DB_PASSWORD', 'motdepasse123'),
        'HOST': os.getenv('DB_HOST', 'localhost'),
        'PORT': os.getenv('DB_PORT', '5432'),
    }
}

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

LANGUAGE_CODE = 'fr-fr'
TIME_ZONE = 'Africa/Casablanca'
USE_I18N = True
USE_TZ = True

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'


# URLs de redirection
LOGIN_URL = '/admin/login/'
LOGIN_REDIRECT_URL = '/admin/'
LOGOUT_URL = '/admin/logout/'
LOGOUT_REDIRECT_URL = '/admin/login/'

PLATFORM_NAME       = "Afriquia"
KEYCLOAK_URL = "http://localhost:8080"
KEYCLOAK_REALM      = os.getenv("KEYCLOAK_REALM",     "Afriquia-Realm")
KEYCLOAK_CLIENT_ID  = os.getenv("KEYCLOAK_CLIENT_ID", "Afriquia-frontend")
KEYCLOAK_AUDIENCE   = os.getenv("KEYCLOAK_AUDIENCE",  "Afriquia-backend")
ORCHESTRATOR_URL    = os.getenv("ORCHESTRATOR_URL",   "http://orchestrator:8000")
JWKS_CACHE_TTL      = int(os.getenv("JWKS_CACHE_TTL", "3600"))