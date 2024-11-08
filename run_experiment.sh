#!/usr/bin/env bash

# To make this file click-able, run: gsettings set org.gnome.nautilus.preferences executable-text-activation 'ask'

set -e #errors will cause script to exit immediately

#change directory to location of this bash script
cd "`dirname -- "$0"`"

#make sure the logs dir exists
mkdir -p logs
cd app_code 
export logfile=../logs/console_`date +"%FT%T"`.log

#redirect output to log file (from: https://serverfault.com/a/103569/72634)
if [ -z "$SCRIPT" ]
then 
    /usr/bin/script -f -c "./install_and_run.sh $*" "$logfile"
    read -p "" x && exit 0
fi

