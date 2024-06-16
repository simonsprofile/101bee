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
        print(heat_status_records.last())
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