from pathlib import Path
import os
from dotenv import load_dotenv

load_dotenv()   # read backend/.env before we use os.getenv below

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# SECRET_KEY: from the environment in production; a dev fallback keeps local easy.
SECRET_KEY = os.getenv(
    "SECRET_KEY",
    "django-insecure-#&cwh!^psb)4!xh_(ys4e+1*5^q-=2a$q^g822d*@i&d$0wp39",
)

# DEBUG: on by default for local dev. SET DEBUG=False in production.
DEBUG = os.getenv("DEBUG", "True").lower() == "true"

# ALLOWED_HOSTS: comma-separated list from the environment (needed when DEBUG is
# False). Localhost is always allowed; Render sets RENDER_EXTERNAL_HOSTNAME itself.
ALLOWED_HOSTS = [h.strip() for h in os.getenv("ALLOWED_HOSTS", "").split(",") if h.strip()]
ALLOWED_HOSTS += ["localhost", "127.0.0.1"]
_render_host = os.getenv("RENDER_EXTERNAL_HOSTNAME")
if _render_host:
    ALLOWED_HOSTS.append(_render_host)

# Behind a host like Render, HTTPS is terminated at the proxy; trust its header.
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

# Application definition

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'rest_framework',   # DRF - our JSON API
    'corsheaders',      # lets React call the API
    'courses',          # our app (models + endpoints)
    'django.contrib.postgres' # unlocks Postgres-only features, needed for HnswIndex
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'corsheaders.middleware.CorsMiddleware',   # must be high, before CommonMiddleware
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'core.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'core.wsgi.application'


# Database
# https://docs.djangoproject.com/en/6.1/ref/settings/#databases

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": os.getenv("DB_NAME"),
        "USER": os.getenv("DB_USER"),
        "PASSWORD": os.getenv("DB_PASSWORD"),
        "HOST": os.getenv("DB_HOST"),
        "PORT": os.getenv("DB_PORT"),
        "CONN_MAX_AGE": int(os.getenv("DB_CONN_MAX_AGE", "0")),
    }
}
# Managed databases (like Supabase) require SSL. Set DB_SSLMODE=require in prod;
# leave it unset for a local Postgres that has no SSL.
_sslmode = os.getenv("DB_SSLMODE")
if _sslmode:
    DATABASES["default"]["OPTIONS"] = {"sslmode": _sslmode}


# Password validation
# https://docs.djangoproject.com/en/6.1/ref/settings/#auth-password-validators

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


# Internationalization
# https://docs.djangoproject.com/en/6.1/topics/i18n/

LANGUAGE_CODE = 'en-us'

TIME_ZONE = 'UTC'

USE_I18N = True

USE_TZ = True


# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/6.1/howto/static-files/

STATIC_URL = 'static/'
STATIC_ROOT = BASE_DIR / "staticfiles"   # where collectstatic gathers files in production


# Email
# https://docs.djangoproject.com/en/6.1/topics/email/#topic-email-configuration

MAILERS = {
    'default': {
        'BACKEND': 'django.core.mail.backends.console.EmailBackend',
    },
}

# Let the React dev server call this API during development. In production, add
# the deployed frontend origin(s) via CORS_ORIGINS (comma-separated).
CORS_ALLOWED_ORIGINS = [
    "http://localhost:5173",
    "http://localhost:5174",
]
CORS_ALLOWED_ORIGINS += [o.strip() for o in os.getenv("CORS_ORIGINS", "").split(",") if o.strip()]
# CSRF trust for the deployed frontend (used by the Django admin over HTTPS).
CSRF_TRUSTED_ORIGINS = [o.strip() for o in os.getenv("CORS_ORIGINS", "").split(",") if o.strip()]

# --- AI provider: Google Gemini (free tier) via its OpenAI-compatible API ---
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_BASE_URL = "https://generativelanguage.googleapis.com/v1beta/openai/"

# --- Media (teacher-uploaded course files) ---
MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

# --- Cloud file storage (optional): Supabase Storage ---
# When these are set, uploaded course files are pushed to a public Supabase
# bucket and the citation "Open"/"Download" links point there, so they work on
# the deployed site (Render's disk is wiped on redeploy). Leave blank for local
# dev to fall back to serving files from /media/. The service key is secret and
# must only ever live on the server, never in the frontend.
SUPABASE_URL = os.getenv("SUPABASE_URL", "")               # e.g. https://xxxx.supabase.co
# The secret key (server only). Accepts Supabase's own env name SUPABASE_SECRET_KEY,
# or the older SUPABASE_SERVICE_KEY, so either copy-pastes cleanly.
SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SECRET_KEY", "") or os.getenv("SUPABASE_SERVICE_KEY", "")
SUPABASE_BUCKET = os.getenv("SUPABASE_BUCKET", "course-files")

# One demo tenant (school) until real login / multi-tenant auth exists.
# Every course created through the API belongs to this tenant for now.
DEMO_TENANT_ID = "00000000-0000-0000-0000-000000000001"