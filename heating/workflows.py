import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from heating.models import (ClimateSensor,
                            HeatPumpStatusRecord,
                            ClimateSensorRecord)
from lights.bridge_api import Bridge
from lights.models import LightsSettings
from scribe.models import WorkflowError
from .daikin_api import DaikinApi


class Heating:
    def __init__(self):
        # Init Hue API
        self.hue = Bridge(self._light_settings().__dict__)

        # Init Daikin API and collect data
        daikin = DaikinApi()
        self.daikin_error = False
        self.current_temps = None
        r = daikin.current_temps()
        if not r['success']:
            self.daikin_error = r['message']
        else:
            self.daikin_temps = r['temps']

    def record_current_data(self):
        # Initialize heat pump data
        heat_pump_status = HeatPumpStatusRecord()
        if not self.daikin_error:
            heat_pump_status.room_setpoint = self.daikin_temps['room_setpoint']
            heat_pump_status.tank_setpoint = self.daikin_temps['tank_setpoint']
            heat_pump_status.return_temperature = self.daikin_temps['flow']

        # Collect data from climate sensors
        sensors = ClimateSensor.objects.all()
        for sensor in sensors:
            print(f'Contacting {sensor.name}')
            if sensor.type == 'hue_presence_sensor':
                if self.hue.is_authorised():
                    climate_data = self._collect_hue_climate_data(sensor)
                    ClimateSensorRecord(
                        sensor=sensor,
                        temperature=climate_data['temperature'],
                        ambient_light=climate_data['ambient_light']
                    ).save()
            elif sensor.type == 'daikin_thermostat':
                if not self.daikin_error:
                    ClimateSensorRecord(
                        sensor=sensor,
                        temperature=self.daikin_temps['room']
                    ).save()
            elif sensor.type == 'daikin_tank':
                if not self.daikin_error:
                    ClimateSensorRecord(
                        sensor=sensor,
                        temperature=self.daikin_temps['hot_water']
                    ).save()
            elif sensor.type == 'daikin_weather':
                if not self.daikin_error:
                    ClimateSensorRecord(
                        sensor=sensor,
                        temperature=self.daikin_temps['outdoor']
                    ).save()
            elif sensor.type == 'esp8266_heat_pump':
                try:
                    session = requests.Session()
                    retry = Retry(connect=5, backoff_factor=0.5)
                    adapter = HTTPAdapter(max_retries=retry)
                    session.mount('http://', adapter)
                    session.mount('https://', adapter)
                    r = session.get(f"http://{sensor.ip_address}/", timeout=10)
                    data = r.json()
                    r.close()
                    print(r)
                    if 'flow' in r and 'return' in r:
                        heat_pump_status.flow_temperature = round(
                            data['flow'], 2
                        )
                        heat_pump_status.return_temperature = round(
                            data['return'], 2
                        )
                    if 'air' in r:
                        cupboard_climate_record = ClimateSensorRecord(
                            sensor=sensor,
                            temperature=round(data['air'], 1)
                        )
                        if 'humidity' in r:
                            cupboard_climate_record.relative_humidity = round(
                                data['humidity'], 1
                            )
                        cupboard_climate_record.save()
                except requests.ConnectTimeout:
                    WorkflowError(
                        error='Connection Timeout',
                        description=(
                            f'{sensor.name} was not contactable at '
                            f'{sensor.ip_address}.'
                        )
                    ).save()
                except requests.ConnectionError:
                    WorkflowError(
                        error='Connection Error',
                        description=(
                            f'{sensor.name} was not contactable at '
                            f'{sensor.ip_address}.'
                        )
                    ).save()
            elif sensor.type == 'esp8266_room':
                try:
                    session = requests.Session()
                    retry = Retry(connect=5, backoff_factor=0.5)
                    adapter = HTTPAdapter(max_retries=retry)
                    session.mount('http://', adapter)
                    session.mount('https://', adapter)
                    r = session.get(f"http://{sensor.ip_address}/", timeout=10)
                    data = r.json()
                    r.close()
                    ClimateSensorRecord(
                        sensor=sensor,
                        temperature=round(data['air'], 1),
                        relative_humidity=round(data['humidity'], 1)
                    ).save()
                except requests.ConnectTimeout:
                    WorkflowError(
                        error='Connection Timeout',
                        description=(
                            f'{sensor.name} was not contactable  at '
                            f'{sensor.ip_address}.'
                        )
                    ).save()
                except requests.ConnectionError:
                    WorkflowError(
                        error='Connection Error',
                        description=(
                            f'{sensor.name} was not contactable at '
                            f'{sensor.ip_address}.'
                        )
                    ).save()

    # Utils
    def _collect_hue_climate_data(self, sensor):
        r = self.hue.get('sensors', sensor.hue_temp_id)
        if not r['success']:
            return r
        temperature = r['record']['state']['temperature'] / 100
        r =  self.hue.get('sensors', sensor.hue_light_id)
        if not r['success']:
            return r
        ambient_light = r['record']['state']['lightlevel']
        return {'temperature': temperature, 'ambient_light': ambient_light}

    def _light_settings(self):
        if not LightsSettings.objects.all().exists():
            LightsSettings().save()
        return LightsSettings.objects.all().first()

