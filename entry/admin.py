from django.contrib import admin
from django.shortcuts import redirect
from .models import *


class DoorAdmin(admin.ModelAdmin):
    list_display = ('name', 'type', 'address', 'status', )

    @admin.display(description='Door Address')
    def address(self, door):
        return f"http://{door.ip}:{door.port}"


class KeyAdmin(admin.ModelAdmin):
    list_display = ('door_name', 'user_name', 'recycle', )

    @admin.display(description='Door Name')
    def door_name(self, door):
        return door.Door.name

    @admin.display(description='User')
    def user_name(self, key):
        if key.User.first_name or key.User.last_name:
            return f"{key.User.first_name} {key.User.last_name}"
        else:
            return key.User.username


class EntryUserAccessAdmin(admin.ModelAdmin):
    list_display = ('user_name', )

    @admin.display(description='User')
    def user_name(self, object):
        if object.User.first_name or object.User.last_name:
            return f"{object.User.first_name} {object.User.last_name}"
        else:
            return object.User.username


admin.site.register(Door, DoorAdmin)
admin.site.register(Key, KeyAdmin)
admin.site.register(EntryUserAccess, EntryUserAccessAdmin)
