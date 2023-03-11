import datetime

from django.db import models


def mirek_from_kelvin(k):
    return 1000000 / k


light_defaults = {
    'morning': {
        'time': datetime.time(hour=6),
        'brightness': 50,
        'colour': mirek_from_kelvin(5400)
    },
    'day': {
        'time': datetime.time(hour=8, minute=30),
        'brightness': 100,
        'colour': mirek_from_kelvin(5600)
    },
    'evening': {
        'time': datetime.time(hour=18, minute=30),
        'brightness': 80,
        'colour': mirek_from_kelvin(2900)
    },
    'night': {
        'time': datetime.time(hour=0, minute=30),
        'brightness': 5,
        'colour': mirek_from_kelvin(2000)
    },
}


class LightsSettings(models.Model):
    bridge_ip = models.CharField(
        'Hue Bridge IP',
        max_length=128,
        blank=True,
        null=True
    )
    bridge_user = models.CharField(
        'Hue Bridge User',
        max_length=128,
        blank=True,
        null=True
    )
    bridge_key = models.CharField(
        'Hue Bridge Key',
        max_length=128,
        blank=True,
        null=True
    )

    morning_time = models.TimeField(
        'Morning Start Time',
        default=light_defaults['morning']['time']
    )
    day_time = models.TimeField(
        'Day Start Time',
        default=light_defaults['day']['time']
    )
    evening_time = models.TimeField(
        'Evening Start Time',
        default=light_defaults['evening']['time']
    )
    night_time = models.TimeField(
        'Night Start Time',
        default=light_defaults['night']['time']
    )

    morning_mirek = models.IntegerField(
        'Morning Colour (Mirek)',
        default=light_defaults['morning']['colour']
    )
    day_mirek = models.IntegerField(
        'Day Colour (Mirek)',
        default=light_defaults['day']['colour']
    )
    evening_mirek = models.IntegerField(
        'Evening Colour (Mirek)',
        default=light_defaults['evening']['colour']
    )
    night_mirek = models.IntegerField(
        'Night Colour (Mirek)',
        default=light_defaults['night']['colour']
    )

    morning_brightness = models.IntegerField(
        'Morning Brightness (%)',
        default=light_defaults['morning']['brightness']
    )
    day_brightness = models.IntegerField(
        'Day Brightness (%)',
        default=light_defaults['day']['brightness']
    )
    evening_brightness = models.IntegerField(
        'Evening Brightness (%)',
        default=light_defaults['evening']['brightness']
    )
    night_brightness = models.IntegerField(
        'Night Brightness (%)',
        default=light_defaults['night']['brightness']
    )

    class Meta:
        verbose_name = 'Light Settings'
        verbose_name_plural = 'Light Settings'
