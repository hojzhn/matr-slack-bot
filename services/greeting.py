
def build_greeting(user_id, text=""):
    """Build the reply text for the /hello command."""
    text = (text or "").strip()
    if text:
        return f"Hi <@{user_id}>! You said: {text}"
    return f"Hi <@{user_id}>! 👋 Try `/hello something`."
