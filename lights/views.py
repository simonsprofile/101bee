import copy
import random
import string

from django.contrib import messages
from django.http import HttpResponseRedirect
from django.urls import reverse_lazy
from django.views.generic import View, TemplateView

from .bridge_api import Bridge
from .models import LightsSettings


class Lights(TemplateView):
    template_name = 'lights.html'

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
            return {'authorised': False} | s

        bridge = Bridge(s)
        if not bridge.is_authorised():
            return {'authorised': False} | s

        return {'authorised': True} | s

    def _get_bridge_counts(self):
        s = _get_settings().__dict__
        if not s['bridge_ip'] or not s['bridge_user'] or not s['bridge_key']:
            return {'rooms': []}

        bridge = Bridge(s)
        r = bridge.search('rules')
        if not r['success']:
            error = (
                'I was not able to find a list of rules because of the '
                f"following  error: {r['error']}. Try re-authorising."
            )
            messages.warning(self.request, error)
            return {'rule_count': 0}

        rule_count = len(r['records'])

        r = bridge.search('light')
        if not r['success']:
            error = (
                'I was not able to find a list of lights because of the '
                f"following  error: {r['error']}. Try re-authorising."
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
            return { 'rooms': [] }

        bridge = Bridge(s)
        r = bridge.search('room')
        if not r['success']:
            error = (
                'I was not able to find a list of rooms because of the '
                f"following  error: {r['error']}. Try re-authorising."
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
                f"following  error: {r['error']}. Try re-authorising."
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
                f"following  error: {r['error']}. Try re-authorising."
            )
            messages.warning(self.request, error)
            return {'devices': []}
        device_list = r['records']

        r = bridge.search('device_power')
        if not r['success']:
            error = (
                'I was not able to find a list of devices because of the '
                f"following  error: {r['error']}. Try re-authorising."
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
            devices.append({
                'name': name,
                'battery_level': state['power_state']['battery_level']
            })
        return {
            'devices': devices,
            'battery_warning': any(x['battery_level'] < 20 for x in devices)
        }


class LightsAuth(View):
    def get(self, request, *args, **kwargs):
        return HttpResponseRedirect(reverse_lazy('lights'))

    def post(self, request, *args, **kwargs):
        ip = request.POST['ip']
        s = _get_settings().__dict__
        s['hub_ip'] = ip
        bridge = Bridge(self._get_settings().__dict__)
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


class LightsDisconnect(View):
    def get(self, request, *args, **kwargs):
        s = _get_settings()
        s.bridge_user = None
        s.bridge_key = None
        s.save()
        messages.success(request, 'Bridge credentials deleted.')
        return HttpResponseRedirect(reverse_lazy('lights'))


class LightsCommitChanges(View):
    def get(self):
        return HttpResponseRedirect(reverse_lazy('lights'))

    def post(self, request, *args, **kwargs):
        self.request = request
        self.s = _get_settings().__dict__
        self.bridge = Bridge(self.s)

        # Get Room
        r = self.bridge.get('room', request.POST['room_id'])
        if not r['success']:
            error = (
                'Sorry, I was unable to find the room information because of '
                f"the following error. Try re-authorising: {r['errors']}"
            )
            messages.warning(request, error)
            return HttpResponseRedirect(reverse_lazy('lights'))
        room = r['record']

        # Get Switches
        r = self._get_switches()
        if not r['success']:
            error = (
                'Sorry, I was unable to find the switch information because of '
                f"the following error. Try re-authorising: {r['errors']}"
            )
            messages.warning(request, error)
            return HttpResponseRedirect(reverse_lazy('lights'))
        switches = r['records']

        if request.POST['action_type'] == 'initiate':
            return self.initiate_daily_scenes(room)
        elif request.POST['action_type'] == 'reset':
            return self.reset_room(room)
        elif request.POST['action_type'] == 'configure_switches':
            if len(switches) < 1:
                messages.danger(request, 'Please select at least one switch.')
                return HttpResponseRedirect(reverse_lazy('lights'))
            return self.configure_switches(room, switches)
        else:
            messages.warning(request, "That function doesn't work yet. Boo!")
            return HttpResponseRedirect(reverse_lazy('lights'))

    def initiate_daily_scenes(self, room):
        # Get Lights in Room
        r = self._get_lights_in(room)
        if not r['success']:
            messages.warning(self.request, r['error'])
            return HttpResponseRedirect(reverse_lazy('lights'))
        lights = r['records']

        # Get Scenes in Room
        r = self._get_scenes_for(room)
        if not r['success']:
            messages.warning(self.request, r['error'])
            return HttpResponseRedirect(reverse_lazy('lights'))
        scene_names = [x['metadata']['name'] for x in r['records']]

        # Get all Rules
        r = self.bridge.search('rules')
        if not r['success']:
            messages.warning(self.request, r['error'])
            return HttpResponseRedirect(reverse_lazy('lights'))
        rules = r['records']

        # Build Scenes
        scenes = ['Morning', 'Day', 'Evening', 'Night']
        for scene in scenes:
            # Post scenes
            prefix = ''
            for action_set in self._collate_actions_for_scene(scene, lights):
                if True in [x['action']['on']['on'] for x in action_set]:
                    payload = self._collate_payload_for_scene(
                        f"{prefix}{scene}", room, action_set
                    )
                    if payload['metadata']['name'] not in scene_names:
                        r = self.bridge.post('scene', payload)
                        if not r['success']:
                            error = (
                                'Sorry, I was not able to create a '
                                f"scene for the {scene} in the "
                                f"{room['metadata']['name']} because of the "
                                f"following error. {r['errors']}"
                            )
                            messages.warning(self.request, error)
                            return HttpResponseRedirect(reverse_lazy('lights'))
                prefix = 'Lamps for '

            # Post transition rule
            rule_name = f"{room['metadata']['name']} >> {scene}"
            if len([x for x in rules.values() if x['name'] == rule_name]) < 1:
                transition_time = self.s[f"{scene.lower()}_time"]
                r = self.bridge.post(
                    'rules',
                    self._collate_payload_for_transition(
                        room,
                        scene,
                        self._time_interval_string_for_transition(transition_time),
                        self.s[f"{scene.lower()}_mirek"]
                    )
                )
                if not r['success']:
                    error = (
                        'Sorry, I was not able to create the transition for the '
                        f"{scene} in the {room['metadata']['name']} because of the "
                        f"following error: {r['errors']}"
                    )
                    messages.warning(self.request, error)
                    return HttpResponseRedirect(reverse_lazy('lights'))

        messages.success(
            self.request,
            f"Scenes and transitions have been created for the "
            f"{room['metadata']['name']}."
        )

        return HttpResponseRedirect(reverse_lazy('lights'))

    def reset_room(self, room):
        # Get Scenes in Room
        r = self._get_scenes_for(room)
        if not r['success']:
            messages.warning(self.request, r['error'])
            return HttpResponseRedirect(reverse_lazy('lights'))
        scenes = r['records']

        # Get all Rules
        r = self.bridge.search('rules')
        if not r['success']:
            messages.warning(self.request, r['error'])
            return HttpResponseRedirect(reverse_lazy('lights'))
        rules = r['records']

        # Get all Schedules
        r = self.bridge.search('schedules')
        if not r['success']:
            messages.warning(self.request, r['error'])
            return HttpResponseRedirect(reverse_lazy('lights'))
        schedules = r['records']

        # Get all Sensors
        r = self.bridge.search('sensors')
        if not r['success']:
            messages.warning(self.request, r['error'])
            return HttpResponseRedirect(reverse_lazy('lights'))
        sensors = r['records']

        for scene in scenes:
            r = self.bridge.delete('scene', scene['id'])
            if not r['success']:
                messages.warning(self.request, r['error'])
                return HttpResponseRedirect(reverse_lazy('lights'))

        for rule_id, rule in rules.items():
            for scene_name in ['Morning', 'Day', 'Evening', 'Night']:
                rules_to_delete = [
                    f"{room['metadata']['name'].replace(' ', '')}>>{scene_name}",
                    f"{room['metadata']['name'].replace(' ', '')}On{scene_name}",
                    f"Lamps for {room['metadata']['name'].replace(' ', '')}On{scene_name}",
                    f"{room['metadata']['name'].replace(' ', '')}DimUp",
                    f"{room['metadata']['name'].replace(' ', '')}DimDn",
                    f"{room['metadata']['name'].replace(' ', '')}Off"
                ]
                for rule_to_delete in rules_to_delete:
                    if rule_to_delete in rule['name']:
                        self.bridge.delete('rules', rule_id)

        for sensor_id, sensor in sensors.items():
            if sensor['name'] == f"{room['metadata']['name'].replace(' ', '')}Clicked":
                self.bridge.delete('sensors', sensor_id)

        for schedule_id, schedule in schedules.items():
            if schedule['name'] == f"{room['metadata']['name'].replace(' ', '')}Clicked":
                self.bridge.delete('schedules', schedule_id)

        messages.success(
            self.request,
            f"All scenes and rules for Daily Scene transitions deleted for "
            f"{room['metadata']['name']}."
        )
        return HttpResponseRedirect(reverse_lazy('lights'))

    def configure_switches(self, room, switches):
        # Get Scenes in Room
        r = self._get_scenes_for(room)
        if not r['success']:
            messages.warning(self.request, r['error'])
            return HttpResponseRedirect(reverse_lazy('lights'))

        scenes = r['records']
        scene_names = [x['metadata']['name'] for x in scenes]
        main_scene_names = ['Morning', 'Day', 'Evening', 'Night']
        main_scenes_exist = False
        lamp_scenes_exist = False
        scenes_error = True
        scenes_error_message = (
            "I couldn't find all the daily scenes. I need this set of scenes "
            "to configure the switch(es). You can initiate the daily scenes "
            "to fix this."
        )
        if all(x in scene_names for x in main_scene_names):
            main_scenes_exist = True
            scenes_error = False

        if main_scenes_exist:
            if all(f"Lamps for {x}" in scene_names for x in main_scene_names):
                lamp_scenes_exist = True
            elif any(f"Lamps for {x}" in scene_names for x in main_scene_names):
                scenes_error = True
                scenes_error_message = (
                    "Some lamp scenes exist, but not all. So I'm not sure "
                    "whether to include a lamp circuit or not. "
                    'You can intiate the daily scenes first to fix this.'
                )

        if scenes_error:
            messages.warning(self.request, scenes_error_message)
            return HttpResponseRedirect(reverse_lazy('lights'))

        r = self.bridge.search('rules')
        if not r['success']:
            messages.warning(self.request, r['error'])
            return HttpResponseRedirect(reverse_lazy('lights'))
        rules = r['records']

        if main_scenes_exist and lamp_scenes_exist:
            # Clicked flag
            payload = {
                "name": f"{room['metadata']['name'].replace(' ', '')}Clicked",
                "type": "CLIPGenericFlag",
                "modelid": "True/False Flag",
                "manufacturername": "Barry Butler",
                "swversion": "Current",
                "uniqueid": ''.join(
                    random.choices(string.ascii_uppercase + string.digits, k=8)
                )
            }
            r = self.bridge.post('sensors', payload)
            if not r['success']:
                error = (
                    'I was unable to setup a click flag because of the '
                    f"following error: {r['errors']}"
                )
                messages.warning(self.request, error)
                return HttpResponseRedirect(reverse_lazy('lights'))
            click_flag = r['record']

            # Click schedule
            payload = {
                'name': f"{room['metadata']['name'].replace(' ', '')}Clicked",
                'command': {
                    'address': (
                        f"/api/{self.s['bridge_user']}"
                        f"{click_flag['id_v1']}/state"
                    ),
                    'body': {'flag': False},
                    'method': 'PUT'
                },
                'time': 'PT00:00:01',
                'autodelete': False
            }
            r = self.bridge.post('schedules', payload)
            if not r['success']:
                error = (
                    'I was unable to setup a click flag timer because of the '
                    f"following error: {r['errors']}"
                )
                messages.warning(self.request, error)
                return HttpResponseRedirect(reverse_lazy('lights'))
            click_schedule = r['record']

            # On Click Actions
            prefixes = ['', 'LampsFor']
            for prefix in prefixes:
                switch_count = 0
                for switch in switches:
                    if len(switches) > 1:
                        switch_count += 1
                    else:
                        switch_count = ''
                    for scene_name in main_scene_names:
                        scene_prefix = 'Lamps for ' if prefix == 'LampsFor' else ''
                        scene = [
                            x for x in scenes
                            if f"{scene_prefix}{scene_name}" == x['metadata']['name']
                        ][0]
                        rule_name = f"{prefix}{room['metadata']['name'].replace(' ', '')}On{scene_name}"
                        if switch_count:
                            rule_name = f"{rule_name}{switch_count}"
                        rule_names = [x['name'] for x in rules.values()]
                        if rule_name in rule_names:
                            continue
                        scene_id = scene['id_v1'].replace('/scenes/', '')
                        time = self._time_interval_string_for_on(scene_name)
                        conditions = [
                            {
                                'address': f"{switch['id_v1']}/state/buttonevent",
                                'operator': 'eq',
                                'value': '1000'
                            },
                            {
                                'address': f"{switch['id_v1']}/state/lastupdated",
                                'operator': 'dx'
                            },
                            {
                                'address': '/config/localtime',
                                'operator': 'in',
                                'value': time
                            },
                            {
                                'address': f"{click_flag['id_v1']}/state/flag",
                                'operator': 'eq',
                                'value': str(not prefix).lower()
                            }
                        ]
                        actions = [
                            {
                                'address': f"{room['id_v1']}/action",
                                'method': 'PUT',
                                'body': {'scene': scene_id}
                            }
                        ]
                        if prefix:
                            actions.append({
                                "address": f"{click_flag['id_v1']}/state",
                                "method": "PUT",
                                "body": {"flag": True}
                            })
                            actions.append({
                                "address": f"{click_schedule['id_v1']}",
                                "method": "PUT",
                                "body": {"status": "enabled"}
                            })
                        payload = {
                            'name': rule_name,
                            'conditions': conditions,
                            'actions': actions
                        }
                        r = self.bridge.post('rules', payload)
                        if not r['success']:
                            error = (
                                'I was unable to post a rule because of the '
                                f"following error: {r['errors']}"
                            )
                            messages.error(self.request, error)
                            return HttpResponseRedirect(reverse_lazy('lights'))

        else:
            switch_count = 0
            for switch in switches:
                if len(switches) > 1:
                    switch_count += 1
                else:
                    switch_count = ''
                for scene_name in main_scene_names:
                    scene = [
                        x for x in scenes
                        if scene_name == x['metadata']['name']
                    ][0]
                    rule_name = f"{room['metadata']['name'].replace(' ', '')}On{scene_name}"
                    if switch_count:
                        rule_name = f"{rule_name}{switch_count}"
                    rule_names = [x['name'] for x in rules.values()]
                    if rule_name in rule_names:
                        continue
                    scene_id = scene['id_v1'].replace('/scenes/', '')
                    time = self._time_interval_string_for_on(scene_name)
                    payload = {
                        'name': rule_name,
                        'conditions': [
                            {
                                'address': f"{switch['id_v1']}/state/buttonevent",
                                'operator': 'eq',
                                'value': '1000'
                            },
                            {
                                'address': f"{switch['id_v1']}/state/lastupdated",
                                'operator': 'dx'
                            },
                            {
                                'address': '/config/localtime',
                                'operator': 'in',
                                'value': time
                            }
                        ],
                        'actions': [
                            {
                                'address': f"{room['id_v1']}/action",
                                'method': 'PUT',
                                'body': {'scene': scene_id}
                            }
                        ]
                    }
                    r = self.bridge.post('rules', payload)
                    if not r['success']:
                        error = (
                            'I was unable to post a rule because of the '
                            f"following error: {r['errors']}"
                        )
                        messages.error(self.request, error)
                        return HttpResponseRedirect(reverse_lazy('lights'))

        universal_rules = [
            {'suffix': 'Off', 'op_value': '4000', 'body': {'on': False}},
            {'suffix': 'DimDn', 'op_value': '3000', 'body': {'bri_inc': -39}},
            {'suffix': 'DimUp', 'op_value': '2000', 'body': {'bri_inc': 39}},
        ]
        switch_count = 0
        for switch in switches:
            if len(switches) > 1:
                switch_count += 1
            else:
                switch_count = ''
            for rule in universal_rules:
                rule_name = f"{room['metadata']['name'].replace(' ', '')}{rule['suffix']}"
                if switch_count:
                    rule_name = f"{rule_name} {switch_count}"
                rule_names = [x['name'] for x in rules.values()]
                if rule_name in rule_names:
                    continue
                payload = {
                    'name': rule_name,
                    'conditions': [
                        {
                            'address': f"{switch['id_v1']}/state/buttonevent",
                            'operator': 'eq',
                            'value': rule['op_value']
                        },
                        {
                            'address': f"{switch['id_v1']}/state/lastupdated",
                            'operator': 'dx'
                        }
                    ],
                    'actions': [
                        {
                            'address': f"{room['id_v1']}/action",
                            'method': 'PUT',
                            'body': rule['body']
                        }
                    ]
                }
                r = self.bridge.post('rules', payload)
                if not r['success']:
                    error = (
                        'I was unable to setup a switch rule because of the '
                        f"following error: {r['errors']}"
                    )
                    messages.warning(self.request, error)
                    return HttpResponseRedirect(reverse_lazy('lights'))

        messages.success(self.request, 'Switch(es) configured!')
        return HttpResponseRedirect(reverse_lazy('lights'))

    def _get_lights_in(self, room):
        lights = []
        for child in room['children']:
            r = self.bridge.get(child['rtype'], child['rid'])
            if not r['success']:
                return r
            r['record']['is_lamp'] = \
                'lamp' in r['record']['metadata']['name'].lower()

            is_light = \
                'light' in [x['rtype'] for x in r['record']['services']]
            if is_light:
                for service in r['record']['services']:
                    if service['rtype'] == 'light':
                        r['record']['light_service_id'] = service['rid']
                lights.append(r['record'])
        return {'success': True, 'records': lights}

    def _get_scenes_for(self, room):
        r = self.bridge.search('scene')
        if not r['success']:
            return r
        return {
            'success': True,
            'records': [
                x for x in r['records']
                if x['group']['rid'] == room['id']
            ]
        }

    def _get_switches(self):
        ids = [
            x.replace('switch_', '') for x in self.request.POST.keys()
            if x[:7] == 'switch_'
        ]
        r = self.bridge.search('device')
        if not r['success']:
            return r
        return {
            'success': True,
            'records': [x for x in r['records'] if x['id'] in ids]
        }

    def _collate_actions_for_scene(self, scene, lights):
        action_template = {
            'target': {'rid': None, 'rtype': 'light'},
            'action': {
                'on': {'on': True},
                'dimming': {
                    'brightness': self.s[f"{scene.lower()}_brightness"]
                },
                'color_temperature': {
                    'mirek': self.s[f"{scene.lower()}_mirek"]
                },
            }
        }
        main, lamps = [], []
        for light in lights:
            action = copy.deepcopy(action_template)
            action['target']['rid'] = light['light_service_id']
            main.append(copy.deepcopy(action))
            action['action']['on']['on'] = light['is_lamp']
            lamps.append(copy.deepcopy(action))
        return [main, lamps]

    def _collate_payload_for_scene(self, scene_name, room, actions):
        return {
            'metadata': {
                'name': scene_name
            },
            'group': {'rid': room['id'], 'rtype': 'room'},
            'speed': 0.5,
            'type': 'scene',
            'actions': actions
        }

    def _collate_payload_for_transition(self, room, scene, interval, mirek):
        return {
            "name": f"{room['metadata']['name'].replace(' ', '')}>>{scene}",
            "recycle": False,
            "conditions": [
                {
                    "address": f"{room['id_v1']}/state/any_on",
                    "operator": "eq",
                    "value": "true"
                },
                {
                    "address": "/config/localtime",
                    "operator": "in",
                    "value": interval
                }
            ],
            "actions": [
                {
                    "address": f"{room['id_v1']}/action",
                    "method": "PUT",
                    "body": {"ct": mirek, "transitiontime": 6000 }
                }
            ]
        }

    def _time_interval_string_for_on(self, scene_name):
        get_end = {
            'morning': 'day',
            'day': 'evening',
            'evening': 'night',
            'night': 'morning'
        }
        s = self.s[f"{scene_name.lower()}_time"]
        e = self.s[f"{get_end[scene_name.lower()]}_time"]
        return (
            f"T{s.hour:02}:{s.minute:02}:{s.second:02}/"
            f"T{e.hour:02}:{e.minute:02}:{e.second:02}"
        )

    def _time_interval_string_for_transition(self, t):
        return (
            f"T{t.hour:02}:{t.minute:02}:{t.second:02}/"
            f"T{t.hour:02}:{t.minute:02}:{t.second+1:02}"
        )


# Utils
def _get_settings():
    if not LightsSettings.objects.all().exists():
        LightsSettings().save()
    return LightsSettings.objects.all().first()