from datetime import datetime
from typing import TYPE_CHECKING

import pytest
from pydantic import HttpUrl

from yt.database import Database
from yt.structures import Subscription, SubscriptionInput

if TYPE_CHECKING:
    from pathlib import Path


@pytest.fixture
def database(tmp_path: Path) -> Database:
    """Create a temporary database for each test."""
    return Database(database_path=tmp_path / "test.db")


def test_read_all_empty(database: Database) -> None:
    """Ensure that a new database contains no subscriptions."""
    assert database.read_all() == []


def test_insert_new(database: Database) -> None:
    """Ensure that subscriptions can be inserted and read."""
    subscription_input = SubscriptionInput(channel_url=HttpUrl("https://www.youtube.com/@noriyaro"))
    database.insert_new(subscription_input=subscription_input)

    subscriptions: list[Subscription] = database.read_all()

    assert len(subscriptions) == 1
    assert subscriptions[0].id == 1
    assert subscriptions[0].channel_url == subscription_input.channel_url

    # We test the SQLite `TIMESTAMP` to `datetime` converter as well
    assert isinstance(subscriptions[0].created_at, datetime)
    assert isinstance(subscriptions[0].updated_at, datetime)


def test_update(database: Database) -> None:
    """Ensure that subscriptions can be updated."""
    subscription_input = SubscriptionInput(channel_url=HttpUrl("https://www.youtube.com/@noriyaro"))
    database.insert_new(subscription_input=subscription_input)

    subscriptions: list[Subscription] = database.read_all()
    subscription = subscriptions[0].with_changes(
        changes={Database.Field.CHANNEL_URL: HttpUrl("https://www.youtube.com/@newchannel")},
    )
    database.update(subscription=subscription)

    updated_subscriptions: list[Subscription] = database.read_all()

    assert len(updated_subscriptions) == 1

    updated_subscription = updated_subscriptions[0]

    assert updated_subscription.id == subscription.id
    assert updated_subscription.channel_url == HttpUrl("https://www.youtube.com/@newchannel")


def test_update_missing_subscription(database: Database) -> None:
    """Ensure that updating a missing subscription raises an error."""
    subscription = Subscription(
        id=1,
        created_at=datetime(2026, 9, 3, 12, 0),  # noqa: DTZ001
        updated_at=datetime(2026, 9, 3, 12, 0),  # noqa: DTZ001
        channel_url=HttpUrl("https://www.youtube.com/@noriyaro"),
    )

    with pytest.raises(RuntimeError, match="Expected to update subscription 1, but updated 0 rows"):
        database.update(subscription=subscription)


def test_delete(database: Database) -> None:
    """Ensure that subscriptions can be deleted."""
    subscription_input = SubscriptionInput(channel_url=HttpUrl("https://www.youtube.com/@noriyaro"))
    database.insert_new(subscription_input=subscription_input)

    subscriptions: list[Subscription] = database.read_all()
    database.delete(subscription=subscriptions[0])

    assert database.read_all() == []


def test_delete_missing_subscription(database: Database) -> None:
    """Ensure that deleting a missing subscription raises an error."""
    subscription = Subscription(
        id=1,
        created_at=datetime(2026, 9, 3, 12, 0),  # noqa: DTZ001
        updated_at=datetime(2026, 9, 3, 12, 0),  # noqa: DTZ001
        channel_url=HttpUrl("https://www.youtube.com/@noriyaro"),
    )

    with pytest.raises(RuntimeError, match="Expected to delete subscription 1, but deleted 0 rows"):
        database.delete(subscription=subscription)
