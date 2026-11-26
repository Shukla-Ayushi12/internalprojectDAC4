"""Password sign-in and session lifecycle for the Streamlit dashboards."""

from dataclasses import dataclass, field
from time import time

from services.database import SupabaseAPI, SupabaseError, require_publishable_key


@dataclass(frozen=True)
class Session:
    user_id: str
    role: str
    expires_at: int
    access_token: str = field(repr=False)
    refresh_token: str = field(repr=False)


def _session(data: dict) -> Session:
    user = data["user"]
    role = (user.get("app_metadata") or {}).get("app_role")
    if role not in {"student", "module_teacher"}:
        raise PermissionError("This login has no student or module teacher role.")
    expires_at = data.get("expires_at")
    if expires_at is None:
        expires_at = int(time()) + data["expires_in"]
    return Session(user["id"], role, int(expires_at), data["access_token"], data["refresh_token"])


class AuthService:
    def __init__(self, url: str, publishable_key: str):
        require_publishable_key(publishable_key)
        self.url = url
        self._key = publishable_key

    def sign_in(self, email: str, password: str) -> Session:
        with SupabaseAPI(self.url, self._key) as api:
            data = api.request("POST", "/auth/v1/token", operation="sign in",
                               params={"grant_type": "password"},
                               json={"email": email.strip(), "password": password})
        return _session(data)

    def refresh_if_needed(self, session: Session) -> Session:
        """Return a replacement session when necessary. Save the return value in session state."""
        if session.expires_at - time() > 60:
            return session
        with SupabaseAPI(self.url, self._key) as api:
            data = api.request("POST", "/auth/v1/token", operation="refresh session",
                               params={"grant_type": "refresh_token"},
                               json={"refresh_token": session.refresh_token})
        return _session(data)

    def sign_out(self, session: Session) -> None:
        with SupabaseAPI(self.url, self._key, session.access_token) as api:
            try:
                api.request("POST", "/auth/v1/logout", operation="sign out", params={"scope": "local"})
            except SupabaseError as error:
                if error.status != 401:
                    raise
