#!/bin/bash


this_path=$(dirname $(realpath $0))
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
	(
	cd $this_path
	log Server not running, starting...
	run nohup ./run_server.sh
	)
fi
