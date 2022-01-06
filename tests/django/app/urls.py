import django.urls

import tests.django.app.views

urlpatterns = [
    django.urls.re_path(r"^error/?$", tests.django.app.views.error_view),
    django.urls.re_path(r"^.*$", tests.django.app.views.ok_view),
]
