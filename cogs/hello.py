"""Hello cog — handles the ``/hello`` slash command."""

from services.greeting import build_greeting


def register(app):
    @app.command("/hello")
    def handle_hello(ack, command, respond):
        # ack() must be called within 3 seconds to acknowledge the command.
        ack()
        respond(build_greeting(command["user_id"], command.get("text", "")))
