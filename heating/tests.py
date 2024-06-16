from unittest import TestCase
from .models import ClimateSensor, HeatRecord


class HeatingModelTests(TestCase):
    def test_heat_sensor(self):
        sensor = ClimateSensor.objects.create(
            name='Test Sensor',
            protocol='nest_thermostat',
            address='test_address'
        )
        self.assertTrue(isinstance(sensor, ClimateSensor))

        record = HeatRecord.objects.create(
            sensor=sensor,
            temperature=21.5,
            relative_humidity=50.0,
            ambient_light=100.0
        )
        self.assertTrue(isinstance(record, HeatRecord))


class HeatingFunctionalTests(TestCase):
    def test_fake(self):
        self.assertTrue(True)
