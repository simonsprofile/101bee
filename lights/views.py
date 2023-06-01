from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import HttpResponseRedirect
from django.shortcuts import redirect
from django.urls import reverse_lazy
from django.views.generic import View, TemplateView

from .bridge_api import Bridge
from .models import LightsSettings, LightsUserAccess
from .workflows import (
    Workflows,
    WorkflowException,
)


class Lights(TemplateView):
    template_name = 'lights.html'

    def dispatch(self, request, *args, **kwargs):
        # Access Control
        user = request.user
        if not user.is_authenticated:
            return redirect(reverse_lazy('dashboard'))
        if not LightsUserAccess.objects.filter(User=user).exists():
            return redirect(reverse_lazy('dashboard'))
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context = context | self._check_bridge()
        context = context | self._get_bridge_counts()
        context = context | self._get_rooms()
        context = context | self._get_switches_and_sensors({
            'switches': 'Hue dimmer switch',
            'sensors': 'Hue motion sensor',
            'buttons': 'Hue Smart button'
        })
        context = context | self._check_batteries()
        return context

    def _check_bridge(self):
        s = _get_settings().__dict__
        if not s['bridge_ip'] or not s['bridge_user'] or not s['bridge_key']:
            return {'authorised': False, 'settings': s}

        bridge = Bridge(s)
        if not bridge.is_authorised():
            return {'authorised': False, 'settings': s}

        return {'authorised': True, 'settings': s}

    def _get_bridge_counts(self):
        s = _get_settings().__dict__
        if not s['bridge_ip'] or not s['bridge_user'] or not s['bridge_key']:
            return {'rooms': []}

        bridge = Bridge(s)
        r = bridge.search('rules')
        if not r['success']:
            error = (
                'I was not able to find a list of rules because of the '
                f"following  error: {r['errors']}. Try re-authorising."
            )
            messages.warning(self.request, error)
            return {'rule_count': 0}

        rule_count = len(r['records'])

        r = bridge.search('light')
        if not r['success']:
            error = (
                'I was not able to find a list of lights because of the '
                f"following  error: {r['errors']}. Try re-authorising."
            )
            messages.warning(self.request, error)
            return {'rule_count': 0}

        bulb_count = len(r['records'])

        return {
            'rule_count': rule_count,
            'bulb_count': bulb_count
        }

    def _get_rooms(self):
        s = _get_settings().__dict__
        if not s['bridge_ip'] or not s['bridge_user'] or not s['bridge_key']:
            return {'rooms': []}

        bridge = Bridge(s)
        r = bridge.search('room')
        if not r['success']:
            error = (
                'I was not able to find a list of rooms because of the '
                f"following  error: {r['errors']}. Try re-authorising."
            )
            messages.warning(self.request, error)
            return {'rooms': []}

        return {
            'rooms': [
                {'id': x['id'], 'name': x['metadata']['name']}
                for x in r['records']
            ]
        }

    def _get_switches_and_sensors(self, devices):
        s = _get_settings().__dict__
        if not s['bridge_ip'] or not s['bridge_user'] or not s['bridge_key']:
            return {'rooms': []}

        bridge = Bridge(s)
        r = bridge.search('device')
        if not r['success']:
            error = (
                'I was not able to find a list of switches because of the '
                f"following  error: {r['errors']}. Try re-authorising."
            )
            messages.warning(self.request, error)
            return r

        response = {}

        for key, product_name in devices.items():
            response[key] = [
                x for x in r['records']
                if x['product_data']['product_name'] == product_name
            ]

        return response

    def _check_batteries(self):
        s = _get_settings().__dict__
        if not s['bridge_ip'] or not s['bridge_user'] or not s['bridge_key']:
            return {'devices': []}

        bridge = Bridge(s)

        r = bridge.search('device')
        if not r['success']:
            error = (
                'I was not able to find a list of devices because of the '
                f"following  error: {r['errors']}. Try re-authorising."
            )
            messages.warning(self.request, error)
            return {'devices': []}
        device_list = r['records']

        r = bridge.search('device_power')
        if not r['success']:
            error = (
                'I was not able to find a list of devices because of the '
                f"following  error: {r['errors']}. Try re-authorising."
            )
            messages.warning(self.request, error)
            return {'devices': []}
        power_states = r['records']

        devices = []
        for state in power_states:
            name = [
                x['metadata']['name'] for x in device_list
                if x['id'] == state['owner']['rid']
            ][0]
            try:
                devices.append({
                    'name': name,
                    'battery_level': state['power_state']['battery_level']
                })
            except KeyError:
                devices.append({
                    'name': name,
                    'battery_level': '??'
                })
        return {
            'devices': devices,
            'battery_warning': any(x['battery_level'] < 20 for x in devices)
        }


class LightsAuth(LoginRequiredMixin, View):
    def get(self, request, *args, **kwargs):
        return HttpResponseRedirect(reverse_lazy('lights'))

    def post(self, request, *args, **kwargs):
        ip = request.POST['ip']
        s = _get_settings().__dict__
        s['hub_ip'] = ip
        bridge = Bridge(_get_settings().__dict__)
        r = bridge.authorise()
        if r['success']:
            messages.success(request, 'Bridge authorised!')
        else:
            messages.warning(
                request,
                'There was a was an error reported when trying to authorise:\n'
                f"{r['message']}"
            )

        return HttpResponseRedirect(reverse_lazy('lights'))


class LightsDisconnect(LoginRequiredMixin, View):
    def get(self, request, *args, **kwargs):
        s = _get_settings()
        s.bridge_user = None
        s.bridge_key = None
        s.save()
        messages.success(request, 'Bridge credentials deleted.')
        return HttpResponseRedirect(reverse_lazy('lights'))


class LightsCommitChanges(LoginRequiredMixin, View):
    def get(self):
        return HttpResponseRedirect(reverse_lazy('lights'))

    def post(self, request, *args, **kwargs):
        self.request = request
        self.s = _get_settings().__dict__
        self.bridge = Bridge(self.s)

        r = self.bridge.get('room', request.POST['room_id'])
        if not r['success']:
            error = (
                'Sorry, I was unable to find the room information because of '
                f"the following error. Try re-authorising: {r['errors']}"
            )
            messages.warning(request, error)
            return HttpResponseRedirect(reverse_lazy('lights'))
        room = r['record']

        devices = {'button': None}
        r = self._get_devices('switch')
        if not r['success']:
            error = (
                'Sorry, I was unable to find the switch information because of '
                f"the following error. Try re-authorising: {r['errors']}"
            )
            messages.warning(request, error)
            return HttpResponseRedirect(reverse_lazy('lights'))
        devices['switches'] = r['records']

        r = self._get_devices('sensor')
        if not r['success']:
            error = (
                'Sorry, I was unable to find the sensor information because of '
                f"the following error. Try re-authorising: {r['errors']}"
            )
            messages.warning(request, error)
            return HttpResponseRedirect(reverse_lazy('lights'))
        devices['sensors'] = r['records']

        if 'button' in request.POST:
            r = self.bridge.get('device', request.POST['button'])
            if not r['success']:
                messages.error(
                    request,
                    f"I wasn't able to find that button in the v2 API because "
                    f"of the following error: {r['errors']}"
                )
                return HttpResponseRedirect(reverse_lazy('lights'))
            rid = r['record']['id_v1'].replace('/sensors/', '')
            r = self.bridge.get('sensors', rid)
            if not r['success']:
                messages.error(
                    request,
                    f"I wasn't able to find that button because of the "
                    f"following error: {r['errors']}"
                )
                return HttpResponseRedirect(reverse_lazy('lights'))
            devices['button'] = r['record']

        # Get delay
        delay = request.POST['minutes']

        bridge_secretary = Workflows(request, room, devices)
        if request.POST['action_type'] == 'create_scenes':
            try:
                bridge_secretary.create_daily_scenes()
            except WorkflowException as e:
                messages.error(request, e)
        elif request.POST['action_type'] == 'remove_scenes':
            try:
                bridge_secretary.remove_daily_scenes()
            except WorkflowException as e:
                messages.error(request, e)
        elif request.POST['action_type'] == 'configure_switches':
            if len(devices['switches']) < 1:
                messages.error(request, 'Please select at least one switch.')
            else:
                try:
                    bridge_secretary.create_switch_configuration()
                except WorkflowException as e:
                    messages.error(request, e)
        elif request.POST['action_type'] == 'remove_switches':
            try:
                bridge_secretary.remove_switch_configuration()
            except WorkflowException as e:
                messages.error(request, e)
        elif request.POST['action_type'] == 'configure_sensors':
            if len(devices['sensors']) < 1:
                messages.error(request, 'Please select at least one sensor.')
            else:
                try:
                    bridge_secretary.create_sensor_configuration(float(delay))
                except WorkflowException as e:
                    messages.error(request, e)
        elif request.POST['action_type'] == 'remove_sensors':
            try:
                bridge_secretary.remove_sensor_configuration()
            except WorkflowException as e:
                messages.error(request, e)
        return HttpResponseRedirect(reverse_lazy('lights'))

    def _get_devices(self, type_slug):
        ids = [
            x.replace(f"{type_slug}_", '') for x in self.request.POST.keys()
            if x[:len(type_slug)+1] == f"{type_slug}_"
        ]
        r = self.bridge.search('device')
        if not r['success']:
            return r
        return {
            'success': True,
            'records': [x for x in r['records'] if x['id'] in ids]
        }


# Utils
def _get_settings():
    if not LightsSettings.objects.all().exists():
        LightsSettings().save()
    return LightsSettings.objects.all().first()
