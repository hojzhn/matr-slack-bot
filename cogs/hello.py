from services.greeting import build_greeting


def register(app):
    @app.command("/hello")
    def handle_hello(ack, command, respond):

        ack()
        respond(build_greeting(command["user_id"], command.get("text", "")))
