from django.contrib import admin
from .models import *

admin.site.register(HeatingUserAccess)
admin.site.register(GoogleAccessToken)
admin.site.register(DaikinAccessToken)


@admin.register(ClimateSensor)
class HeatSensorAdmin(admin.ModelAdmin):
    list_display = ('name', 'type', )
    list_filter = ('type', )


@admin.register(ClimateSensorRecord)
class TemperatureRecordAdmin(admin.ModelAdmin):
    list_display = ('created_at', 'sensor', 'temperature', )
    list_filter = ('sensor', )


@admin.register(HeatPumpStatusRecord)
class HeatStatusRecordAdmin(admin.ModelAdmin):
    list_display = ('created_at', 'flow_temperature', 'return_temperature', )
