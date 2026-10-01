import sys
import types

import pytest

from lmw.credentials import CredentialStore
from lmw.errors import CredentialStoreError


def install_fake_keyring(monkeypatch):
    store = {}
    keyring = types.ModuleType("keyring")
    errors = types.ModuleType("keyring.errors")

    class KeyringError(Exception):
        pass

    class PasswordDeleteError(KeyringError):
        pass

    def get_password(service_name, username):
        return store.get((service_name, username))

    def set_password(service_name, username, password):
        store[(service_name, username)] = password

    def delete_password(service_name, username):
        try:
            del store[(service_name, username)]
        except KeyError as exc:
            # Real backends use messages like "No such password!", so only the type is reliable.
            raise PasswordDeleteError("No such password!") from exc

    keyring.get_keyring = lambda: types.SimpleNamespace(priority=1)
    keyring.get_password = get_password
    keyring.set_password = set_password
    keyring.delete_password = delete_password
    errors.KeyringError = KeyringError
    errors.PasswordDeleteError = PasswordDeleteError
    keyring.errors = errors

    monkeypatch.setitem(sys.modules, "keyring", keyring)
    monkeypatch.setitem(sys.modules, "keyring.errors", errors)
    return store


def test_credential_store_saves_password_and_default_email(monkeypatch):
    install_fake_keyring(monkeypatch)
    credential_store = CredentialStore()

    credential_store.ensure_available()
    credential_store.set_password("me@example.com", "secret")

    assert credential_store.get_password("me@example.com") == "secret"
    assert credential_store.get_default_email() == "me@example.com"


def test_credential_store_deletes_password_and_default_email(monkeypatch):
    install_fake_keyring(monkeypatch)
    credential_store = CredentialStore()
    credential_store.set_password("me@example.com", "secret")

    credential_store.delete_password("me@example.com")

    assert credential_store.get_password("me@example.com") is None
    assert credential_store.get_default_email() is None


def test_forgetting_a_password_that_was_never_saved_is_not_an_error(monkeypatch):
    install_fake_keyring(monkeypatch)
    credential_store = CredentialStore()

    credential_store.delete_password("nobody@example.com")
    credential_store.delete_password("nobody@example.com")


def test_other_keyring_errors_on_delete_are_reported(monkeypatch):
    install_fake_keyring(monkeypatch)
    keyring = sys.modules["keyring"]

    def broken_delete(service_name, username):
        raise sys.modules["keyring.errors"].KeyringError("locked")

    monkeypatch.setattr(keyring, "delete_password", broken_delete)

    with pytest.raises(CredentialStoreError, match="locked"):
        CredentialStore().delete_password("me@example.com")
