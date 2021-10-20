#!/bin/bash

this_path=$(dirname $(realpath $0))

killall aquaserver.py

$this_path/aquaserver.py 2>&1 >> $this_path/aqualog.log &
pid=$!
nohup cpulimit --pid $pid --limit 50 &
