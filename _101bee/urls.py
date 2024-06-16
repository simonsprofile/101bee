from django.contrib import admin
from django.contrib.auth import views
from django.urls import path, include
from dashboard.views import Dashboard, Settings
from lights.urls import urlpatterns as lights
from entry.urls import urlpatterns as entry
from heating.urls import urlpatterns as heating
from scribe.urls import urlpatterns as scribe

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', Dashboard.as_view(), name='dashboard'),
    path('settings/', Settings.as_view(), name='settings'),
    path('lights/', include(lights)),
    path('entry/', include(entry)),
    path('heating/', include(heating)),
    path('scribe/', include(scribe)),

    path('', include('django.contrib.auth.urls')),
]
