"""Temporary code switches; retain grant data and dormant implementations for reopening."""

LEARNING_AUTHORIZATION_ENABLED = False
IN_APP_DICTIONARY_ENABLED = False


def permission_mode():
    """Version permission snapshots whenever a paused capability is restored."""
    return (
        f"auth{int(LEARNING_AUTHORIZATION_ENABLED)}:"
        f"lookup{int(IN_APP_DICTIONARY_ENABLED)}:resource-login1"
    )
