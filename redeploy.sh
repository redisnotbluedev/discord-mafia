#!/bin/bash
cd /home/arduino/discord-mafia
git fetch --all
git reset --hard origin/main
sudo systemctl restart mafia-bot
