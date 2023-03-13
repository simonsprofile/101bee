from django.views.generic import TemplateView


class Entry(TemplateView):
    template_name = 'entry.html'
