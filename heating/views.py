import datetime
import json

from dateutil.relativedelta import relativedelta
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import HttpResponseRedirect
from django.shortcuts import redirect
from django.urls import reverse
from django.urls import reverse_lazy
from django.views.generic import TemplateView, View

from .daikin_api import DaikinApi
from .models import (HeatingUserAccess,
                     HeatPumpStatusRecord,
                     ClimateSensor,
                     ClimateSensorRecord)
from .nest_api import GoogleApi


class Heating(TemplateView):
    template_name = 'heating.html'

    def dispatch(self, request, *args, **kwargs):
        # Access Control
        user = request.user
        if not user.is_authenticated:
            return redirect(reverse_lazy('dashboard'))
        if not HeatingUserAccess.objects.filter(User=user).exists():
            return redirect(reverse_lazy('dashboard'))
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # Get Daikin Data
        daikin = DaikinApi()
        context['daikin_authenticated'] = True
        r = daikin.current_temps()
        if r['success']:
            context['temps'] = r['temps']
        else:
            context['temps'] = False
            context['daikin_auth_url'] = daikin.auth_url()
            context['daikin_authenticated'] = False
            context['daikin_error'] = r['error']

        # Get Historical Data
        NOW = datetime.datetime.now()
        ONE_DAY_AGO = NOW + relativedelta(days=-1)
        TWO_DAYS_AGO = NOW + relativedelta(days=-2)
        ONE_WEEK_AGO = NOW + relativedelta(weeks=-1)
        ONE_MONTH_AGO = NOW + relativedelta(months=-1)
        ONE_YEAR_AGO = NOW + relativedelta(years=-1)

        context['now'] = NOW.isoformat()
        context['one_day_ago'] = ONE_DAY_AGO.isoformat()
        context['two_days_ago'] = TWO_DAYS_AGO.isoformat()
        context['one_week_ago'] = ONE_WEEK_AGO.isoformat()
        context['one_month_ago'] = ONE_MONTH_AGO.isoformat()
        context['one_year_ago'] = ONE_YEAR_AGO.isoformat()

        heat_status_records = HeatPumpStatusRecord.objects.filter(
            created_at__gt=ONE_YEAR_AGO
        )
        sensors = ClimateSensor.objects.all()

        context['sensor_records'] = {}
        for sensor in sensors:
            records = ClimateSensorRecord.objects.filter(
                created_at__gt=ONE_YEAR_AGO,
                sensor=sensor
            )
            context['sensor_records'][sensor.name] = json.dumps([
                {'x': x.created_at.isoformat(), 'y': x.temperature}
                for x in records
            ])

        context['room_setpoint_records'] = json.dumps([
            {'x': x.created_at.isoformat(), 'y': x.room_setpoint}
            for x in heat_status_records
        ])
        context['tank_setpoint_records'] = json.dumps([
            {'x': x.created_at.isoformat(), 'y': x.tank_setpoint}
            for x in heat_status_records
        ])
        context['flow_temperature_records'] = json.dumps([
            {'x': x.created_at.isoformat(), 'y': x.flow_temperature}
            for x in heat_status_records
        ])
        context['return_temperature_records'] = json.dumps([
            {'x': x.created_at.isoformat(), 'y': x.return_temperature}
            for x in heat_status_records
        ])
        return context


class DaikinDisconnect(LoginRequiredMixin, View):
    def get(self, request, *args, **kwargs):
        daikin = DaikinApi()
        daikin.revoke_access()
        messages.success(request, 'Daikin access was revoked.')
        return HttpResponseRedirect(reverse_lazy('heating'))


class GoogleCallback(View):
    def get(self, request, *args, **kwargs):
        code = request.GET['code']
        if not code:
            messages.error(
                request,
                'There was no access token returned from Google.'
            )
            return HttpResponseRedirect(reverse('heating'))

        google = GoogleApi()
        r = google.authorize(code)
        if not r['success']:
            print(r['message'])
        return HttpResponseRedirect(reverse('heating'))


class DaikinCallback(View):
    def get(self, request, *args, **kwargs):
        code = request.GET['code']
        if not code:
            messages.error(
                request,
                'There was no access token returned from Daikin.'
            )
            return HttpResponseRedirect(reverse('heating'))

        daikin = DaikinApi()
        r = daikin.authorize(code)
        if not r['success']:
            print(r['message'])
        return HttpResponseRedirect(reverse('heating'))
