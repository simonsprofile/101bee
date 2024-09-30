import json

from django.http import HttpResponse, JsonResponse
from django.views.generic import View
from heating.workflows import Heating


class RecordData(View):
    def get(self, request, *args, **kwargs):
        heating = Heating()
        heating.record_current_data()
        return HttpResponse(status_code=200)