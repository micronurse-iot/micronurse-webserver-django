#!/usr/bin/env bash

python3 ./manage.py runserver 0.0.0.0:13000 --noreload > micronurse-webserver.log 2> micronurse-webserver.log &