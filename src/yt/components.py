from concurrent.futures import Future, ThreadPoolExecutor
from typing import TYPE_CHECKING

import pandas as pd
import streamlit as st

from yt.config import settings
from yt.database import Database
from yt.structures import Subscription, SubscriptionInput, SubscriptionStatus
from yt.youtube import fetch_subscription_status

if TYPE_CHECKING:
    from streamlit.typing import DataEditorState


@st.cache_resource(show_spinner="Creating SQLite database...")
def _get_database() -> Database:
    """Return the shared SQLite database instance."""
    return Database()


@st.cache_data(
    # Evict stale cache immediately
    max_entries=1,
    show_time=True,
    # Auto-refresh every N seconds
    ttl=settings.refresh_interval_seconds,
    show_spinner="Fetching the latest available videos...",
)
def _fetch_subscription_statuses(subscriptions: list[Subscription]) -> list[SubscriptionStatus]:
    """Fetch the YouTube subscription statuses from the internet: current channel names and the latest N videos."""
    # Fetch at most 4 channels to avoid making too many requests to YouTube
    max_workers: int = min(4, len(subscriptions))

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        subscription_to_futures: list[tuple[Subscription, Future[SubscriptionStatus]]] = [
            (subscription, executor.submit(fetch_subscription_status, subscription)) for subscription in subscriptions
        ]

        subscription_statuses: list[SubscriptionStatus] = []

        for subscription, future in subscription_to_futures:
            try:
                subscription_status = future.result()
            except Exception as error:
                st.warning(f"Could not fetch {subscription.channel_url}: {error}", icon=":material/warning:")
                continue

            subscription_statuses.append(subscription_status)

    return subscription_statuses


def draw_browse_page() -> None:
    """Show the latest videos from all YouTube subscriptions."""
    # Always run everything on the latest list of subscriptions so that if a user adds a new one, we fetch again
    database = _get_database()
    subscriptions: list[Subscription] = database.read_all()

    # The SQLite database will be empty on first boot, so handle that
    if not subscriptions:
        st.info("No subscriptions found. Please add some in the `Modify` tab.", icon=":material/lightbulb:")
        return

    # Fetch data from YouTube, with caching to avoid repeated calls
    subscription_statuses: list[SubscriptionStatus] = _fetch_subscription_statuses(subscriptions)

    for subscription_status in subscription_statuses:
        st.subheader(subscription_status.name)

        # Keep every video in a single horizontally scrollable row
        # This is better than `st.container` because each video gets an equal-width column
        cols = st.columns(
            wrap=False,
            gap="xsmall",
            spec=len(subscription_status.videos),
        )

        for col, video in zip(cols, subscription_status.videos, strict=True):
            with col:
                # The images are clickable, just like on the real YouTube homepage
                st.image(
                    width="stretch",
                    caption=video.video_title,
                    link=str(video.video_url),
                    image=str(video.thumbnail_url),
                )


def draw_modify_page() -> None:
    """Show the YouTube subscription manager."""
    # Always run this on the latest list of subscriptions so that if a user adds a new one, we fetch again
    database = _get_database()
    subscriptions: list[Subscription] = database.read_all()

    # Pandas is the easiest way to pass data to `st.data_editor` (Streamlit requires pandas anyway)
    # Using dicts will work if there is more than one entry; otherwise, `st.data_editor` defaults to floats
    subscriptions_df = pd.DataFrame(
        # Define columns so that if there are no subscriptions yet, it uses `object`
        columns=[Database.Field.CHANNEL_URL],
        data=[{Database.Field.CHANNEL_URL: str(s.channel_url)} for s in subscriptions],
    )

    data_editor_key: str = "app.editor.data_editor"

    st.data_editor(
        data=subscriptions_df,
        # Expand to fit the content, since there is nothing on the page besides this table anyway
        height="content",
        hide_index=True,
        column_config={
            Database.Field.CHANNEL_URL: st.column_config.LinkColumn(
                label="Channel URL",
                help="Link to the YouTube channel (e.g., `https://www.youtube.com/@noriyaro`)",
                required=True,
                # Perform basic regex validation to ensure it's at least a YouTube link
                # That way, broadly incorrect links are immediately rejected inside the Streamlit UI
                # We will perform thorough extraction within the Pydantic structures afterward
                validate=r"^https://.*youtube\.com.*$",
            ),
        },
        key=data_editor_key,
        # Enable add/edit/delete mode
        num_rows="dynamic",
        placeholder="...",
    )

    editor_state: DataEditorState = st.session_state[data_editor_key]  # pyright: ignore[reportAny]

    for row_position, edited_values in editor_state.edited_rows.items():
        # A row deleted without prior edits may be absent from `edited_rows`
        # An edited-then-deleted row can appear in both
        if row_position in editor_state.deleted_rows:
            continue

        subscription: Subscription = subscriptions[row_position].with_changes(edited_values)
        database.update(subscription)

    for row_position in editor_state.deleted_rows:
        subscription: Subscription = subscriptions[row_position]
        database.delete(subscription)

    for added_row in editor_state.added_rows:
        subscription_input = SubscriptionInput.model_validate(added_row)
        database.insert_new(subscription_input)
