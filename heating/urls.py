from django.urls import path
from .views import *

urlpatterns = [
    path('', Heating.as_view(), name='heating'),
    path('disconnect/', DaikinDisconnect.as_view(), name='daikin_disconnect'),
    path('google/callback/', GoogleCallback.as_view(), name='google_callback'),
    path('daikin/callback/', DaikinCallback.as_view(), name='daikin_callback'),
]
