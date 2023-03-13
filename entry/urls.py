from django.urls import path
from .views import *

urlpatterns = [
    path('', Entry.as_view(), name='entry'),
]
