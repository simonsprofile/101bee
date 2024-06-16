import requests
from .models import DaikinAccessToken
import environ
from datetime import datetime, timedelta
from requests.auth import HTTPBasicAuth
from pprint import pprint


ENV = environ.Env()


class DaikinApi:
    def __init__(self):
        self.client_id = ENV('DAIKIN__CLIENT_ID', None)
        self.client_secret = ENV('DAIKIN__SECRET', None)
        self.redirect_uri = ENV('DAIKIN__REDIRECT_URI', None)
        self.basic_auth = HTTPBasicAuth(self.client_id, self.client_secret)
        self.headers = {
            'Accept': 'application/json',
            'Content-Type': 'application/json'
        }

    def build_url(self, subdomain, endpoint, params={}):
        oidc = 'oidc/' if subdomain == 'idp' else ''
        url = f"https://{subdomain}.onecta.daikineurope.com/v1/{oidc}{endpoint}"
        connector = '?'
        for k, v in params.items():
            url = f"{url}{connector}{k}={v}"
            connector = '&'
        return url

    def get_token(self):
        token = DaikinAccessToken.objects.first()
        return token if token else False

    def is_authenticated(self):
        token = self.get_token()
        if not token:
            return False
        if token.expires_at < datetime.now():
            r = self.refresh_token(token.refresh_token)
            if not r['success']:
                return False
            else:
                token = r['token']
        url = self.build_url('idp', 'introspect', {'token': token.access_token})
        r = requests.post(url, auth=self.basic_auth, headers=self.headers)
        response = r.json()
        return response['active']

    def auth_url(self):
        params = {
            'response_type': 'code',
            'client_id': self.client_id,
            'redirect_uri': self.redirect_uri,
            'scope': 'openid%20onecta:basic.integration'
        }
        return self.build_url('idp', 'authorize', params)

    def authorize(self, code):
        params = {
            'grant_type': 'authorization_code',
            'client_id': self.client_id,
            'client_secret': self.client_secret,
            'code': code,
            'redirect_uri': self.redirect_uri
        }
        url = self.build_url('idp', 'token', params)
        r = requests.post(url, auth=self.basic_auth, headers=self.headers)
        self.save_token(r.json())
        success = self.is_authenticated()
        return {'success': success}

    def refresh_token(self, refresh_token):
        params = {
            'grant_type': 'refresh_token',
            'client_id': self.client_id,
            'client_secret': self.client_secret,
            'refresh_token': refresh_token
        }
        url = self.build_url('idp', 'token', params)
        r = requests.post(url, headers=self.headers)
        token = self.save_token(r.json())
        success = self.is_authenticated()
        return {
            'success': success,
            'token': token
        }

    def save_token(self, token_json):
        token = DaikinAccessToken.objects.first()
        if not token:
            token = DaikinAccessToken()
        token.access_token = token_json['access_token']
        token.refresh_token = token_json['refresh_token']
        token.expires_at = (
            datetime.now()
            + timedelta(seconds=(token_json['expires_in'] - 30))
        )
        token.save()
        return token

    def revoke_access(self):
        token = self.get_token()
        params = {
            'token': token.refresh_token,
            'client_id': self.client_id,
            'client_secret': self.client_secret,
            'token_type_hint': 'refresh_token'
        }
        url = self.build_url('idp', 'revoke', params)
        requests.post(url, headers=self.headers)

        params['token'] = token.access_token
        params['token_type_hint'] = 'access_token'
        requests.post(url, headers=self.headers)

        token.delete()
        return

    def current_temps(self):
        if not self.is_authenticated():
            return {'success': False, 'message': 'Daikin not authenticated.'}
        token = self.get_token()

        temps = {
            'hot_water': None,
            'tank_setpoint': None,
            'room': None,
            'room_setpoint': None,
            'outdoor': None,
            'flow': None
        }

        self.headers['Authorization'] = f"Bearer {token.access_token}"
        url = self.build_url('api', 'gateway-devices')
        r = requests.get(url, headers=self.headers)
        self.headers.pop('Authorization', None)
        if 'message' in r.json():
            return {'success': False, 'message': r.json()['message']}
        for g in r.json():
            for m in g['managementPoints']:
                if m['managementPointType'] == 'nerp':
                    pprint(m)
                if m['managementPointType'] == 'domesticHotWaterTank':
                    temps['hot_water'] = m['sensoryData']['value']['tankTemperature']['value']
                    temps['tank_setpoint'] = m['temperatureControl']['value']['operationModes']['heating']['setpoints']['domesticHotWaterTemperature']['value']
                elif m['managementPointType'] == 'climateControl':
                    temps['room'] = m['sensoryData']['value']['roomTemperature']['value']
                    temps['outdoor'] = m['sensoryData']['value']['outdoorTemperature']['value']
                    temps['flow'] = m['sensoryData']['value']['leavingWaterTemperature']['value']
                    temps['room_setpoint'] = m['temperatureControl']['value']['operationModes']['auto']['setpoints']['roomTemperature']['value']
        return {'success': True, 'temps': temps}

    def record_snapshot(self):
        pass
