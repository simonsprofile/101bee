from .bridge_api import Bridge
from .models import LightsSettings
from django.contrib import messages
import random
import string


# Utils
def get_settings():
    if not LightsSettings.objects.all().exists():
        LightsSettings().save()
    return LightsSettings.objects.all().first()


class WorkflowException(Exception):
    def __init__(self, message):
        super().__init__(message)


class DailyScenesForRoom:
    pass


class SwitchesForRoom:
    def __init__(self, request, room, switches=None):
        self.s = get_settings().__dict__
        self.bridge = Bridge(self.s)

        self.request = request
        self.room = room
        self.room_name = room['metadata']['name']
        self.room_name_min = self.room_name.replace(' ', '')
        self.scenes = self._get_scenes_for_room()

        self.switches = switches
        self.records_posted = []
        self.schedule = None
        self.flag = None
        self.switch_suffix = 0 if len(switches) > 1 else ''
        self.scene_names = ['Morning', 'Day', 'Evening', 'Night']
        self.generic_buttons = [
            {'suffix': 'Off', 'op_value': '4000', 'body': {'on': False}},
            {'suffix': 'DimDn', 'op_value': '3000', 'body': {'bri_inc': -39}},
            {'suffix': 'DimUp', 'op_value': '2000', 'body': {'bri_inc': 39}},
        ]

    def create_configuration(self):
        is_not_compatible = self._is_not_compatible()
        if is_not_compatible:
            return self._failure(
                'checking compatibility with the bridge',
                is_not_compatible
            )

        if self._has_lamps():
            self.flag = self._post(
                'posting Click Check Sensor',
                'sensors',
                self.payload__click_check_sensor()
            )

            self.schedule = self._post(
                'posting Click Check Schedule',
                'schedules',
                self.payload__click_check_schedule()
            )

        for switch in self.switches:
            if len(self.switches) > 1:
                self.switch_suffix += 1

            for button in self.generic_buttons:
                record = self._post(
                    f"posting {button['suffix']} button rule",
                    'rules',
                    self.payload__generic_button(switch, button)
                )

            for scene_name in self.scene_names:
                if self._has_lamps():
                    record = self._post(
                        f"posting {scene_name} Lamps On button rule",
                        'rules',
                        self.payload__on_button_lamps(switch, scene_name)
                    )
                    record = self._post(
                        f"posting {scene_name} Main On button rule",
                        'rules',
                        self.payload__on_button_main(switch, scene_name)
                    )

                else:
                    record = self._post(
                        f"posting {scene_name} On button rule",
                        'rules',
                        self.payload__on_button_no_lamps(switch, scene_name)
                    )

        return self._create_success()

    def remove_configuration(self):
        config = self._get_resourcelink()
        if not config:
            message = (
                "I couldn't find a switch configuration for the "
                f"{self.room_name}."
            )
            messages.warning(self.request, message)
            return
        for link in config['links']:
            r = self.bridge.delete(link.split('/')[1], link.split('/')[2])
            if not r['success']:
                self._failure('removing existing configuration', r['errors'])
        r = self.bridge.delete(
            config['id_v1'].split('/')[1],
            config['id_v1'].split('/')[2]
        )
        if not r['success']:
            self._failure('removing existing configuration', r['errors'])

        return self._remove_success()

    # Handle failure
    def _failure(self, task, message):
        error = (
            f"Unfortunately while I was {task} the "
            f"following error was returned: {message}"
        )
        self._cleanup()
        raise WorkflowException(error)

    def _cleanup(self):
        for record in self.records_posted:
            if record['endpoint'] in self.bridge.v1_endpoints():
                rid = record['id_v1'].replace(f"/{record['endpoint']}/", '')
            else:
                rid = record['id']
            r = self.bridge.delete(record['endpoint'], rid)
            if not r['success']:
                message = (
                    f"While trying to cleanup, I couldn't delete the record "
                    f"{rid} from {record['endpoint']}. The following error was "
                    f"returned: {r['errors']}"
                )
                messages.warning(self.request, message)

    # Handle success
    def _create_success(self):
        record = self._post(
            'creating Resource Link set',
            'resourcelinks',
            self.payload__resource_link()
        )
        pluralise = 'Switches' if len(self.switches) > 1 else 'Switch'
        message = f"{pluralise} configured for the {self.room_name}."
        messages.success(self.request, message)
        return

    def _remove_success(self):
        message = f"Switch configuration removed for the {self.room_name}."
        messages.success(self.request, message)
        return

    # Validation
    def _is_not_compatible(self):
        configuration_exists = self._get_resourcelink()
        if configuration_exists:
            return (
                f"An existing configuration for the {self.room_name}. "
                'Please remove that configuration before creating a new one.'
            )

        existing_scene_names = [x['metadata']['name'] for x in self.scenes]
        required_scenes_exist = all(
            x in existing_scene_names for x in self.scene_names
        )
        if not required_scenes_exist:
            return (
                "The required 'Daily Scenes' do not exist for the "
                f"{self.room_name}. Please initiate these scenes first."
            )

        return False

    def _has_lamps(self):
        existing_scene_names = [x['metadata']['name'] for x in self.scenes]
        lamps_scene_names = [f"Lamps for {x}" for x in self.scene_names]
        return all(
            x in existing_scene_names for x in lamps_scene_names
        )

    # Serializers
    def payload__generic_button(self, switch, button):
        return {
            'name': (
                f"{self.room_name_min}{button['suffix']}{self.switch_suffix}"
            ),
            'conditions': [
                {
                    'address': f"{switch['id_v1']}/state/buttonevent",
                    'operator': 'eq',
                    'value': button['op_value']
                },
                {
                    'address': f"{switch['id_v1']}/state/lastupdated",
                    'operator': 'dx'
                }
            ],
            'actions': [
                {
                    'address': f"{self.room['id_v1']}/action",
                    'method': 'PUT',
                    'body': button['body']
                }
            ]
        }

    def payload__on_button_no_lamps(self, switch, scene_name):
        scene = [
            x for x in self.scenes
            if scene_name == x['metadata']['name']
        ][0]
        return {
            'name': f"{self.room_name_min}{scene_name}On{self.switch_suffix}",
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
                    'value': self._build_time_interval_string(scene_name)
                }
            ],
            'actions': [
                {
                    'address': f"{self.room['id_v1']}/action",
                    'method': 'PUT',
                    'body': {'scene': scene['id_v1'].replace('/scene/', '')}
                }
            ]
        }

    def payload__click_check_sensor(self):
        return {
            "name": f"{self.room_name_min}Clicked",
            "type": "CLIPGenericFlag",
            "modelid": "True/False Flag",
            "manufacturername": "Barry Butler",
            "swversion": "Current",
            "uniqueid": ''.join(
                random.choices(string.ascii_uppercase + string.digits, k=8)
            )
        }

    def payload__click_check_schedule(self):
        return {
            'name': f"{self.room_name_min}Clicked",
            'command': {
                'address': (
                    f"/api/{self.s['bridge_user']}"
                    f"{self.flag['id_v1']}/state"
                ),
                'body': {'flag': False},
                'method': 'PUT'
            },
            'time': 'PT00:00:01',
            'autodelete': False
        }

    def payload__on_button_main(self, switch, scene_name):
        scene = [
            x for x in self.scenes
            if x['metadata']['name'] == scene_name
        ][0]
        return {
            'name': f"{self.room_name_min}{scene_name}On{self.switch_suffix}",
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
                    'value': self._build_time_interval_string(scene_name)
                },
                {
                    'address': f"{self.flag['id_v1']}/state/flag",
                    'operator': 'eq',
                    'value': 'true'
                }
            ],
            'actions': [
                {
                    'address': f"{self.room['id_v1']}/action",
                    'method': 'PUT',
                    'body': {'scene': scene['id_v1'].replace('/scenes/', '')}
                }
            ]
        }

    def payload__on_button_lamps(self, switch, scene_name):
        scene = [
            x for x in self.scenes
            if f"Lamps for {scene_name}" == x['metadata']['name']
        ][0]
        return {
            'name': (
                f"Lamps{self.room_name_min}{scene_name}On{self.switch_suffix}"
            ),
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
                    'value': self._build_time_interval_string(scene_name)
                },
                {
                    'address': f"{self.flag['id_v1']}/state/flag",
                    'operator': 'eq',
                    'value': 'false'
                }
            ],
            'actions': [
                {
                    'address': f"{self.room['id_v1']}/action",
                    'method': 'PUT',
                    'body': {'scene': scene['id_v1'].replace('/scenes/', '')}
                },
                {
                    "address": f"{self.flag['id_v1']}/state",
                    "method": "PUT",
                    "body": {"flag": True}
                },
                {
                    "address": f"{self.schedule['id_v1']}",
                    "method": "PUT",
                    "body": {"status": "enabled"}
                }
            ]
        }

    def payload__resource_link(self):
        return {
            'name': f"{self.room_name_min}Switches",
            'description': 'Barry Butler switch config.',
            'classid': 1,
            'recycle': False,
            'links': [x['id_v1'] for x in self.records_posted]
        }

    # Utils
    def _get_scenes_for_room(self):
        r = self.bridge.search('scene')
        if not r['success']:
            self._failure(
                'getting existing scenes for this room',
                r['errors']
            )
        return [x for x in r['records'] if x['group']['rid'] == self.room['id']]

    def _get_resourcelink(self):
        r = self.bridge.search('resourcelinks')
        if not r['success']:
            self._failure(
                'getting Resource Links',
                r['errors']
            )
        name = f"{self.room_name_min}Switches"
        if name in [x['name'] for x in r['records'].values()]:
            return [
                y | {'id_v1': f"/resourcelinks/{x}"}
                for x, y in r['records'].items()
                if y['name'] == name
            ][0]
        return

    def _post(self, task, endpoint, payload):
        r = self.bridge.post(endpoint, payload)
        if not r['success']:
            self._failure(task, r['errors'])
        record = r['record'] | {'endpoint': endpoint}
        self.records_posted.append(record)
        return r['record']

    def _build_time_interval_string(self, scene_name):
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


class SensorsForRoom:
    pass
