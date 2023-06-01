from django.contrib import admin
from .models import *


class LightsUserAccessAdmin(admin.ModelAdmin):
    list_display = ('user_name', )

    @admin.display(description='User')
    def user_name(self, object):
        if object.User.first_name or object.User.last_name:
            return f"{object.User.first_name} {object.User.last_name}"
        else:
            return object.User.username


admin.site.register(LightsSettings)
admin.site.register(LightsUserAccess, LightsUserAccessAdmin)
