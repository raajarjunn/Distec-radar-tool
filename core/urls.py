
# G:Distec\core\urls.py
from django.contrib import admin
from django.urls import path, include  # add this


urlpatterns = [
   
    path('admin/', admin.site.urls),
    path("technology/", include("apps.technology.urls")),
    path('tinymce/', include('tinymce.urls')),  # optional but fine to keep
    # put profiles BEFORE home so the home catch-all doesn't swallow it
    path("profile/", include("apps.profiles.urls")),
    #path("", include("apps.technology.urls")),
  
    # auth and home after
    path("", include("apps.authentication.urls")),
    path("", include("apps.home.urls")),
]