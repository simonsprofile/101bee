from django.db import models

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
