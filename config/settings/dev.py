from .base import *  # noqa

DEBUG = True
ALLOWED_HOSTS = ["*"]

# Render templates so dev console / DRF browsable API work.
REST_FRAMEWORK["DEFAULT_RENDERER_CLASSES"] = (
    "rest_framework.renderers.JSONRenderer",
    "rest_framework.renderers.BrowsableAPIRenderer",
)

# Use console email backend during development.
EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"

# Faster password hashers in dev.
PASSWORD_HASHERS = [
    "django.contrib.auth.hashers.MD5PasswordHasher",
]
