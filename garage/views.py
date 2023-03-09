from django.views.generic import TemplateView


class Garage(TemplateView):
    template_name = 'garage.html'
