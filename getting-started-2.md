The bot seems to actually need this list of permissions:

On the server:

- View Channels
- Manage Channels
- Manage Roles
- Manage Webhooks

On the relevant channel, as overrides

- View Channel
- Manage Channel
- Manage Permissions
- Send Messages
- Send Messages in Threads
- Create Public Threads
- Create Private Threads
- Manage Threads

The effect of Setup will be:

- The bot edits its channel overrides (in various ways that _should_ be 
  no-ops, but probably aren't) and creates the Mafia Player role.
- The bot waits for a message to be sent -- upon a message being sent, it will
  block off the channel and create a view advertising the game.

The effect of starting a game will be:

- The bot explicitly ungrants access from general players to the game channel.
- The bot attempts to fix its channel level overrides to match the above
- The bot creates a webhook and uses it to send messages
- The bot creates Mafia Private Chat.
- All players inside the game will become Mafia Players.

Theoretically, the Mafia Player role should be cleared off of affected players
when the game ends, but I'm not sure this works.

General note: The bot really likes to overwrite its own channel overrides -- this happens in the two above places I mentioned.