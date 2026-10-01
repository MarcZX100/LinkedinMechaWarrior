import json
from types import SimpleNamespace

import pytest

from linkedin_automation.errors import (
    AuthenticationRequiredError,
    ChallengeError,
    RateLimitedError,
    VoyagerError,
    VoyagerHTTPError,
)
from linkedin_automation.voyager import VoyagerClient, build_url


class FakePacer:
    def __init__(self) -> None:
        self.requests = 0
        self.cooldowns: list[str] = []

    def before_request(self) -> None:
        pass

    def record_request(self) -> None:
        self.requests += 1

    def start_cooldown(self, seconds: float, reason: str) -> None:
        self.cooldowns.append(reason)


class FakePage:
    def __init__(self, response: dict) -> None:
        self.response = response
        self.calls: list[dict] = []

    def evaluate(self, script, arg):
        self.calls.append(arg)
        return {"url": arg["url"], "contentType": "application/json", **self.response}


class FakeSession:
    def __init__(self, cookies: dict) -> None:
        self.cookies = cookies
        self.config = SimpleNamespace(default_timeout_ms=30000)

    def linkedin_cookies(self) -> dict:
        return self.cookies

    def has_session_cookie(self) -> bool:
        return bool(self.cookies.get("li_at"))


def make_client(response: dict, cookies: dict | None = None):
    session = FakeSession(cookies if cookies is not None else {"li_at": "x", "JSESSIONID": '"ajax:123"'})
    pacer = FakePacer()
    client = VoyagerClient(session, pacer)
    page = FakePage(response)
    client._page = page
    return client, page, pacer


def test_build_url_adds_prefix_and_keeps_restli_syntax():
    assert build_url("/me") == "https://www.linkedin.com/voyager/api/me"
    assert build_url("voyager/api/me") == "https://www.linkedin.com/voyager/api/me"
    url = build_url("/graphql", {"variables": "(start:0,count:10)", "queryId": "x.y", "q": "a b"})
    assert url == "https://www.linkedin.com/voyager/api/graphql?variables=(start:0,count:10)&queryId=x.y&q=a%20b"


def test_build_url_rejects_other_hosts():
    with pytest.raises(ValueError):
        build_url("https://evil.example.com/voyager/api/me")
    with pytest.raises(ValueError):
        build_url("https://www.linkedin.com/feed/")


def test_get_sends_csrf_token_from_jsessionid_and_parses_json():
    client, page, pacer = make_client({"status": 200, "text": json.dumps({"data": {"plainId": 1}})})

    assert client.get("/me") == {"data": {"plainId": 1}}
    headers = page.calls[0]["headers"]
    assert headers["csrf-token"] == "ajax:123"
    assert headers["x-restli-protocol-version"] == "2.0.0"
    assert page.calls[0]["body"] is None
    assert pacer.requests == 1


def test_post_sends_json_body():
    client, page, _ = make_client({"status": 201, "text": ""})
    assert client.post("/something", {"a": 1}) == {}
    assert json.loads(page.calls[0]["body"]) == {"a": 1}
    assert page.calls[0]["headers"]["content-type"].startswith("application/json")


def test_missing_session_cookie_requires_login():
    client = VoyagerClient(FakeSession({}), FakePacer())
    with pytest.raises(AuthenticationRequiredError):
        client.connect()


def test_missing_csrf_cookie_requires_login_without_sending():
    client, page, pacer = make_client({"status": 200, "text": "{}"}, cookies={"li_at": "x"})
    with pytest.raises(AuthenticationRequiredError):
        client.get("/me")
    assert page.calls == [] and pacer.requests == 0


@pytest.mark.parametrize("status", [429, 999])
def test_rate_limit_starts_a_cooldown(status):
    client, _, pacer = make_client({"status": status, "text": ""})
    with pytest.raises(RateLimitedError):
        client.get("/me")
    assert pacer.cooldowns


def test_redirect_to_checkpoint_is_a_challenge():
    client, _, pacer = make_client(
        {"status": 200, "text": "<html>", "url": "https://www.linkedin.com/checkpoint/challenge/abc"}
    )
    with pytest.raises(ChallengeError):
        client.get("/me")
    assert pacer.cooldowns


def test_challenge_body_on_403_is_a_challenge():
    client, _, pacer = make_client({"status": 403, "text": '{"status":403,"code":"CHALLENGE"}'})
    with pytest.raises(ChallengeError):
        client.get("/me")
    assert pacer.cooldowns


def test_expired_session_is_reported_without_cooldown():
    for response in (
        {"status": 401, "text": ""},
        {"status": 403, "text": "CSRF check failed"},
        {"status": 200, "text": "<html>", "url": "https://www.linkedin.com/login?session_redirect=x"},
    ):
        client, _, pacer = make_client(response)
        with pytest.raises(AuthenticationRequiredError):
            client.get("/me")
        assert pacer.cooldowns == []


def test_other_http_errors_and_bad_json():
    client, _, _ = make_client({"status": 404, "text": "not here"})
    with pytest.raises(VoyagerHTTPError) as info:
        client.get("/nope")
    assert info.value.status == 404

    client, _, _ = make_client({"status": 200, "text": "<html>oops</html>"})
    with pytest.raises(VoyagerError):
        client.get("/me")

    client, _, _ = make_client({"status": 0, "text": "", "error": "TypeError: Failed to fetch"})
    with pytest.raises(VoyagerError, match="Failed to fetch"):
        client.get("/me")
