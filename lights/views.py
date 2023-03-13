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
        context = context | self._get_rooms()
        return context

    def _check_bridge(self):
        s = _get_settings().__dict__
        if not s['bridge_ip'] or not s['bridge_user'] or not s['bridge_key']:
            return {'authorised': False} | s

        bridge = Bridge(s)
        if not bridge.is_authorised():
            return {'authorised': False} | s

        return {'authorised': True} | s

    def _get_rooms(self):
        s = _get_settings().__dict__
        if not s['bridge_ip'] or not s['bridge_user'] or not s['bridge_key']:
            return { 'rooms': [] }

        bridge = Bridge(s)
        r = bridge.search('room')
        if not r['success']:
            error = (
                'I was not able to find the bridge because of the following '
                f'error: {r["error"]}. Try re-authorising.'
            )
            messages.warning(self.request, error)
            return {'rooms': []}

        return {
            'rooms': [
                {'id': x['id'], 'name': x['metadata']['name']}
                for x in r['records']
            ]
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


class LightsInitiateDailyScenes(View):
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

        if request.POST['action_type'] == 'initiate':
            return self.initiate_daily_scenes(room)
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

        from pprint import pprint
        pprint(lights)
        raise Exception

        # Build Scenes
        scenes = ['Morning', 'Day', 'Evening', 'Night']
        for scene in scenes:
            # Post scenes
            action_sets = self._collate_actions_for_scene(scene, lights)
            for action_set in action_sets:
                r = self.bridge.post(
                    'scene',
                    self._collate_payload_for_scene(scene, room, action_set)
                )
                if not r['success']:
                    error = (
                        'Sorry, I was not able to create the main scene for the '
                        f"{scene} in the {room['metadata']['name']} because of the "
                        f"following error. {r['errors']}"
                    )
                    messages.warning(self.request, error)
                    return HttpResponseRedirect(reverse_lazy('lights'))

            # Post transition rule
            transition_time = self.s[f"{scene.lower()}_time"]
            r = self.bridge.post(
                'rules',
                self._collate_payload_for_transition(
                    room,
                    scene,
                    self._construct_time_interval_string(transition_time),
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

    def _collate_actions_for_scene(self, scene, lights):
        main = []
        lamps = []
        for light in lights:
            main_action = {
                'target': {
                    'rid': light['light_service_id'],
                    'rtype': 'light'
                },
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
            lamp_action = {
                'target': {
                    'rid': light['light_service_id'],
                    'rtype': 'light'
                },
                'action': {
                    'on': {'on': light['is_lamp']},
                    'dimming': {
                        'brightness': self.s[f"{scene.lower()}_brightness"]
                    },
                    'color_temperature': {
                        'mirek': self.s[f"{scene.lower()}_mirek"]
                    },
                }
            }
            main.append(main_action)
            lamps.append(lamp_action)

        from pprint import pprint
        pprint(main)
        pprint(lamps)

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
            "name": f"{room['metadata']['name']} >> {scene}",
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

    def _construct_time_interval_string(self, t):
        h = t.hour
        m = t.minute
        ss = t.second
        se = t.second + 1
        return f"T{h:02}:{m:02}:{ss:02}/T{h:02}:{m:02}:{se:02}"


# Utils
def _get_settings():
    if not LightsSettings.objects.all().exists():
        LightsSettings().save()
    return LightsSettings.objects.all().first()