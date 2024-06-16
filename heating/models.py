from django.db import models
from django.contrib.auth.models import User

sensor_types = (
    ('nest_thermostat', 'Nest Thermostat'),
    ('hue_presence_sensor', 'Hue Sensor'),
    ('daikin_thermostat', 'Daikin Room Stat'),
    ('daikin_tank', 'Daikin Cylinder Stat'),
    ('daikin_weather', 'Daikin Weather Sensor'),
    ('esp8266_heat_pump', 'Sitech Industries Heat Pump Monitor'),
    ('esp8266_room', 'Sitech Industries Room Sensor'),
)


class ClimateSensor(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    name = models.CharField('Sensor Name', max_length=50)
    measures_temperature = models.BooleanField('Temperature', default=True, null=False)
    measures_humidity = models.BooleanField('Humidity', default=True, null=False)
    measures_light = models.BooleanField('Ambient Light', default=True, null=False)
    type = models.CharField(
        'Type', max_length=20, default='nest_thermostat', choices=sensor_types, null=False, blank=True
    )
    hue_temp_id = models.IntegerField(
        'Philips Hue Sensor ID for Temperature', null=True, blank=True
    )
    hue_light_id = models.IntegerField(
        'Philips Hue Sensor ID for Ambient Light', null=True, blank=True
    )
    ip_address = models.GenericIPAddressField('IP Address', protocol='IPv4', null=True, blank=True)

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = 'Climate Sensor'


class ClimateSensorRecord(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    sensor = models.ForeignKey(ClimateSensor, verbose_name='Sensor', null=False, on_delete=models.CASCADE)
    temperature = models.FloatField('Temperature (°C)', null=True, blank=True)
    relative_humidity = models.FloatField('Humidity (%)', null=True, blank=True)
    ambient_light = models.FloatField('Ambient Light (lx)', null=True, blank=True)

    def __str__(self):
        return f"{self.created_at}: {self.sensor}"

    class Meta:
        verbose_name = 'Climate Sensor Record'


class HeatPumpStatusRecord(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    room_setpoint = models.FloatField('Heating Setpoint (°C)', null=True, blank=True)
    tank_setpoint = models.FloatField('Hot Water Setpoint (°C)', null=True, blank=True)
    flow_temperature = models.FloatField('Flow Temperature (°C)', null=True, blank=True)
    return_temperature = models.FloatField('Return Temperature (°C)', null=True, blank=True)
    reported_flow_temperature = models.FloatField('Reported Flow Temperature (°C)', null=True, blank=True)

    def __str__(self):
        return f"{self.created_at}"

    class Meta:
        verbose_name = 'Heat Pump Status Record'


class HeatingUserAccess(models.Model):
    user = models.ForeignKey(
        User,
        name='User',
        blank=False,
        null=False,
        on_delete=models.CASCADE
    )

    class Meta:
        verbose_name = 'User Access Grant'


class GoogleAccessToken(models.Model):
    access_token = models.CharField('Access Token', max_length=100, blank=True)
    expires_at = models.DateTimeField('Expires At', null=False)

    class Meta:
        verbose_name = 'Google Access Token'


class DaikinAccessToken(models.Model):
    access_token = models.CharField('Access Token', max_length=1500, blank=True)
    refresh_token = models.CharField('Refresh Token', max_length=500, blank=True)
    expires_at = models.DateTimeField('Expires At', null=False)

    class Meta:
        verbose_name = 'Daikin Access Token'
