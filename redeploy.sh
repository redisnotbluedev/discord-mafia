#!/bin/bash

cd $HOME/discord-mafia
git fetch --all
git reset --hard origin/main

STATUS_FILE="games_ongoing.txt"

# Check if there are any ongoing games and wait if necessary
if [ -f "$STATUS_FILE" ]; then
    while [ "$(cat "$STATUS_FILE")" == "1" ]; do
        echo "Games are currently ongoing. Waiting for them to finish before redeploying..."
        sleep 10
    done
fi

echo "No games ongoing. Proceeding with restart."
sudo systemctl restart mafia-bot
