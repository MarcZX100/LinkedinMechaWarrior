import sys
import types

from linkedin_automation.credentials import CredentialStore


def install_fake_keyring(monkeypatch):
    store = {}
    keyring = types.ModuleType("keyring")
    errors = types.ModuleType("keyring.errors")

    class KeyringError(Exception):
        pass

    def get_password(service_name, username):
        return store.get((service_name, username))

    def set_password(service_name, username, password):
        store[(service_name, username)] = password

    def delete_password(service_name, username):
        try:
            del store[(service_name, username)]
        except KeyError as exc:
            raise KeyringError("not found") from exc

    keyring.get_keyring = lambda: types.SimpleNamespace(priority=1)
    keyring.get_password = get_password
    keyring.set_password = set_password
    keyring.delete_password = delete_password
    errors.KeyringError = KeyringError

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
