from django.urls import path
from .views import *

urlpatterns = [
    path('', Lights.as_view(), name='lights'),
    path('auth/', LightsAuth.as_view(), name='lights_auth'),
    path('disconnect/', LightsDisconnect.as_view(), name='lights_disconnect'),
    path(
        'initiate-daily-scenes/',
        LightsInitiateDailyScenes.as_view(),
        name='lights_intitate_daily_scenes'
    ),
]
