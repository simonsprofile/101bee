from django.contrib import admin
from django.urls import path
from dashboard.views import Dashboard
from lights.views import Lights
from garage.views import Garage

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', Dashboard.as_view(), name='dashboard'),
    path('lights/', Lights.as_view(), name='lights'),
    path('garage/', Garage.as_view(), name='garage'),
]
