from django.views.generic import View, TemplateView
from django.template.response import TemplateResponse
from lights.models import LightsSettings
from django.http import HttpResponseRedirect
from django.urls import reverse_lazy


class Dashboard(TemplateView):
    template_name = 'dashboard.html'


class Settings(View):
    def get(self, request, *args, **kwargs):
        context = {'light_settings': _get_settings()}
        return TemplateResponse(request, 'settings.html', context)

    def post(self, request, *args, **kwargs):
        print('post!')
        return HttpResponseRedirect(reverse_lazy('settings'))

# Utils
def _get_settings():
    if not LightsSettings.objects.all().exists():
        LightsSettings().save()
    return LightsSettings.objects.all().first()