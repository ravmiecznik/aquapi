#!/bin/bash

this_path=$(dirname $0)

debug=$1

if [ "$debug" == "debug" ]
then
  echo debug mode
  exec >> $this_path/keep_alive.log
  exec 2>&1
else
   echo no debug mode
   exec 1>>$this_path/keep_alive.log
   exec 2> /dev/null
fi

ps -aux | grep aquaserver.py | grep -v grep
ap_status=$?

ps -aux | grep ph_controller.py | grep -v grep
pc_status=$?

function run() {
	echo $*
	$*
}

function log () {
	echo $(date) $*
	logger "$*"
}

if [ $pc_status != 0 ]
then
  (
    cd $this_path
	  log Ph controller not running, starting...
    nohup ./ph_controller.py &
	)
fi

if [ $ap_status != 0 ]
then
  (
    cd $this_path
	  log Server not running, starting...
	  kill $(ps -aux | grep aquaserver.py | grep -v grep | awk '{print $2}')
    nohup ./aquaserver.py &
    pid=$!
    nohup cpulimit --pid $pid --limit 50 &
	)
fi
