from django.views.generic import View, TemplateView
from django.template.response import TemplateResponse
from django.http import HttpResponseRedirect, HttpResponse
from django.urls import reverse_lazy
from .models import LightsSettings
from .bridge_api import Bridge
from django.contrib import messages


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
                (
                    'There was a was an error reported when trying to authorise:\n'
                    f'{r["message"]}'
                )
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
        s = _get_settings().__dict__
        bridge = Bridge(s)

        # Get Room
        r = bridge.get('room', request.POST['room_id'])
        if not r['success']:
            error = (
                'Sorry, I was unable to find the room information because of '
                f"the following error. Try re-authorising: {r['errors']}"
            )
            messages.warning(request, error)
            return HttpResponseRedirect(reverse_lazy('lights'))
        room = r['record']

        # Get Devices in Room
        lights = []
        for child in room['children']:
            r = bridge.get(child['rtype'], child['rid'])
            if not r['success']:
                error = (
                    'Sorry, I was unable to find the room information '
                    'because of the following error. '
                    f"Try re-authorising: {r['errors']}"
                )
                messages.warning(request, error)
                return HttpResponseRedirect(reverse_lazy('lights'))
            r['record']['is_lamp'] = \
                'lamp' in r['record']['metadata']['name'].lower()

            is_light = \
                'light' in [x['rtype'] for x in r['record']['services']]
            if is_light:
                for service in r['record']['services']:
                    if service['rtype'] == 'light':
                        r['record']['light_service_id'] = service['rid']
                lights.append(r['record'])

        # Build Scenes
        scenes = ['Morning', 'Day', 'Evening', 'Night']
        for scene in scenes:
            main_actions, lamp_actions = self._collate_lights_into_actions(
                s, scene, lights
            )

            main_scene_payload = {
                'metadata': {
                    'name': scene
                },
                'group': {'rid': room['id'], 'rtype': 'room'},
                'speed': 0.5,
                'type': 'scene',
                'actions': main_actions
            }

            r = bridge.post('scene', main_scene_payload)
            if not r['success']:
                error = (
                    'Sorry, I was not able to create the main scene for the '
                    f"{scene} in the {room['metadata']['name']} because of the "
                    f"following error. {r['errors']}"
                )
                messages.warning(request, error)
                return HttpResponseRedirect(reverse_lazy('lights'))

            lamp_scene_payload = {
                'metadata': {
                    'name': f"Lamps for {scene}"
                },
                'group': {'rid': room['id'], 'rtype': 'room'},
                'speed': 0.5,
                'type': 'scene',
                'actions': lamp_actions
            }

            r = bridge.post('scene', lamp_scene_payload)
            if not r['success']:
                error = (
                    'Sorry, I was not able to create the lamp scene for the '
                    f"{scene} in the {room['metadata']['name']} because of the "
                    f"following error. {r['errors']}"
                )
                messages.warning(request, error)
                return HttpResponseRedirect(reverse_lazy('lights'))

        messages.success(request, 'Daily scenes created!')

        return HttpResponseRedirect(reverse_lazy('lights'))

    def _collate_lights_into_actions(self, s, scene, lights):
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
                        'brightness': s[f"{scene.lower()}_brightness"]
                    },
                    'color_temperature': {
                        'mirek': s[f"{scene.lower()}_mirek"]
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
                        'brightness': s[f"{scene.lower()}_brightness"]
                    },
                    'color_temperature': {
                        'mirek': s[f"{scene.lower()}_mirek"]
                    },
                }
            }
            main.append(main_action)
            lamps.append(lamp_action)

        return main, lamps


# Utils
def _get_settings():
    if not LightsSettings.objects.all().exists():
        LightsSettings().save()
    return LightsSettings.objects.all().first()