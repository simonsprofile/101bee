from django.urls import path
from .views import *

urlpatterns = [
    path('', Lights.as_view(), name='lights'),
    path('auth/', LightsAuth.as_view(), name='lights_auth'),
    path('disconnect/', LightsDisconnect.as_view(), name='lights_disconnect'),
    path('commit/', LightsCommitChanges.as_view(), name='lights_commit'),
]
