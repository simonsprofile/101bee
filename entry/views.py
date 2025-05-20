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

        for door in doors:
            # These are just going to have to be unique for now
            if door.name == 'Garage':
                try:
                    print(f'calling http://{door.ip}:{door.port}/hellooo')
                    r = requests.get(f'http://{door.ip}:{door.port}/hellooo', timeout=10)
                    print('called')
                    if r.status_code == 200:
                        door.status = 'connected'
                    else:
                        door.status = 'not_connected'
                except requests.ConnectionError as e:
                    print('connection error')
                    print(e)
                    door.status = 'not_connected'
                except requests.Timeout as e:
                    print('timeout')
                    door.status = 'not_connected'
                door.save()
        context = {
            'keys': keys,
            'inaccessible_doors': [
                d for d in doors if d not in [k.Door for k in keys]
            ]
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
                if door.name == 'Garage':
                    try:
                        r = requests.post(
                            f'http://{door.ip}:{door.port}/open-sesame'
                        )
                        if r.status_code == 200:
                            messages.success(request, "Door unlocked")
                        else:
                            messages.danger(request, "Request failed")
                    except requests.ConnectionError as e:
                        messages.danger(request, "Request failed")
                    except requests.Timeout as e:
                        messages.danger(request, "Request failed")
                else:
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
