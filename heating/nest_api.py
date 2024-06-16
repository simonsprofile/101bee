import requests
from .models import GoogleAccessToken
import environ
from datetime import datetime, timedelta

ENV = environ.Env()

class GoogleApi:
    def __init__(self):
        requests.packages.urllib3.disable_warnings()
        self.project_id = ENV('GOOGLE__PROJECT_ID', None)
        self.client_id = ENV('GOOGLE__CLIENT_ID', None)
        self.client_secret = ENV('GOOGLE__SECRET', None)
        self.base_url = (
            'https://smartdevicemanagement.googleapis.com/v1/enterprises/'
            f'{self.project_id}'
        )
        self.headers = {

        }

    # Authentication
    def is_authenticated(self):
        token = GoogleAccessToken.objects.first()
        if not token:
            return False
        r = self.search('devices')

        return True

    def auth_url(self):
        return (
            f"https://nestservices.google.com/partnerconnections/auth?"
            f"redirect_uri={ENV('GOOGLE__REDIRECT_URI', None)}&"
            f"client_id={self.client_id}&"
            'access_type=offline&'
            'response_type=code&'
            'scope=https://www.googleapis.com/auth/sdm.service'
        )

    def authorize(self, code):
        url = (
            "https://www.googleapis.com/oauth2/v4/token?"
            f"client_id={self.client_id}&"
            f"client_secret={self.client_secret}&"
            f"code={code}&"
            "grant_type=authorization_code&"
            f"redirect_uri={ENV('GOOGLE__REDIRECT_URI', None)}"
        )
        r = requests.post(url)
        response = r.json()
        print(response)
        self.save_token(
            response['access_token'],
            datetime.now() + timedelta(seconds=(response['expires_in'] - 30))
        )
        success = self.is_authenticated()
        return {'success': success}

    def save_token(self, access_token, expires_at):
        print('saving...')
        token = GoogleAccessToken.objects.first()
        if not token:
            token = GoogleAccessToken()
        token.access_token = access_token
        token.expires_at = expires_at
        token.save()
        return

    def search(self, endpoint, filters={}):
        url = f"{self.base_url}/{endpoint}"
        r = requests.get(url)
        return r.json()


    def get(self, endpoint, id):
        pass
