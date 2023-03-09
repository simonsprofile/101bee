from django.views.generic import TemplateView


class Lights(TemplateView):
    template_name = 'lights.html'
