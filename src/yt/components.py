from concurrent.futures import Future, ThreadPoolExecutor

import streamlit as st

from yt.config import settings
from yt.database import Database
from yt.structures import Subscription, SubscriptionInput, SubscriptionStatus
from yt.youtube import fetch_subscription_status


@st.cache_resource(show_spinner="Creating SQLite database...")
def _get_database() -> Database:
    """Return the shared SQLite database instance."""
    return Database()


# TODO(ryouze): We should draw the fetched channel immediately instead of waiting until everything is fetched
@st.cache_data(
    # Evict stale cache immediately
    max_entries=1,
    # Do not display a spinner; we will rely on the progress bar instead
    show_spinner=False,
    # Auto-refresh every N seconds
    ttl=settings.refresh_interval_seconds,
)
def _fetch_subscription_statuses(subscriptions: list[Subscription]) -> list[SubscriptionStatus]:
    """Fetch the YouTube subscription statuses from the internet: current channel names and the latest N videos."""
    subscription_statuses: list[SubscriptionStatus] = []

    # Counters
    processed_count: int = 0
    subscription_count: int = len(subscriptions)

    # Progress bar
    progress_text_template: str = "Fetching subscriptions: {processed}/{total}"
    progress_text: str = progress_text_template.format(processed=processed_count, total=subscription_count)
    progress_bar = st.progress(0, text=progress_text)

    # Fetch at most 4 channels to avoid making too many requests to YouTube
    max_workers: int = min(4, subscription_count)

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        subscription_to_futures: list[tuple[Subscription, Future[SubscriptionStatus]]] = [
            (subscription, executor.submit(fetch_subscription_status, subscription)) for subscription in subscriptions
        ]

        # TODO(ryouze): Use `as_completed()` so progress updates as each subscription fetch finishes while preserving
        # subscription order (or sort later?)

        for subscription, future in subscription_to_futures:
            try:
                subscription_status = future.result()
            except Exception as error:
                st.warning(f"Could not fetch {subscription.channel_url}: {error}", icon=":material/warning:")
            else:
                # Append successes, do not append failures
                subscription_statuses.append(subscription_status)
            finally:
                # Whether success or failure, always advance the progress bar
                processed_count += 1

                progress_text = progress_text_template.format(processed=processed_count, total=subscription_count)
                progress_bar.progress(processed_count / subscription_count, text=progress_text)

    progress_bar.empty()

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
        # TODO(ryouze): Use a `st.container(horizontal=True)` here if possible
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

    with st.form("components.draw_modify_page.form.add_subscription", clear_on_submit=True):  # noqa: SIM117
        # Arrange horizontally, hooked to the bottom so the submit button is is aligned with the text field
        with st.container(horizontal=True, wrap=False, vertical_alignment="bottom"):
            new_channel_url: str = st.text_input(
                label="New channel URL",
                type="url",
                placeholder="https://www.youtube.com/@noriyaro",
                required=True,
                label_visibility="collapsed",
                # Perform basic regex validation to ensure it's at least a YouTube link
                # That way, broadly incorrect links are immediately rejected inside the Streamlit UI
                # We will perform thorough extraction within the Pydantic structures afterward
                validate=r"^https://.*youtube\.com.*$",
            )
            is_add_new_channel_url_pressed: bool = st.form_submit_button(
                # TODO(ryouze): Make this consistent through the app: do we call them "channels" or "subscriptions"?
                label="Add",
                help="Add the entered YouTube channel URL to the list of subscribed channels",
                type="primary",
                icon=":material/add:",
            )

    if is_add_new_channel_url_pressed:
        # TODO(ryouze): Check if this is the best way to create a validated Pydantic model
        subscription_input = SubscriptionInput.model_validate({Database.Field.CHANNEL_URL: new_channel_url})
        database.insert_new(subscription_input)
        st.rerun()

    with st.container(border=True):
        if not subscriptions:
            st.info("No subscriptions added yet. Please add one in the form above.", icon=":material/lightbulb:")
            return

        for subscription in subscriptions:
            # This will be re-used often within the loop
            channel_url_str = str(subscription.channel_url)

            with st.container(horizontal=True, wrap=False):
                st.link_button(
                    label=channel_url_str,
                    url=channel_url_str,
                    help="Open this channel in a new tab",
                    type="tertiary",
                    icon=":material/person:",
                )

                # Greedily fill remaining space between content-sized widgets
                st.space("stretch")

                with st.popover(
                    label=":material/edit:",
                    help="Edit the channel URL or delete the subscription",
                ):
                    with (
                        st.form(
                            key=f"components.draw_modify_page.form.edit_subscription.{subscription.id}",
                            clear_on_submit=True,
                            border=False,
                        ),
                        st.container(horizontal=True, wrap=False, vertical_alignment="bottom"),
                    ):
                        modified_channel_url: str = st.text_input(
                            label="Modified channel URL",
                            value=channel_url_str,
                            type="url",
                            placeholder="https://www.youtube.com/@noriyaro",
                            required=True,
                            label_visibility="collapsed",
                            # Perform basic regex validation to ensure it's at least a YouTube link
                            # That way, broadly incorrect links are immediately rejected inside the Streamlit UI
                            # We will perform thorough extraction within the Pydantic structures afterward
                            validate=r"^https://.*youtube\.com.*$",
                        )
                        is_modify_existing_channel_url_pressed: bool = st.form_submit_button(
                            label="Set URL",
                            help="Set the YouTube channel URL to the entered URL",
                            type="primary",
                            icon=":material/send:",
                        )

                    if is_modify_existing_channel_url_pressed:
                        updated_subscription = subscription.with_changes(
                            {Database.Field.CHANNEL_URL: modified_channel_url},
                        )
                        database.update(updated_subscription)
                        st.rerun()

                    is_delete_existing_channel_pressed: bool = st.button(
                        label="Delete channel",
                        # This isn't a `st.form_submit_button` so we need unique keys to avoid
                        # `StreamlitDuplicateElementId`
                        key=f"components.draw_modify_page.button.delete_subscription.{subscription.id}",
                        help="Delete the YouTube channel permanently",
                        type="primary",
                        icon=":material/delete_forever:",
                        width="stretch",
                    )
                    if is_delete_existing_channel_pressed:
                        database.delete(subscription)
                        st.rerun()
