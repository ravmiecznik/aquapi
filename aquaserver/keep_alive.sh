#!/bin/bash


this_path=$(dirname $0)
ps -aux | grep aquaserver.py | grep -v grep

status=$?

function run() {
	echo $*
	$*
}

function log () {
	echo $*
	logger "$*"
}

if [ $status != 0 ]
then
	log Server not running, starting...
	run nohup $this_path/run_server.sh
fi
