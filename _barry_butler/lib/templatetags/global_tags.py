from django import template


register = template.Library()


@register.simple_tag
def nav_list():
    return [
        {'title': 'Dashboard', 'icon': 'dashboard', 'url': 'dashboard'},
        {'title': 'Entry', 'icon': 'door_open', 'url': 'entry'},
        {'title': 'Lights', 'icon': 'lightbulb', 'url': 'lights'},
    ]
