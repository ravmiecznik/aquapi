#!/bin/bash

this_path=$(dirname $0)

exec >> $this_path/keep_alive.log
exec 2>&1

ps -aux | grep aquaserver.py | grep -v grep

status=$?

function run() {
	echo $*
	$*
}

function log () {
	echo $(date) $*
	logger "$*"
}

if [ $status != 0 ]
then
  (
    cd $this_path
	  log Server not running, starting...
	  killall -9 aquaserver.py
    nohup ./aquaserver.py &
    pid=$!
    nohup cpulimit --pid $pid --limit 50 &
	)
fi
