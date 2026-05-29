import os

from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler

from cogs import load_cogs

# Initializes your app with your bot token.
app = App(token=os.environ.get("SLACK_BOT_TOKEN"))

# Auto-discover and register every cog (feature module) in the cogs/ package.
load_cogs(app)

# Start your app over Socket Mode.
if __name__ == "__main__":
    SocketModeHandler(app, os.environ["SLACK_APP_TOKEN"]).start()
