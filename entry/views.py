from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import render, redirect
from django.urls import reverse_lazy
from django.views.generic import View
from .models import Door, Key, EntryUserAccess

import requests


class Entry(LoginRequiredMixin, View):
    def get(self, request, *args, **kwargs):
        template_name = 'entry.html'
        user = request.user

        # Access control
        if not EntryUserAccess.objects.filter(User=user).exists():
            return redirect(reverse_lazy('dashboard'))

        keys = Key.objects.filter(User=user.id)
        doors = Door.objects.all()
        context = {
            'keys': keys,
            'inaccessible_doors': [d for d in doors if d not in [k.Door for k in keys]]
        }
        return render(request, template_name, context)

    def post(self, request, *args, **kwargs):
        keyless_actions = ['lock', 'close', ]
        form = request.POST
        try:
            action = form['action']
            door_id = form['door']
            door = Door.objects.get(id=door_id)
            key_exists = Key.objects.filter(
                Door=door,
                User=request.user
            ).exists()

            # Provide unsecured access for closing and locking
            if action in keyless_actions and not key_exists:
                Key(Door=door, User=request.user, recycle=True)
                key_exists = True

            if key_exists:
                key = Key.objects.get(Door=door, User=request.user)
                try:
                    r = requests.post(
                        f"http://{door.ip}:{door.port}",
                        headers={'door-action': action},
                        timeout=5
                    )
                    if 199 < r.status_code < 300:
                        door.status = r.content.decode()
                        door.save()
                        messages.success(
                            request,
                            f"Door communication successful."
                        )
                    if key.recycle:
                        key.delete()
                    else:
                        messages.error(
                            request,
                            f"Door error: {r.content.decode()}"
                        )
                except requests.ConnectionError:
                    door.status = 'unknown'
                    door.save()
                    messages.warning(request, "Door not available, status unkown.")
            else:
                messages.warning(request, "You don't have a key to this door.")

        except KeyError:
            pass
        return redirect(reverse_lazy('entry'))
