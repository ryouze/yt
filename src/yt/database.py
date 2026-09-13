import sqlite3
from contextlib import closing, contextmanager
from datetime import datetime
from enum import StrEnum, auto
from pathlib import Path
from typing import TYPE_CHECKING

from loguru import logger

from yt.structures import Subscription, SubscriptionInput

if TYPE_CHECKING:
    from collections.abc import Generator

# Convert all SQLite `CURRENT_TIMESTAMP` text values to `datetime` for strict Pydantic validation
# Register globally because SQLite's converter registry is process-wide, so putting it within the class would make
# no semantic difference
sqlite3.register_converter(
    "TIMESTAMP",
    lambda value_bytes: datetime.fromisoformat(value_bytes.decode()),
)


class Database:
    """A SQLite database for YouTube subscriptions."""

    # Keep this self-contained as in Textual (we can access its members via `Database.Field.*`)
    class Field(StrEnum):
        """
        Statically-typed SQLite field names.

        Refer to the `Subscription` docstring for more information about what each field represents.
        """

        ID = auto()
        CREATED_AT = auto()
        UPDATED_AT = auto()
        CHANNEL_URL = auto()

    def __init__(self, database_path: Path | None = None) -> None:
        """Create the SQLite database and the table for YouTube subscriptions."""
        # By default, we write to `data/yt.db`, but the database path is overridden in automated tests
        # We could support `:memory:`, but then we'd need to handle `mkdir` and other edge cases, so it's probably
        # not worth it
        if database_path is None:
            database_path = Path("data/yt.db")

        self._database_path: Path = database_path
        self._database_path.parent.mkdir(parents=True, exist_ok=True)

        with self._connect() as connection:
            # Use Write-Ahead Logging (WAL) mode so SQLite appends changes to the WAL file first
            # Readers can keep reading the old database state while writers append new changes (this reduces blocking)
            connection.execute("PRAGMA journal_mode = WAL")

            connection.execute(
                # SQLite `CURRENT_TIMESTAMP` uses UTC in the `YYYY-MM-DD HH:MM:SS` format
                f"""
                CREATE TABLE IF NOT EXISTS subscriptions (
                    {self.Field.ID} INTEGER PRIMARY KEY,
                    {self.Field.CHANNEL_URL} TEXT NOT NULL,
                    {self.Field.CREATED_AT} TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    {self.Field.UPDATED_AT} TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
                );
                """,
            )

        logger.info("Initialized database at {}", self._database_path)

    def read_all(self) -> list[Subscription]:
        """Return all YouTube subscriptions sorted by channel URL."""
        with self._connect() as connection:
            cursor: sqlite3.Cursor = connection.execute(
                f"""
                SELECT
                    {self.Field.ID},
                    {self.Field.CHANNEL_URL},
                    {self.Field.CREATED_AT},
                    {self.Field.UPDATED_AT}
                FROM
                    subscriptions
                ORDER BY
                    {self.Field.CHANNEL_URL} COLLATE NOCASE,
                    {self.Field.ID}
                """,
            )
            rows: list[sqlite3.Row] = cursor.fetchall()

        logger.info("Read {} subscriptions from the database", len(rows))

        # Pydantic does not support `sqlite3.Row`, so convert each row to a `dict` first
        return [Subscription.model_validate(dict(row)) for row in rows]

    def insert_new(self, subscription_input: SubscriptionInput) -> None:
        """Insert a new YouTube subscription."""
        with self._connect() as connection:
            cursor: sqlite3.Cursor = connection.execute(
                f"""
                INSERT INTO subscriptions (
                    {self.Field.CHANNEL_URL}
                )
                VALUES
                    (?)
                """,
                (str(subscription_input.channel_url),),
            )

            inserted_id: int | None = cursor.lastrowid

        logger.info("Created subscription with ID {} for {}", inserted_id, subscription_input.channel_url)

    def update(self, subscription: Subscription) -> None:
        """Update one YouTube subscription."""
        with self._connect() as connection:
            cursor: sqlite3.Cursor = connection.execute(
                f"""
                UPDATE
                    subscriptions
                SET
                    {self.Field.CHANNEL_URL} = ?,
                    {self.Field.UPDATED_AT} = CURRENT_TIMESTAMP
                WHERE
                    {self.Field.ID} = ?
                """,
                (
                    str(subscription.channel_url),
                    subscription.id,
                ),
            )

            # SQLite does not treat updating zero rows as an error
            if cursor.rowcount != 1:
                msg: str = f"Expected to update subscription {subscription.id}, but updated {cursor.rowcount} rows"
                raise RuntimeError(msg)

        logger.info("Updated subscription with ID {}", subscription.id)

    def delete(self, subscription: Subscription) -> None:
        """Delete one YouTube subscription."""
        with self._connect() as connection:
            cursor: sqlite3.Cursor = connection.execute(
                f"""
                DELETE FROM
                    subscriptions
                WHERE
                    {self.Field.ID} = ?
                """,
                (subscription.id,),
            )

            # SQLite does not treat deleting zero rows as an error
            if cursor.rowcount != 1:
                msg: str = f"Expected to delete subscription {subscription.id}, but deleted {cursor.rowcount} rows"
                raise RuntimeError(msg)

        logger.info("Deleted subscription with ID {}", subscription.id)

    @contextmanager
    def _connect(self) -> Generator[sqlite3.Connection]:
        """Open, manage, and close a SQLite connection."""
        # Connect to the `.db` file
        connection: sqlite3.Connection = sqlite3.connect(
            timeout=5.0,
            database=self._database_path,
            detect_types=sqlite3.PARSE_DECLTYPES,
        )

        # Return rows with column-name access (`row["channel_url"]`) instead of plain tuples (`row[1]`)
        connection.row_factory = sqlite3.Row

        # The `sqlite3.Connection` is already a context manager, but it only handles the transaction
        # On success, it calls `commit()`; on exception, it calls `rollback()`, but it never calls `close()`
        with closing(connection), connection:
            yield connection
