from django.shortcuts import redirect
from django.template.response import TemplateResponse
from django.urls import reverse_lazy
from django.views.generic import View, TemplateView
from django.contrib.auth.mixins import LoginRequiredMixin

from lights.models import LightsSettings, LightsUserAccess
from heating.models import HeatPumpStatusRecord, ClimateSensorRecord, ClimateSensor
import datetime
from dateutil.relativedelta import relativedelta

import json
from pprint import pprint


class Dashboard(LoginRequiredMixin, TemplateView):
    template_name = 'dashboard.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        return context


class Settings(LoginRequiredMixin, View):
    def get(self, request, *args, **kwargs):
        user = request.user
        if not LightsUserAccess.objects.filter(User=user).exists():
            context = {'light_settings': None}
        else:
            context = {'light_settings': _get_settings()}
        return TemplateResponse(request, 'settings.html', context)

    def post(self, request, *args, **kwargs):
        print('post!')
        # more work to be done here obviously, maybe move this whole thing to
        # the lights app?
        return redirect(reverse_lazy('settings'))


# Utils
def _get_settings():
    if not LightsSettings.objects.all().exists():
        LightsSettings().save()
    return LightsSettings.objects.all().first()