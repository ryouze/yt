import sqlite3
from datetime import datetime
from pathlib import Path

import pytest
from pydantic import HttpUrl

from yt.database import Database
from yt.structures import Subscription, SubscriptionInput


@pytest.fixture
def database(tmp_path: Path) -> Database:
    """Create a temporary database for each test."""
    return Database(database_path=tmp_path / "test.db")


def test_read_all_empty(database: Database) -> None:
    """Ensure that a new database contains no subscriptions."""
    assert database.read_all() == []


def test_insert_new_subscription(database: Database) -> None:
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


def test_update_subscription(database: Database) -> None:
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


def test_insert_duplicate_subscription(database: Database) -> None:
    """Ensure that duplicate subscriptions cannot be inserted."""
    subscription_input = SubscriptionInput(channel_url=HttpUrl("https://www.youtube.com/@noriyaro"))
    database.insert_new(subscription_input=subscription_input)

    with pytest.raises(sqlite3.IntegrityError, match=r"UNIQUE constraint failed: subscriptions\.channel_url"):
        database.insert_new(subscription_input=subscription_input)

    subscriptions: list[Subscription] = database.read_all()

    assert len(subscriptions) == 1
    assert subscriptions[0].channel_url == subscription_input.channel_url


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


def test_update_duplicate_subscription(database: Database) -> None:
    """Ensure that a subscription cannot be updated to duplicate another subscription."""
    first_subscription_input = SubscriptionInput(channel_url=HttpUrl("https://www.youtube.com/@noriyaro"))
    second_subscription_input = SubscriptionInput(channel_url=HttpUrl("https://www.youtube.com/@newchannel"))

    database.insert_new(subscription_input=first_subscription_input)
    database.insert_new(subscription_input=second_subscription_input)

    subscriptions: list[Subscription] = database.read_all()

    second_subscription = next(s for s in subscriptions if s.id == 2)
    duplicate_subscription = second_subscription.with_changes(
        changes={Database.Field.CHANNEL_URL: first_subscription_input.channel_url},
    )

    with pytest.raises(sqlite3.IntegrityError, match=r"UNIQUE constraint failed: subscriptions\.channel_url"):
        database.update(subscription=duplicate_subscription)

    # Check if after the failed duplicate update, the database still contains exactly the two original channel URLs
    subscriptions = database.read_all()

    assert len(subscriptions) == 2
    assert {s.channel_url for s in subscriptions} == {
        first_subscription_input.channel_url,
        second_subscription_input.channel_url,
    }


def test_delete_subscription(database: Database) -> None:
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
