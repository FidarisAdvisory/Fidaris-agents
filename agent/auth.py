import os

import google.auth.transport.requests
import google.oauth2.credentials


def get_google_credentials() -> google.oauth2.credentials.Credentials:
    """
    Build a refreshed Google credentials object from environment variables.
    Requires: GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET, GOOGLE_REFRESH_TOKEN
    """
    credentials = google.oauth2.credentials.Credentials(
        token=None,
        refresh_token=os.environ["GOOGLE_REFRESH_TOKEN"],
        client_id=os.environ["GOOGLE_CLIENT_ID"],
        client_secret=os.environ["GOOGLE_CLIENT_SECRET"],
        token_uri=os.environ.get(
            "GOOGLE_TOKEN_URI", "https://oauth2.googleapis.com/token"
        ),
        scopes=[
            "https://www.googleapis.com/auth/calendar.readonly",
            "https://www.googleapis.com/auth/gmail.send",
            "https://www.googleapis.com/auth/gmail.readonly",
            "https://www.googleapis.com/auth/drive.readonly",
        ],
    )
    credentials.refresh(google.auth.transport.requests.Request())
    return credentials
