from django.http import HttpResponse
from django.views.generic import View
from heating.workflows import Heating


class RecordData(View):
    def get(self, request, *args, **kwargs):
        heating = Heating()
        heating.record_current_data()
        r = HttpResponse()
        r.status_code = 200
        return r