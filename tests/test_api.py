import pytest

from lmw.api import get_feed, parse_feed, parse_me
from lmw.errors import VoyagerError

ME_PAYLOAD = {
    "data": {"plainId": 123, "*miniProfile": "urn:li:fs_miniProfile:ACoAAB"},
    "included": [
        {
            "$type": "com.linkedin.voyager.identity.shared.MiniProfile",
            "entityUrn": "urn:li:fs_miniProfile:ACoAAB",
            "dashEntityUrn": "urn:li:fsd_profile:ACoAAB",
            "firstName": "Ada",
            "lastName": "Lovelace",
            "occupation": "Analyst at Analytical Engines",
            "publicIdentifier": "ada-lovelace",
        }
    ],
}


def feed_update(activity_id: int, author: str, text: str | None, **extra) -> dict:
    update = {
        "$type": "com.linkedin.voyager.feed.render.UpdateV2",
        "entityUrn": f"urn:li:fs_updateV2:(urn:li:activity:{activity_id},MAIN_FEED,EMPTY,DEFAULT,false)",
        "updateMetadata": {"urn": f"urn:li:activity:{activity_id}"},
        "actor": {
            "name": {"text": author, "attributes": []},
            "description": {"text": "Engineer"},
            "subDescription": {"text": "3h • Edited • "},
        },
        "*socialDetail": f"urn:li:fs_socialDetail:urn:li:activity:{activity_id}",
    }
    if text is not None:
        update["commentary"] = {"text": {"text": text}}
    update.update(extra)
    return update


def feed_payload(updates: list[dict], extra_included: list[dict] | None = None) -> dict:
    included = list(updates) + (extra_included or [])
    for update in updates:
        activity = update["updateMetadata"]["urn"]
        included.append(
            {
                "entityUrn": f"urn:li:fs_socialDetail:{activity}",
                "*totalSocialActivityCounts": f"urn:li:fs_socialActivityCounts:{activity}",
            }
        )
        included.append(
            {"entityUrn": f"urn:li:fs_socialActivityCounts:{activity}", "numLikes": 12, "numComments": 3, "numShares": 1}
        )
    return {"data": {"*elements": [update["entityUrn"] for update in updates]}, "included": included}


def test_parse_me():
    profile = parse_me(ME_PAYLOAD)
    assert profile.name == "Ada Lovelace"
    assert profile.headline == "Analyst at Analytical Engines"
    assert profile.url == "https://www.linkedin.com/in/ada-lovelace/"
    assert profile.urn == "urn:li:fsd_profile:ACoAAB"


def test_parse_me_falls_back_to_included_profile():
    payload = {"data": {}, "included": ME_PAYLOAD["included"]}
    assert parse_me(payload).first_name == "Ada"


def test_parse_me_rejects_unknown_shape():
    with pytest.raises(VoyagerError):
        parse_me({"data": {}, "included": []})


def test_parse_feed_extracts_posts_and_counts():
    posts, count = parse_feed(feed_payload([feed_update(1, "Grace Hopper", "Hello\nworld")]))

    assert count == 1
    post = posts[0]
    assert post.author == "Grace Hopper"
    assert post.author_headline == "Engineer"
    assert post.age == "3h"
    assert post.text == "Hello\nworld"
    assert (post.reactions, post.comments, post.reposts) == (12, 3, 1)
    assert post.url == "https://www.linkedin.com/feed/update/urn:li:activity:1/"
    assert post.promoted is False


def test_parse_feed_handles_reshares_and_promoted_posts():
    original = feed_update(2, "Alan Turing", "Original thoughts")
    original["entityUrn"] = "urn:li:fs_updateV2:original"
    repost = feed_update(3, "Grace Hopper", None, **{"*resharedUpdate": "urn:li:fs_updateV2:original"})
    promoted = feed_update(4, "Some Brand", "Buy things")
    promoted["actor"]["subDescription"] = {"text": "Promoted"}

    payload = feed_payload([repost, promoted])
    payload["included"].append(original)
    posts, count = parse_feed(payload)

    assert count == 2
    assert posts[0].reshared_author == "Alan Turing"
    assert posts[0].text == "Original thoughts"
    assert posts[1].promoted is True


def test_parse_feed_skips_entries_it_cannot_understand():
    payload = {"data": {"*elements": ["urn:li:missing", "urn:li:empty"]}, "included": [{"entityUrn": "urn:li:empty"}]}
    posts, count = parse_feed(payload)
    assert posts == [] and count == 2


def test_parse_feed_tolerates_garbage():
    assert parse_feed(None) == ([], 0)
    assert parse_feed({"data": "x", "included": "y"}) == ([], 0)


class FakeFeedClient:
    def __init__(self, pages):
        self.pages = list(pages)
        self.calls = []

    def get(self, path, params=None):
        self.calls.append((path, dict(params)))
        return self.pages.pop(0) if self.pages else {"data": {"*elements": []}, "included": []}


def test_get_feed_paginates_until_limit():
    first = feed_payload([feed_update(i, f"Author {i}", f"Post {i}") for i in range(10)])
    second = feed_payload([feed_update(i, f"Author {i}", f"Post {i}") for i in range(10, 20)])
    client = FakeFeedClient([first, second])

    posts = get_feed(client, 15)

    assert len(posts) == 15
    assert [call[1]["start"] for call in client.calls] == [0, 10]


def test_get_feed_stops_on_empty_page_and_caps_pages():
    client = FakeFeedClient([feed_payload([feed_update(1, "A", "x")])])
    assert len(get_feed(client, 20)) == 1

    unparseable = {"data": {"*elements": ["urn:li:missing"] * 10}, "included": []}
    client = FakeFeedClient([unparseable] * 100)
    assert get_feed(client, 10) == []
    assert len(client.calls) == 2


def test_get_feed_validates_limit():
    with pytest.raises(ValueError):
        get_feed(FakeFeedClient([]), 0)
    with pytest.raises(ValueError):
        get_feed(FakeFeedClient([]), 51)
