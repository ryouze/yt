from datetime import datetime

import pytest
from pydantic import HttpUrl, ValidationError

from yt.database import Database
from yt.structures import Subscription, SubscriptionInput


@pytest.mark.parametrize(
    argnames=("input_url", "expected_url"),
    argvalues=[
        ("https://youtube.com/@noriyaro", "https://www.youtube.com/@noriyaro"),
        ("https://www.youtube.com/c/noriyaro", "https://www.youtube.com/c/noriyaro"),
        ("https://m.youtube.com/@noriyaro/videos", "https://www.youtube.com/@noriyaro"),
        ("https://www.youtube.com/user/noriyaro", "https://www.youtube.com/user/noriyaro"),
        ("https://www.youtube.com/channel/UC123/videos", "https://www.youtube.com/channel/UC123"),
    ],
)
def test_subscription_input_normalizes_supported_channel_urls(input_url: str, expected_url: str) -> None:
    """Ensure that supported YouTube channel URLs are normalized to their canonical form."""
    subscription = SubscriptionInput(channel_url=HttpUrl(input_url))

    assert subscription.channel_url == HttpUrl(expected_url)


@pytest.mark.parametrize(
    argnames="channel_url",
    argvalues=[
        "https://example.com/@noriyaro",
        "https://www.youtube.com/watch?v=abc123",
        "https://www.youtube.com/playlist?list=abc123",
    ],
)
def test_subscription_input_rejects_non_channel_urls(channel_url: str) -> None:
    """Ensure that URLs which do not identify a supported YouTube channel are rejected."""
    with pytest.raises(ValidationError):
        SubscriptionInput(channel_url=HttpUrl(channel_url))


def test_subscription_input_channel_videos_url_appends_videos_path() -> None:
    """Ensure that `channel_videos_url` points to the normalized channel's `/videos` page."""
    subscription = SubscriptionInput(channel_url=HttpUrl("https://www.youtube.com/@noriyaro"))

    assert subscription.channel_videos_url == HttpUrl("https://www.youtube.com/@noriyaro/videos")


def test_subscription_with_changes_returns_updated_copy() -> None:
    """Ensure that `with_changes` returns a modified copy without changing the original subscription."""
    subscription = Subscription(
        id=1,
        created_at=datetime(2026, 9, 3, 12, 0),  # noqa: DTZ001
        updated_at=datetime(2026, 9, 3, 12, 0),  # noqa: DTZ001
        channel_url=HttpUrl("https://www.youtube.com/@noriyaro"),
    )

    new_updated_at = datetime(2026, 9, 4, 12, 0)  # noqa: DTZ001
    updated_subscription: Subscription = subscription.with_changes({Database.Field.UPDATED_AT: new_updated_at})

    assert updated_subscription.updated_at == new_updated_at
    assert subscription.updated_at != new_updated_at
