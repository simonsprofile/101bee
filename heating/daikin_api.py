import json

import requests
from .models import DaikinAccessToken
import environ
from datetime import datetime, timedelta
from requests.auth import HTTPBasicAuth


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
        return token if token else None

    def is_authenticated(self):
        token = self.get_token()
        if not token:
            return {'authorized': False, 'error': 'No saved auth token.'}
        if token.expires_at < datetime.now():
            refresh = self.refresh_token(token.refresh_token)
            if not refresh['success']:
                return {
                    'authorized': False,
                    'error': (f"While refreshing the token the following "
                              f"error occurred:\n{refresh['error']}")
                }
            else:
                token = refresh['token']
        url = self.build_url('idp', 'introspect', {'token': token.access_token})
        r = requests.post(url, auth=self.basic_auth, headers=self.headers)
        cleaned_r = self.clean_response(r, ['active'])
        if cleaned_r['success']:
            r_json = cleaned_r['json']
            if r_json['active']:
                return {'authorized': True}
            else:
                return {
                    'authorized': False,
                    'error': 'Token exists but was not valid.'
                }
        else:
            return {
                'authorized': False,
                'error': (f"While checking if the token was valid, there was "
                          f"an issue with the response:\n{cleaned_r['error']}")
            }

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
        cleaned_r = self.clean_response(
            r,
            ['access_token', 'expires_in', 'refresh_token']
        )
        if cleaned_r['success']:
            self.save_token(cleaned_r['json'])
            auth_check = self.is_authenticated()
            if auth_check['authorized']:
                return {'success': True}
            else:
                return {
                    'success': False,
                    'error': (f"While authorising with Daikin, the following "
                              f"error occurred:\n{auth_check['error']}")
                }
        else:
            return {
                'success': False,
                'error': (f"While authorising with Daikin, there was a problem "
                          f"with the response:\n{cleaned_r['error']}")
            }

    def refresh_token(self, refresh_token):
        params = {
            'grant_type': 'refresh_token',
            'client_id': self.client_id,
            'client_secret': self.client_secret,
            'refresh_token': refresh_token
        }
        url = self.build_url('idp', 'token', params)
        r = requests.post(url, headers=self.headers)
        cleaned_r = self.clean_response(
            r,
            ['access_token', 'expires_in', 'refresh_token']
        )
        if cleaned_r['success']:
            r_json = cleaned_r['json']
        else:
            return cleaned_r
        token = self.save_token(r_json)
        success = self.is_authenticated()
        return {'success': success, 'token': token}

    def save_token(self, token_json):
        token = DaikinAccessToken.objects.first()
        if not token:
            token = DaikinAccessToken()
        token.access_token = token_json['access_token']
        token.expires_at = (
                datetime.now()
                + timedelta(seconds=(token_json['expires_in'] - 30))
        )
        token.refresh_token = token_json['refresh_token']
        print('Saving token:')
        print(token.__dict__)
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

    def clean_response(self, r, required_keys=[]):
        try:
            r_json = r.json()
        except AttributeError as e:
            return {'success': False, 'error': 'Response is not JSON.'}
        for key in required_keys:
            try:
                value = r_json[key]
            except KeyError as e:
                return {
                    'success': False,
                    'error': f"{e} not found in response."
                }
        return {'success': True, 'json': r_json}

    def current_temps(self):
        auth_check = self.is_authenticated()
        if not auth_check['authorized']:
            return {
                'success': False,
                'error': (f"Daikin was not authenticated because of the "
                          f"following error:\n{auth_check['error']}")
            }
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
            return {
                'success': False,
                'error': (f"While retrieving the status of the Daikin heating"
                          f"system the following error occurred\n"
                          f"{r.json()['message']}")
            }
        for g in r.json():
            for m in g['managementPoints']:
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
