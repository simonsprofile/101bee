import requests
import json
from .models import LightsSettings


class Bridge:
    def __init__(self, s):
        requests.packages.urllib3.disable_warnings()
        self.update_creds(s['bridge_ip'], s['bridge_user'])

    def update_creds(self, bridge_ip, bridge_user):
        self.bridge_ip = bridge_ip
        self.headers = {
            'hue-application-key': bridge_user,
            'Cache-Control': 'no-cache',
            'Pragma': 'no-cache'
        }

    def authorise(self):
        r = requests.post(
            'http://{}/api'.format(self.bridge_ip),
            data=json.dumps({
                'devicetype': 'sitechindustries#hue_helper',
                'generateclientkey': True
            })
        )
        if 'error' in r.json()[0]:
            return {
                'success': False,
                'message': r.json()[0]['error']['description']
            }
        elif 'success' in r.json()[0]:
            self.update_creds(self.bridge_ip, r.json()[0]['success']['username'])
            s = LightsSettings.objects.all().first()
            s.bridge_ip = self.bridge_ip
            s.bridge_user = r.json()[0]['success']['username']
            s.bridge_key = r.json()[0]['success']['clientkey']
            s.save()
            return {'success': True}

    def is_authorised(self):
        url = 'https://{}/clip/v2/resource/bridge'.format(self.bridge_ip)
        try:
            r = requests.get(url, headers=self.headers, verify=False, timeout=5)
        except requests.ConnectTimeout:
            return False

        try:
            if len(r.json()['errors']) <= 0:
                return True
        except Exception as e:
            print(e)
            return False

    def search(self, endpoint):
        url = 'https://{}/clip/v2/resource/{}'.format(
            self.bridge_ip,
            endpoint
        )
        r = requests.get(url, headers=self.headers, verify=False)
        if len(r.json()['errors']) > 0:
            return {
                'success': False,
                'errors': '\n'.join([
                    x['description'] for x in r.json()['errors']
                ])
            }
        else:
            return {
                'success': True,
                'records': r.json()['data']
            }

    def get(self, endpoint, id):
        url = 'https://{}/clip/v2/resource/{}/{}'.format(
            self.bridge_ip,
            endpoint,
            id
        )
        r = requests.get(url, headers=self.headers, verify=False)
        if len(r.json()['errors']) > 0:
            return {
                'success': False,
                'errors': '\n'.join([
                    x['description'] for x in r.json()['errors']
                ])
            }
        else:
            return {
                'success': True,
                'record': r.json()['data'][0]
            }

    def post(self, endpoint, id, payload):
        if not id:
            id = ''
        url = 'https://{}/clip/v2/resource/{}/{}'.format(
            self.bridge_ip,
            endpoint,
            id
        )
        r = requests.post(
            url,
            headers=self.headers,
            verify=False,
            data=json.dumps(payload)
        )
        if len(r.json()['errors']) > 0:
            return {
                'success': False,
                'errors': '\n'.join([
                    x['description'] for x in r.json()['errors']
                ])
            }
        else:
            return {'success': True}
