import os
from pathlib import Path
import environ

BASE_DIR = Path(__file__).resolve().parent.parent

env = environ.Env()
environ.Env.read_env(BASE_DIR / ".env")

SUPABASE_PROJECT_ID = env("VITE_SUPABASE_PROJECT_ID", default="nggndpmbclssomtmrofs")
SUPABASE_URL = env("VITE_SUPABASE_URL", default="https://nggndpmbclssomtmrofs.supabase.co")
SUPABASE_PUBLISHABLE_KEY = env("VITE_SUPABASE_PUBLISHABLE_KEY", default="")


SUPABASE_SERVICE_KEY = env("SUPABASE_SERVICE_KEY", default="")
if not SUPABASE_SERVICE_KEY:
    print("⚠️ ATTENTION: SUPABASE_SERVICE_KEY n'est pas définie dans .env")
    print("   Le service Supabase ne pourra pas fonctionner correctement.")

SQL_AGENT_BASE_URL = env("SQL_AGENT_BASE_URL", default="http://localhost:8006")
RAG_AGENT_BASE_URL = env("RAG_AGENT_BASE_URL", default="http://localhost:8005")
RAG_AGENT_ADMIN_API_KEY = env("akwa_admin_secret_2025", default="")
MICROSERVICE_TIMEOUT_SECONDS = env.int("MICROSERVICE_TIMEOUT_SECONDS", default=90)
SECRET_KEY = 'django-insecure-your-secret-key-here-change-in-production'

DEBUG = True

ALLOWED_HOSTS = [
    'localhost',
    '127.0.0.1',
    'host.docker.internal',
]

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    
    # Third party
    'crispy_forms',
    'crispy_tailwind',
    'corsheaders',

    'django_htmx', 
    
    # Local apps
    'dashboard',
]

MIDDLEWARE = [
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'django_htmx.middleware.HtmxMiddleware',
]

ROOT_URLCONF = 'meta_chatbot.urls'

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

WSGI_APPLICATION = 'meta_chatbot.wsgi.application'

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
}

AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]

LANGUAGE_CODE = 'en-us'

TIME_ZONE = 'UTC'

USE_I18N = True

USE_TZ = True

STATIC_URL = '/static/'
STATICFILES_DIRS = [BASE_DIR / 'static']
STATIC_ROOT = BASE_DIR / 'staticfiles'

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# Crispy Forms
CRISPY_ALLOWED_TEMPLATE_PACKS = "tailwind"
CRISPY_TEMPLATE_PACK = "tailwind"

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
        },
    },
    'loggers': {
        'api.gateway': {
            'handlers': ['console'],
            'level': 'DEBUG',
            'propagate': True,
        },
    },
}

CORS_ALLOWED_ORIGINS = [
    "http://localhost:8080",
    "http://127.0.0.1:8080",
]