from __future__ import annotations

from dataclasses import dataclass


SERVICE_NAME = "linkedin-mecha-warrior"
DEFAULT_EMAIL_KEY = "__default_linkedin_email__"


class CredentialStoreError(RuntimeError):
    """Raised when the system credential store cannot be used."""


@dataclass(frozen=True)
class CredentialStore:
    service_name: str = SERVICE_NAME

    def ensure_available(self) -> None:
        try:
            import keyring
            from keyring.errors import KeyringError
        except ImportError as exc:
            raise CredentialStoreError(
                "keyring is not installed. Run `pip install -r requirements.txt`."
            ) from exc

        try:
            backend = keyring.get_keyring()
        except KeyringError as exc:
            raise CredentialStoreError(
                "Could not access a secure system keyring. Configure an OS keychain backend, "
                "or run without `--save-password`."
            ) from exc

        if getattr(backend, "priority", 0) <= 0:
            raise CredentialStoreError(
                "No secure system keyring backend is available. Configure an OS keychain backend, "
                "or run without `--save-password`."
            )

    def get_default_email(self) -> str | None:
        return self._call("get_password", self.service_name, DEFAULT_EMAIL_KEY)

    def set_default_email(self, email: str) -> None:
        self._call("set_password", self.service_name, DEFAULT_EMAIL_KEY, email)

    def clear_default_email(self, email: str | None = None) -> None:
        default_email = self.get_default_email()
        if default_email and (email is None or default_email == email):
            self._delete(DEFAULT_EMAIL_KEY)

    def get_password(self, email: str) -> str | None:
        return self._call("get_password", self.service_name, email)

    def set_password(self, email: str, password: str) -> None:
        self._call("set_password", self.service_name, email, password)
        self.set_default_email(email)

    def delete_password(self, email: str) -> None:
        self._delete(email)
        self.clear_default_email(email)

    def _delete(self, username: str) -> None:
        try:
            self._call("delete_password", self.service_name, username)
        except CredentialStoreError as exc:
            message = str(exc).lower()
            if "not found" not in message and "not exist" not in message:
                raise

    def _call(self, method_name: str, *args):
        try:
            import keyring
            from keyring.errors import KeyringError
        except ImportError as exc:
            raise CredentialStoreError(
                "keyring is not installed. Run `pip install -r requirements.txt`."
            ) from exc

        try:
            method = getattr(keyring, method_name)
            return method(*args)
        except KeyringError as exc:
            raise CredentialStoreError(
                "Could not access a secure system keyring. Configure an OS keychain backend, "
                "or run `linkedin-cli auth --manual` without saved credentials. "
                f"Original error: {exc}"
            ) from exc
