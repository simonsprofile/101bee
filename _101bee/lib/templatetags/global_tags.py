from django import template
from lights.models import LightsUserAccess
from entry.models import EntryUserAccess
from heating.models import HeatingUserAccess


register = template.Library()


@register.simple_tag(takes_context=True)
def nav_list(context):
    nav_items = [
        {'title': 'Dashboard', 'icon': 'dashboard', 'url': 'dashboard'}
    ]
    user = context['request'].user
    if user.is_authenticated:
        if LightsUserAccess.objects.filter(User=user).exists():
            nav_items.append(
                {'title': 'Lights', 'icon': 'lightbulb', 'url': 'lights'}
            )
        if EntryUserAccess.objects.filter(User=user).exists():
            nav_items.append(
                {'title': 'Entry', 'icon': 'door_open', 'url': 'entry'}
            )
        if HeatingUserAccess.objects.filter(User=user).exists():
            nav_items.append(
                {'title': 'Heating', 'icon': 'mode_heat', 'url': 'heating'}
            )
    return nav_items
