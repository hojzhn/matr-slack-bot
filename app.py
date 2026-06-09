import os

from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler

from cogs import load_cogs


app = App(token=os.environ.get("SLACK_BOT_TOKEN"))


load_cogs(app)


if __name__ == "__main__":
    SocketModeHandler(app, os.environ["SLACK_APP_TOKEN"]).start()
