from django.urls import path
from .views import *

urlpatterns = [
    path('record-data', RecordData.as_view(), name='record_data'),
]
