# -*- encoding: utf-8 -*-
"""
Copyright (c) 2019 - present AppSeed.us
"""

import os
from decouple import config
from pathlib import Path  # <- use pathlib only

# ---------- Paths ----------
BASE_DIR = Path(__file__).resolve().parent.parent        # project root
CORE_DIR = BASE_DIR                                      # keep existing semantics

TEMPLATE_DIR = CORE_DIR / "apps" / "templates"
STATIC_ROOT = CORE_DIR / "staticfiles"
STATIC_URL = "/static/"
STATICFILES_DIRS = [CORE_DIR / "apps" / "static"]

# Logs dir as a Path (not string)
LOG_DIR = CORE_DIR / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)               # ensure exists

# ---------- Security / Debug ----------
SECRET_KEY = config("SECRET_KEY", default="S#perS3crEt_1122")
DEBUG = config("DEBUG", default=True, cast=bool)
ALLOWED_HOSTS = ["localhost", "127.0.0.1", config("SERVER", default="127.0.0.1")]

# ---------- Installed apps / middleware ----------
INSTALLED_APPS = [
    "apps.authentication.apps.AuthenticationConfig",
    "apps.profiles.apps.ProfilesConfig",
    "apps.technology.apps.TechnologyConfig",
    'django.contrib.humanize',
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "apps.home",
    'tinymce',
]

AUTH_USER_MODEL = "authentication.User"

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "apps.authentication.middleware.access_policy.AccessPolicyMiddleware",
]

ROOT_URLCONF = "core.urls"
LOGIN_REDIRECT_URL = "home"
LOGOUT_REDIRECT_URL = "home"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [TEMPLATE_DIR],       # Path works fine; no need to str()
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "apps.authentication.context_processors.user_context",
            ],
        },
    },
]

WSGI_APPLICATION = "core.wsgi.application"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# ---------- Database ----------
DATABASES = {
    "default": {
        "ENGINE": "djongo",
        "NAME": "tech_tool_db",
        "ENFORCE_SCHEMA": False,
    }
}

# ---------- Password validation ----------
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# ---------- I18N ----------
LANGUAGE_CODE = "en-us"
TIME_ZONE = "Europe/Paris"
USE_I18N = True
USE_L10N = True
USE_TZ = True

# ---------- Logging ----------
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,

    "formatters": {
        "standard": {
            "format": "[{asctime}] {levelname} {name} - {message}",
            "style": "{",
        },
        "verbose": {
            "format": "%(asctime)s %(levelname)s %(name)s:%(lineno)d — %(message)s",
            "datefmt": "%Y-%m-%d %H:%M:%S",
        },
    },

    "handlers": {
        "profiles_file": {
            "class": "logging.handlers.RotatingFileHandler",
            "level": "DEBUG",
            "filename": str(LOG_DIR / "profiles.log"),  # Path -> str
            "maxBytes": 5 * 1024 * 1024,
            "backupCount": 3,
            "formatter": "standard",
            "encoding": "utf-8",
        },
        "console": {
            "class": "logging.StreamHandler",
            "stream": "ext://sys.stdout",
            "formatter": "verbose",
        },
    },

    "loggers": {
        "apps.profiles": {
            "handlers": ["profiles_file", "console"],
            "level": "DEBUG",
            "propagate": False,
        },
        "apps.authentication": {
            "handlers": ["console"],
            "level": "INFO",
            "propagate": False,
        },
        "apps.authentication.views": {
            "handlers": ["console"],
            "level": "INFO",
            "propagate": False,
        },
        "django.request": {
            "handlers": ["console"],
            "level": "WARNING",
            "propagate": False,
        },
    },

    "root": {
        "handlers": ["console"],
        "level": "INFO",
    },
}
