from django.views.generic import View, TemplateView
from django.http import HttpResponseRedirect
from django.urls import reverse_lazy
from .models import LightsSettings
from .bridge_api import Bridge
from django.contrib import messages


class Lights(TemplateView):
    template_name = 'lights.html'

    def get_context_data(self, **kwargs):
        return super().get_context_data(**kwargs) | self._check_bridge()

    def _get_settings(self):
        if not LightsSettings.objects.all().exists():
            LightsSettings().save()
        return LightsSettings.objects.all().first()

    def _check_bridge(self):
        s = self._get_settings().__dict__
        if not s['bridge_ip'] or not s['bridge_user'] or not s['bridge_key']:
            return {'authorised': False} | s

        bridge = Bridge(s)
        if not bridge.is_authorised():
            return {'authorised': False} | s

        return {'authorised': True} | s


class LightsAuth(View):
    def get(self, request, *args, **kwargs):
        return HttpResponseRedirect(reverse_lazy('lights'))

    def post(self, request, *args, **kwargs):
        ip = request.POST['ip']
        s = self._get_settings().__dict__
        s['hub_ip'] = ip
        bridge = Bridge(self._get_settings().__dict__)
        r = bridge.authorise()
        if r['success']:
            messages.success(request, 'Bridge authorised!')
        else:
            messages.warning(
                request,
                (
                    'There was a was an error reported when trying to authorise:\n'
                    f'{r["message"]}'
                )
            )

        return HttpResponseRedirect(reverse_lazy('lights'))

    def _get_settings(self):
        if not LightsSettings.objects.all().exists():
            LightsSettings().save()
        return LightsSettings.objects.all().first()


class LightsDisconnect(View):
    def get(self, request, *args, **kwargs):
        s = self._get_settings()
        s.bridge_user = None
        s.bridge_key = None
        s.save()
        messages.success(request, 'Bridge credentials deleted.')
        return HttpResponseRedirect(reverse_lazy('lights'))

    def _get_settings(self):
        if not LightsSettings.objects.all().exists():
            LightsSettings().save()
        return LightsSettings.objects.all().first()

