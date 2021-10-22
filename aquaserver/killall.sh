#!/bin/bash

kill $(ps -aux | grep aquaserver.py | grep -v grep | awk '{print $2}')
kill $(ps -aux | grep ph_controller.py | grep -v grep | awk '{print $2}')