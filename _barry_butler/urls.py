from django.contrib import admin
from django.urls import path, include
from dashboard.views import Dashboard
from lights.urls import urlpatterns as lights

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', Dashboard.as_view(), name='dashboard'),
    path('lights/', include(lights)),
]
