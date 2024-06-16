from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import HttpResponseRedirect
from django.shortcuts import redirect
from django.urls import reverse
from django.urls import reverse_lazy
from django.views.generic import TemplateView, View

from .daikin_api import DaikinApi
from .models import HeatingUserAccess
from .nest_api import GoogleApi


class Heating(TemplateView):
    template_name = 'heating.html'

    def dispatch(self, request, *args, **kwargs):
        # Access Control
        user = request.user
        if not user.is_authenticated:
            return redirect(reverse_lazy('dashboard'))
        if not HeatingUserAccess.objects.filter(User=user).exists():
            return redirect(reverse_lazy('dashboard'))
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        daikin = DaikinApi()
        context['daikin_authenticated'] = daikin.is_authenticated()
        context['daikin_auth_url'] = daikin.auth_url()
        r = daikin.current_temps()
        if r['success']:
            context['temps'] = r['temps']
        else:
            context['temps'] = False
        return context


class DaikinDisconnect(LoginRequiredMixin, View):
    def get(self, request, *args, **kwargs):
        daikin = DaikinApi()
        daikin.revoke_access()
        messages.success(request, 'Daikin access was revoked.')
        return HttpResponseRedirect(reverse_lazy('heating'))


class GoogleCallback(View):
    def get(self, request, *args, **kwargs):
        code = request.GET['code']
        if not code:
            messages.error(
                request,
                'There was no access token returned from Google.'
            )
            return HttpResponseRedirect(reverse('heating'))

        google = GoogleApi()
        r = google.authorize(code)
        if not r['success']:
            print(r['message'])
        return HttpResponseRedirect(reverse('heating'))


class DaikinCallback(View):
    def get(self, request, *args, **kwargs):
        code = request.GET['code']
        if not code:
            messages.error(
                request,
                'There was no access token returned from Daikin.'
            )
            return HttpResponseRedirect(reverse('heating'))

        daikin = DaikinApi()
        r = daikin.authorize(code)
        if not r['success']:
            print(r['message'])
        return HttpResponseRedirect(reverse('heating'))
