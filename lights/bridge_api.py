import requests
import json
from .models import LightsSettings


class Bridge:
    def __init__(self, s):
        requests.packages.urllib3.disable_warnings()
        self.update_creds(s['bridge_ip'], s['bridge_user'])

    def update_creds(self, bridge_ip, bridge_user):
        self.bridge_ip = bridge_ip
        self.bridge_user = bridge_user
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
            self.update_creds(
                self.bridge_ip,
                r.json()[0]['success']['username']
            )
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

    '''
        The Hue Bridge v2 API is still in development, and some endpoints will
        still need us to use the old v1 API.
    '''
    def v1_endpoints(self):
        return ['rules', 'schedules', 'sensors', 'resourcelinks']

    def search(self, endpoint):
        return self.search_v1(endpoint) \
            if endpoint in self.v1_endpoints() \
            else self.search_v2(endpoint)

    def get(self, endpoint, id):
        return self.get_v1(endpoint, id) \
            if endpoint in self.v1_endpoints() \
            else self.get_v2(endpoint, id)

    def put(self, endpoint, id, payload):
        return self.put_v1(endpoint, id, payload) \
            if endpoint in self.v1_endpoints() \
            else self.put_v2(endpoint, id, payload)

    def post(self, endpoint, payload):
        return self.post_v1(endpoint, payload) \
            if endpoint in self.v1_endpoints() \
            else self.post_v2(endpoint, payload)

    def delete(self, endpoint, id):
        return self.delete_v1(endpoint, id) \
            if endpoint in self.v1_endpoints() \
            else self.delete_v2(endpoint, id)

    def search_v2(self, endpoint):
        url = f"https://{self.bridge_ip}/clip/v2/resource/{endpoint}"
        try:
            r = requests.get(url, headers=self.headers, verify=False, timeout=5)
        except requests.ConnectTimeout:
            return {'success': False, 'errors': 'No response from the Bridge.'}

        if len(r.json()['errors']) > 0:
            return {
                'success': False,
                'errors': '\n'.join([
                    x['description'] for x in r.json()['errors']
                ])
            }
        else:
            return {'success': True, 'records': r.json()['data']}

    def get_v2(self, endpoint, id):
        url = f"https://{self.bridge_ip}/clip/v2/resource/{endpoint}/{id}"
        try:
            r = requests.get(url, headers=self.headers, verify=False, timeout=5)
        except requests.ConnectTimeout:
            return {'success': False, 'errors': 'No response from the Bridge.'}
        if len(r.json()['errors']) > 0:
            return {
                'success': False,
                'errors': '\n'.join([
                    x['description'] for x in r.json()['errors']
                ])
            }
        else:
            return {'success': True, 'record': r.json()['data'][0]}

    def post_v2(self, endpoint, payload):
        url = f"https://{self.bridge_ip}/clip/v2/resource/{endpoint}"
        try:
            r = requests.post(
                url,
                headers=self.headers,
                verify=False,
                data=json.dumps(payload)
            )
        except requests.ConnectTimeout:
            return {'success': False, 'errors': 'No response from the Bridge.'}
        if len(r.json()['errors']) > 0:
            return {
                'success': False,
                'errors': '\n'.join([
                    x['description'] for x in r.json()['errors']
                ])
            }
        else:
            return {'success': True, 'record': r.json()['data'][0]}

    def delete_v2(self, endpoint, id):
        url = f"https://{self.bridge_ip}/clip/v2/resource/{endpoint}/{id}"
        try:
            r = requests.delete(
                url, headers=self.headers, verify=False, timeout=5
            )
        except requests.ConnectTimeout:
            return {'success': False, 'errors': 'No response from the Bridge.'}
        if len(r.json()['errors']) > 0:
            return {
                'success': False,
                'errors': '\n'.join([
                    x['description'] for x in r.json()['errors']
                ])
            }
        else:
            return {'success': True}

    def search_v1(self, endpoint):
        url = f"https://{self.bridge_ip}/api/{self.bridge_user}/{endpoint}"
        try:
            r = requests.get(url, headers=self.headers, verify=False, timeout=5)
        except requests.ConnectTimeout:
            return {'success': False, 'errors': 'No response from the Bridge.'}
        try:
            data = r.json()
        except requests.JSONDecodeError:
            return {'success': False, 'errors': 'Response was not JSON.'}
        if isinstance(data, list):
            return {
                'success': False,
                'errors': '\n'.join([x['error']['description'] for x in data])
            }
        else:
            return {'success': True, 'records': data}

    def get_v1(self, endpoint, id):
        url = f"https://{self.bridge_ip}/api/{self.bridge_user}/{endpoint}/{id}"
        try:
            r = requests.get(url, headers=self.headers, verify=False, timeout=5)
        except requests.ConnectTimeout:
            return {'success': False, 'errors': 'No response from the Bridge.'}
        try:
            data = r.json()
        except requests.JSONDecodeError:
            return {'success': False, 'errors': 'Response was not JSON.'}
        if isinstance(data, list):
            return {
                'success': False,
                'errors': '\n'.join([x['error']['description'] for x in data])
            }
        else:
            return {
                'success': True,
                'record': data | {'id_v1': f"/{endpoint}/{id}"}
            }

    def put_v1(self, endpoint, id, payload):
        url = f"https://{self.bridge_ip}/api/{self.bridge_user}/{endpoint}/{id}"
        try:
            r = requests.put(
                url,
                headers=self.headers,
                verify=False,
                timeout=5,
                data=json.dumps(payload)
            )
        except requests.ConnectTimeout:
            return {'success': False, 'errors': 'No response from the Bridge.'}
        try:
            data = r.json()
        except requests.JSONDecodeError:
            return {'success': False, 'errors': 'Response was not JSON.'}

        results = sum([list(x.keys()) for x in data], [])
        if 'success' in results:
            r = self.get(endpoint, data[0]['success']['id'])
            if not r['success']:
                return {
                    'success': False,
                    'errors': ('Updating the record appeared successful, '
                               'but I was unable to retrieve the result '
                               f"because of the error: {r['errors']}")
                }
            return {'success': True, 'record': r['record']}
        errors = sum([
            list(x.values()) for x in data
            if 'error' in list(x.keys())
        ], [])
        return {
            'success': False,
            'errors': '\n'.join([x['description'] for x in errors])
        }

    def post_v1(self, endpoint, payload):
        url = f"https://{self.bridge_ip}/api/{self.bridge_user}/{endpoint}"
        try:
            r = requests.post(
                url,
                headers=self.headers,
                verify=False,
                timeout=5,
                data=json.dumps(payload)
            )
        except requests.ConnectTimeout:
            return {'success': False, 'errors': 'No response from the Bridge.'}
        try:
            data = r.json()
        except requests.JSONDecodeError:
            return {'success': False, 'errors': 'Response was not JSON.'}
        results = sum([list(x.keys()) for x in data], [])
        if 'success' in results:
            r = self.get(endpoint, data[0]['success']['id'])
            if not r['success']:
                return {
                    'success': False,
                    'errors': ('Creating the record appeared successful, '
                               'but I was unable to retrieve the result '
                               f"because of the error: {r['errors']}")
                }
            r['record']['id_v1'] = f"/{endpoint}/{data[0]['success']['id']}"
            return {'success': True, 'record': r['record']}
        errors = sum([
            list(x.values()) for x in data
            if 'error' in list(x.keys())
        ], [])
        return {
            'success': False,
            'errors': '\n'.join([x['description'] for x in errors])
        }

    def delete_v1(self, endpoint, id):
        url = f"https://{self.bridge_ip}/api/{self.bridge_user}/{endpoint}/{id}"
        try:
            r = requests.delete(
                url, headers=self.headers, verify=False, timeout=5
            )
        except requests.ConnectTimeout:
            return {'success': False, 'errors': 'No response from the Bridge.'}
        try:
            data = r.json()
        except requests.JSONDecodeError:
            return {'success': False, 'errors': 'Response was not JSON.'}
        results = sum([list(x.keys()) for x in data], [])
        if 'success' in results:
            return {'success': True}
        errors = sum([
            list(x.values()) for x in data
            if 'error' in list(x.keys())
        ], [])
        return {
            'success': False,
            'errors': '\n'.join([x['description'] for x in errors])
        }
