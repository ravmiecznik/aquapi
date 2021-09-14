#!/bin/bash

this_path=$(dirname $0)

killall aquaserver.py

$this_path/aquaserver.py &
pid=$!
nohup cpulimit --pid $pid --limit 50 &
