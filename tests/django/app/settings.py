"""Django settings that should be in-place when running tests."""
SECRET_KEY = "dummy-secret"

APILYTICS_API_KEY = "dummy-key"

MIDDLEWARE = [
    "apilytics.django.ApilyticsMiddleware",
]

ROOT_URLCONF = "tests.django.app.urls"
