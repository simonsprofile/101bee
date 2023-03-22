from .bridge_api import Bridge
from .models import LightsSettings
from django.contrib import messages
import copy
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


class Workflows:
    def __init__(self, request, room, devices):
        self.s = get_settings().__dict__
        self.bridge = Bridge(self.s)

        self.request = request
        self.room = room
        self.room_name = room['metadata']['name']
        self.room_name_min = self.room_name.replace(' ', '')
        self.scenes = self._get_scenes_for_room()
        self.lights = self._get_lights_in_room()

        self.switches = devices['switches']
        self.sensors = devices['sensors']
        self.button = devices['button']
        self.records_posted = []
        self.schedule = None
        self.flag = None
        self.occupancy_status = None
        self.light_level_sensor = None
        self.switch_suffix = 0 if len(self.switches) > 1 else ''
        self.sensor_suffix = 0 if len(self.sensors) > 1 else ''
        self.scene_names = ['Morning', 'Day', 'Evening', 'Night']
        self.generic_buttons = [
            {'suffix': 'Off', 'op_value': '4000', 'body': {'on': False}},
            {'suffix': 'DimDn', 'op_value': '3000', 'body': {'bri_inc': -39}},
            {'suffix': 'DimUp', 'op_value': '2000', 'body': {'bri_inc': 39}},
        ]
        self.pluralise = ''

    def create_daily_scenes(self):
        self.pluralise = 'Daily Scenes'
        r = self.bridge.search('rules')
        if not r['success']:
            self.failure('getting rule data', r['errors'])
        rule_names = [x['name'] for x in r['records'].values()]

        # Create Scenes
        for time_of_day in self.scene_names:
            # Create Scenes
            existing_scene_names = [x['metadata']['name'] for x in self.scenes]
            lamps_scene = False
            post_it = True
            for _ in range(2):
                scene_name = time_of_day
                if lamps_scene:
                    scene_name = f"Lamps for {time_of_day}"
                exists = scene_name in existing_scene_names
                if post_it and not exists:
                    r = self.bridge.post(
                        'scene',
                        self.payload__scene(time_of_day, lamps_scene)
                    )
                    if not r['success']:
                        self._failure(
                            f"creating new scene for {scene_name}",
                            r['errors']
                        )
                lamps_scene = True
                post_it = self._room_has_lamps()

            # Create Transition Rule
            rule_name = f"{self.room_name_min}>>{time_of_day}"
            if not rule_name in rule_names:
                r = self.bridge.post(
                    'rules',
                    self.payload__transition_rule(time_of_day)
                )
                if not r['success']:
                    self._failure(
                        f"creating new transition rule for {time_of_day}",
                        r['errors']
                    )

        self._create_success()

    def remove_daily_scenes(self):
        self.pluralise = 'Daily Scenes'

        scenes_to_remove = self.scene_names + [
            f"Lamps for {x}" for x in self.scene_names
        ]
        for scene in self.scenes:
            if scene['metadata']['name'] in scenes_to_remove:
                r = self.bridge.delete('scene', scene['id'])
                if not r['success']:
                    self._failure(
                        f"deleting scene {scene['metadata']['name']}",
                        r['errors']
                    )

        r = self.bridge.search('rules')
        if not r['success']:
            self.failure('getting rule data', r['errors'])
        for id_v1, rule in r['records'].items():
            for scene_name in self.scene_names:
                rule_to_delete = f"{self.room_name_min}>>{scene_name}"
                if rule['name'] == rule_to_delete:
                    r = self.bridge.delete('rules', id_v1)
                    if not r['success']:
                        self._failure('deleting rule', r['errors'])
        self._remove_success()

    def create_switch_configuration(self):
        self.pluralise = 'Switch' if len(self.switches) == 1 else 'Switches'
        self._check_config_exists()
        self._check_daily_scenes_exist()

        if self._has_lamps_scenes():
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
                if self._has_lamps_scenes():
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

    def remove_switch_configuration(self):
        self.pluralise = 'Switch Configuration'
        config = self._get_resourcelink('Switches')
        if not config:
            config = self._get_resourcelink('Switch')
            if not config:
                message = (
                    "I couldn't find a switch configuration for the "
                    f"{self.room_name}."
                )
                messages.warning(self.request, message)
                return
        self._delete_records_in(config)
        return self._remove_success()

    def create_sensor_configuration(self, delay):
        self.pluralise = 'Sensor' if len(self.sensors) == 1 else 'Sensors'

        config_exists = self._config_exists()
        if config_exists:
            return self._failure(
                'checking compatibility with the bridge',
                config_exists
            )

        self.occupancy_status = self._post(
            'posting Occupancy Status Sensor',
            'sensors',
            self.payload__status_sensor()
        )

        for sensor in self.sensors:
            self.light_level_sensor = self._get_light_level_sensor_for(sensor)
            if len(self.switches) > 1:
                self.switch_suffix += 1

            record = self._post(
                f"posting Occupancy Detected 1 rule",
                'rules',
                self.payload__occupancy_1(sensor)
            )
            record = self._post(
                f"posting Occupancy Detected 2 rule",
                'rules',
                self.payload__occupancy_2(sensor)
            )
            record = self._post(
                f"posting Dim (No Motion) rule",
                'rules',
                self.payload__dim_no_motion(sensor, delay)
            )
            record = self._post(
                f"posting Off (No Motion) rule",
                'rules',
                self.payload__off_no_motion(sensor)
            )
            if self.button:
                record = self._post(
                    f" posting Sensor Snooze rule",
                    'rules',
                    self.payload__sensor_snooze()
                )
                record = self._post(
                    f" posting Sensor Un-Snooze rule",
                    'rules',
                    self.payload__sensor_unsnooze()
                )
                record = self._post(
                    f" posting Button Off rule",
                    'rules',
                    self.payload__button_off()
                )

            for scene_name in self.scene_names:
                record = self._post(
                    f"posting {scene_name} On rule",
                    'rules',
                    self.payload__sensor_on(scene_name)
                )
                if self.button:
                    record = self._post(
                        f" posting {scene_name} Button On rule",
                        'rules',
                        self.payload__button_on(scene_name)
                    )

        return self._create_success()

    def remove_sensor_configuration(self):
        self.pluralise = 'Sensor Configuration'
        config = self._get_resourcelink('Sensors')
        if not config:
            config = self._get_resourcelink('Sensor')
            if not config:
                message = (
                    "I couldn't find a sensor configuration for the "
                    f"{self.room_name}."
                )
                messages.warning(self.request, message)
                return
        self._delete_records_in(config)
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
        message = f"{self.pluralise} configured for the {self.room_name}."
        messages.success(self.request, message)
        return

    def _remove_success(self):
        message = f"{self.pluralise} removed for the {self.room_name}."
        messages.success(self.request, message)
        return

    # Validation
    def _check_config_exists(self):
        switches = self._get_resourcelink('Switches')
        sensors = self._get_resourcelink('Sensors')
        if switches or sensors:
            message = 'switches' if switches else 'sensors'
            error = (
                f"There is already an existing configuration for {message} "
                f"in the {self.room_name}. Please remove that "
                f"configuration before creating a new one."
            )
            return self._failure('checking for existing configuration', error)
        return

    def _check_daily_scenes_exist(self):
        existing_scene_names = [x['metadata']['name'] for x in self.scenes]
        required_scenes_exist = all(
            x in existing_scene_names for x in self.scene_names
        )
        if not required_scenes_exist:
            error = (
                "The required 'Daily Scenes' do not exist for the "
                f"{self.room_name}. Please initiate these scenes first."
            )
            return self._failure('checking for Daily Scenes', error)
        return

    def _has_lamps_scenes(self):
        existing_scene_names = [x['metadata']['name'] for x in self.scenes]
        lamps_scene_names = [f"Lamps for {x}" for x in self.scene_names]
        return all(
            x in existing_scene_names for x in lamps_scene_names
        )

    def _room_has_lamps(self):
        return True in [x['is_lamp'] for x in self.lights]

    # Serializers
    # For Daily Scenes
    def payload__scene(self, scene_name, lamps_only):
        action_template = {
            'target': {'rid': None, 'rtype': 'light'},
            'action': {
                'on': {'on': True},
                'dimming': {
                    'brightness': self.s[f"{scene_name.lower()}_brightness"]
                },
                'color_temperature': {
                    'mirek': self.s[f"{scene_name.lower()}_mirek"]
                },
            }
        }
        scene_name = f"Lamps for {scene_name}" if lamps_only else scene_name
        actions = []
        for light in self.lights:
            action = copy.deepcopy(action_template)
            action['target']['rid'] = light['light_service_id']
            if lamps_only:
                action['action']['on']['on'] = light['is_lamp']
            actions.append(action)
        return {
            'metadata': {
                'name': scene_name
            },
            'group': {'rid': self.room['id'], 'rtype': 'room'},
            'speed': 0.5,
            'type': 'scene',
            'actions': actions
        }

    def payload__transition_rule(self, time_of_day):
        mirek = self.s[f"{time_of_day.lower()}_mirek"]
        t = self.s[f"{time_of_day.lower()}_time"]
        interval = (
            f"T{t.hour:02}:{t.minute:02}:{t.second:02}/"
            f"T{t.hour:02}:{t.minute:02}:{t.second + 1:02}"
        )
        return {
            "name": f"{self.room_name_min}>>{time_of_day}",
            "recycle": False,
            "conditions": [
                {
                    "address": f"{self.room['id_v1']}/state/any_on",
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
                    "address": f"{self.room['id_v1']}/action",
                    "method": "PUT",
                    "body": {"ct": mirek, "transitiontime": 6000}
                }
            ]
        }

    # For Switch Config
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

    # For Sensor Config
    def payload__status_sensor(self):
        return {
            'name': f"{self.room_name_min}Occupancy",
            'type': 'CLIPGenericStatus',
            'modelid': 'Numeric Status',
            'manufacturername': 'Barry Butler',
            'swversion': 'Current',
            'uniqueid': ''.join(
                random.choices(string.ascii_uppercase + string.digits, k=8)
            )
        }

    def payload__occupancy_1(self, sensor):
        return {
            "name": f"{self.room_name_min}Motion1",
            "recycle": False,
            "conditions": [
                {
                    "address": f"{self.light_level_sensor['id_v1']}/state/dark",
                    "operator": "eq",
                    "value": "true"
                },
                {
                    "address": f"{self.occupancy_status['id_v1']}/state/status",
                    "operator": "eq",
                    "value": "0"
                },
                {
                    "address": f"{sensor['id_v1']}/state/presence",
                    "operator": "dx"
                },
                {
                    "address": f"{sensor['id_v1']}/state/presence",
                    "operator": "eq",
                    "value": "true"
                }
            ],
            "actions": [
                {
                    "address": f"{self.occupancy_status['id_v1']}/state",
                    "method": "PUT",
                    "body": {"status": 1}
                }
            ]
        }

    def payload__occupancy_2(self, sensor):
        return {
            "name": f"{self.room_name_min}Motion2",
            "recycle": False,
            "conditions": [
                {
                    "address": f"{self.occupancy_status['id_v1']}/state/status",
                    "operator": "gt",
                    "value": "0"
                },
                {
                    "address": f"{self.occupancy_status['id_v1']}/state/status",
                    "operator": "lt",
                    "value": "3"
                },
                {
                    "address": f"{sensor['id_v1']}/state/presence",
                    "operator": "dx"
                },
                {
                    "address": f"{sensor['id_v1']}/state/presence",
                    "operator": "eq",
                    "value": "true"
                }
            ],
            "actions": [
                {
                    "address": f"{self.occupancy_status['id_v1']}/state",
                    "method": "PUT",
                    "body": {"status": 1}
                },

            ]
        }

    def payload__dim_no_motion(self, sensor, delay):
        return {
            "name": f"{self.room_name_min}DimNoMotion",
            "recycle": False,
            "conditions": [
                {
                    "address": f"{self.room['id_v1']}/state/any_on",
                    "operator": "eq",
                    "value": "true"
                },
                {
                    "address": f"{self.occupancy_status['id_v1']}/state/status",
                    "operator": "lt",
                    "value": "3"
                },
                {
                    "address": f"{sensor['id_v1']}/state/presence",
                    "operator": "eq",
                    "value": "false"
                },
                {
                    "address": f"{sensor['id_v1']}/state/presence",
                    "operator": "ddx",
                    "value": self._build_duration_from_delay(delay)
                },

            ],
            "actions": [
                {
                    "address": f"{self.occupancy_status['id_v1']}/state",
                    "method": "PUT",
                    "body": {"status": 2}
                },
                {
                    "address": f"{self.room['id_v1']}/action",
                    "method": "PUT",
                    "body": {"bri_inc": -128, "transitiontime": 20}
                }
            ]
        }

    def payload__off_no_motion(self, sensor):
        return {
            "name": f"{self.room_name_min}OffNoMotion",
            "recycle": False,
            "conditions": [
                {
                    "address": f"{self.occupancy_status['id_v1']}/state/status",
                    "operator": "eq",
                    "value": "2"
                },
                {
                    "address": (
                        f"{self.occupancy_status['id_v1']}/state/lastupdated"
                    ),
                    "operator": "ddx",
                    "value": "PT00:00:20"
                },
                {
                    "address": f"{sensor['id_v1']}/state/presence",
                    "operator": "eq",
                    "value": "false"
                }
            ],
            "actions": [
                {
                    "address": f"{self.occupancy_status['id_v1']}/state",
                    "method": "PUT",
                    "body": {"status": 0}
                },
                {
                    "address": f"{self.room['id_v1']}/action",
                    "method": "PUT",
                    "body": {"on": False}
                }
            ]
        }

    def payload__sensor_on(self, scene_name):
        scene = [
            x for x in self.scenes
            if x['metadata']['name'] == scene_name
        ][0]
        return {
            "name": f"{self.room_name_min}On{scene_name}",
            "recycle": False,
            "conditions": [
                {
                    "address": f"{self.occupancy_status['id_v1']}/state/status",
                    "operator": "eq",
                    "value": "1"
                },
                {
                    "address": f"{self.occupancy_status['id_v1']}/state/status",
                    "operator": "dx"
                },
                {
                    'address': '/config/localtime',
                    'operator': 'in',
                    'value': self._build_time_interval_string(scene_name)
                }
            ],
            "actions": [
                {
                    "address": f"{self.room['id_v1']}/action",
                    "method": "PUT",
                    "body": {"scene": scene['id_v1'].replace('/scenes/', '')}
                }
            ]
        }

    def payload__sensor_snooze(self):
        return {
            "name": f"{self.room_name_min}SensorSnooze",
            "recycle": False,
            "conditions": [
                {
                    "address": f"{self.occupancy_status['id_v1']}/state/status",
                    "operator": "lt",
                    "value": "3"
                },
                {
                    "address": f"{self.button['id_v1']}/state/buttonevent",
                    "operator": "dx"
                },
                {
                    "address": f"{self.button['id_v1']}/state/buttonevent",
                    "operator": "eq",
                    "value": "1010"
                }
            ],
            "actions": [
                {
                    "address": f"{self.occupancy_status['id_v1']}/state",
                    "method": "PUT",
                    "body": {"status": 3}
                },
                {
                    "address": f"{self.room['id_v1']}/action",
                    "method": "PUT",
                    "body": {"alert": "select"}
                }
            ]
        }

    def payload__sensor_unsnooze(self):
        return {
            "name": f"{self.room_name_min}SensorUnSnooze",
            "recycle": False,
            "conditions": [
                {
                    "address": f"{self.occupancy_status['id_v1']}/state/status",
                    "operator": "eq",
                    "value": "3"
                },
                {
                    "address": f"{self.button['id_v1']}/state/buttonevent",
                    "operator": "dx"
                },
                {
                    "address": f"{self.button['id_v1']}/state/buttonevent",
                    "operator": "eq",
                    "value": "1010"
                }
            ],
            "actions": [
                {
                    "address": f"{self.occupancy_status['id_v1']}/state",
                    "method": "PUT",
                    "body": {"status": 0}
                },
                {
                    "address": f"{self.room['id_v1']}/action",
                    "method": "PUT",
                    "body": {"on": False}
                },
                {
                    "address": f"{self.room['id_v1']}/action",
                    "method": "PUT",
                    "body": {"alert": "select"}
                }
            ]
        }

    def payload__button_on(self, scene_name):
        scene = [
            x for x in self.scenes
            if x['metadata']['name'] == scene_name
        ][0]
        return {
            "name": f"{self.room_name_min}BtnOn{scene_name}",
            "recycle": False,
            "conditions": [
                {
                    "address": f"{self.occupancy_status['id_v1']}/state/status",
                    "operator": "eq",
                    "value": "3"
                },
                {
                    "address": f"{self.room['id_v1']}/state/any_on",
                    "operator": "eq",
                    "value": "false"
                },
                {
                    "address": f"{self.button['id_v1']}/state/buttonevent",
                    "operator": "dx"
                },
                {
                    "address": f"{self.button['id_v1']}/state/buttonevent",
                    "operator": "eq",
                    "value": "1000"
                },
                {
                    'address': '/config/localtime',
                    'operator': 'in',
                    'value': self._build_time_interval_string(scene_name)
                }
            ],
            "actions": [
                {
                    "address": f"{self.room['id_v1']}/action",
                    "method": "PUT",
                    "body": {"scene": scene['id_v1'].replace('/scenes/', '')}
                }
            ]
        }

    def payload__button_off(self):
        return {
            "name": f"{self.room_name_min}BtnOff",
            "recycle": False,
            "conditions": [
                {
                    "address": f"{self.occupancy_status['id_v1']}/state/status",
                    "operator": "eq",
                    "value": "3"
                },
                {
                    "address": f"{self.room['id_v1']}/state/any_on",
                    "operator": "eq",
                    "value": "true"
                },
                {
                    "address": f"{self.button['id_v1']}/state/buttonevent",
                    "operator": "dx"
                },
                {
                    "address": f"{self.button['id_v1']}/state/buttonevent",
                    "operator": "eq",
                    "value": "1000"
                }
            ],
            "actions": [
                {
                    "address": f"{self.room['id_v1']}/action",
                    "method": "PUT",
                    "body": {"on": False}
                }
            ]
        }

    # Resource Link
    def payload__resource_link(self):
        return {
            'name': f"{self.room_name_min}{self.pluralise}",
            'description': f"Barry Butler {self.pluralise} Configuration.",
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

    def _get_lights_in_room(self):
        lights = []
        for child in self.room['children']:
            r = self.bridge.get(child['rtype'], child['rid'])
            if not r['success']:
                self._failure('finding lights', r['errors'])
            r['record']['is_lamp'] = \
                'lamp' in r['record']['metadata']['name'].lower()

            is_light = \
                'light' in [x['rtype'] for x in r['record']['services']]
            if is_light:
                for service in r['record']['services']:
                    if service['rtype'] == 'light':
                        r['record']['light_service_id'] = service['rid']
                lights.append(r['record'])
        return lights

    def _get_light_level_sensor_for(self, sensor):
        r = self.bridge.get('sensors', sensor['id_v1'].replace('/sensors/', ''))
        if not r['success']:
            self._failure('getting v1 presence sensor', r['errors'])
        presence_sensor = r['record']
        r = self.bridge.search('sensors')
        if not r['success']:
            self._failure('getting Sensor list', r['errors'])
        all_sensors = [
            (y | {'id_v1': f"/sensors/{x}"}) for x, y in r['records'].items()
            if 'uniqueid' in y
        ]
        unique_id = presence_sensor['uniqueid'][:27]
        try:
            return [
                x for x in all_sensors if x['uniqueid'] == f"{unique_id}0400"
            ][0]
        except IndexError:
            self._failure('finding light sensor', 'Light sensor not found!')

    def _get_resourcelink(self, type):
        r = self.bridge.search('resourcelinks')
        if not r['success']:
            self._failure(
                'getting Resource Links',
                r['errors']
            )
        name = f"{self.room_name_min}{type}"
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

    def _delete_records_in(self, config):
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
        return

        return self._remove_success()

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

    def _build_duration_from_delay(self, delay):
        s = int(delay % 1 * 60 - 20)
        m = int(delay)
        if s < 0:
            m -= 1
            s = 40
        return f"PT00:{m:02}:{s:02}"
