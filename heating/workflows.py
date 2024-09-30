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
            heat_pump_status.flow_temperature = self.daikin_temps['flow']

        # Collect data from climate sensors
        sensors = ClimateSensor.objects.all()
        for sensor in sensors:
            print(f'Contacting {sensor.name}')
            if sensor.type == 'hue_presence_sensor':
                if self.hue.is_authorised():
                    climate_data = self._collect_hue_climate_data(sensor)
                    temperature = (
                        climate_data['temperature']
                        + sensor.temperature_offset
                    )
                    ClimateSensorRecord(
                        sensor=sensor,
                        temperature=temperature,
                        ambient_light=climate_data['ambient_light']
                    ).save()
            elif sensor.type == 'daikin_thermostat':
                if not self.daikin_error:
                    temperature = (
                            self.daikin_temps['room']
                            + sensor.temperature_offset
                    )
                    ClimateSensorRecord(
                        sensor=sensor,
                        temperature=temperature
                    ).save()
            elif sensor.type == 'daikin_tank':
                if not self.daikin_error:
                    temperature = (
                            self.daikin_temps['hot_water']
                            + sensor.temperature_offset
                    )
                    ClimateSensorRecord(
                        sensor=sensor,
                        temperature=temperature
                    ).save()
            elif sensor.type == 'daikin_weather':
                if not self.daikin_error:
                    temperature = (
                        self.daikin_temps['outdoor']
                        + sensor.temperature_offset
                    )
                    ClimateSensorRecord(
                        sensor=sensor,
                        temperature=temperature
                    ).save()
            elif sensor.type == 'esp8266_heat_pump':
                try:
                    session = requests.Session()
                    retry = Retry(connect=3, backoff_factor=0.5)
                    adapter = HTTPAdapter(max_retries=retry)
                    session.mount('http://', adapter)
                    session.mount('https://', adapter)
                    r = session.get(f"http://{sensor.ip_address}/", timeout=5)
                    data = r.json()
                    r.close()
                    if 'flow' in data and 'return' in data:
                        flow = round(data['flow'], 2)
                        retn = round(data['return'], 2)
                        if not self.daikin_error:
                            heat_pump_status.flow_temperature = flow
                            heat_pump_status.return_temperature = retn
                            heat_pump_status.reported_flow_temperature = \
                                self.daikin_temps['flow']
                    if 'air' in data:
                        temperature = (
                            round(data['air'], 1)
                            + sensor.temperature_offset
                        )
                        cupboard_climate_record = ClimateSensorRecord(
                            sensor=sensor,
                            temperature=temperature
                        )
                        if 'humidity' in data:
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
                    retry = Retry(connect=3, backoff_factor=0.5)
                    adapter = HTTPAdapter(max_retries=retry)
                    session.mount('http://', adapter)
                    session.mount('https://', adapter)
                    r = session.get(f"http://{sensor.ip_address}/", timeout=5)
                    data = r.json()
                    r.close()
                    temperature = (
                        round(data['air'], 1)
                        + sensor.temperature_offset
                    )
                    ClimateSensorRecord(
                        sensor=sensor,
                        temperature=temperature,
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
        if not self.daikin_error:
            heat_pump_status.save()

        return

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

