from loguru import logger
from pydantic import HttpUrl
from yt_dlp import YoutubeDL

from yt.structures import Subscription, SubscriptionStatus, Video


def fetch_subscription_status(subscription: Subscription) -> SubscriptionStatus:
    """Retrieve the YouTube subscription status from the internet: current channel name and the latest N videos."""
    # We need to retrieve more content than necessary because YouTube also returns live streams, shorts, etc.
    requested_video_amount: int = 5
    requested_total_amount: int = 15

    logger.info("Fetching subscription status for {}", subscription.channel_url)

    yt_dlp_options: dict[str, object] = {
        "quiet": True,
        # Process playlist entries as yt-dlp receives them instead of parsing the entire playlist first
        "lazy_playlist": True,
        # Do not open every individual video page when the channel tab already provides the metadata we need
        "extract_flat": "in_playlist",
        # Inspect only the first N entries from the channel's Videos tab
        "playlist_items": f"1:{requested_total_amount}",
    }

    with YoutubeDL(yt_dlp_options) as youtube_dl:  # pyright: ignore[reportArgumentType]
        channel_data = youtube_dl.extract_info(
            download=False,
            url=str(subscription.channel_videos_url),
        )

    # yt-dlp can return `None` if an extractor returns no result despite its return type annotation
    if channel_data is None:  # pyright: ignore[reportUnnecessaryComparison]
        msg: str = f"yt-dlp returned no data for {subscription.channel_url}"
        raise RuntimeError(msg)

    # We do not store the channel name inside the SQLite database because it can change, and keeping it up to date
    # sounds like a good example of over-engineering
    channel_name: str | None = channel_data.get("channel")

    if not channel_name:
        msg: str = f"yt-dlp returned no channel name for {subscription.channel_url}"
        raise RuntimeError(msg)

    videos: list[Video] = []

    for entry in channel_data.get("entries", []):
        if entry is None:
            logger.debug("Skipping empty yt-dlp entry for {}", subscription.channel_url)
            continue

        video_id: str | None = entry.get("id")
        video_url: str | None = entry.get("url")
        title: str | None = entry.get("title")

        if video_id is None or video_url is None or title is None:
            logger.debug("Skipping incomplete yt-dlp entry for {}", subscription.channel_url)
            continue

        # Reject YouTube Shorts if yt-dlp identifies an entry as one
        if "/shorts/" in video_url:
            logger.debug("Skipping YouTube Short {} for {}", video_url, subscription.channel_url)
            continue

        # Reject current, upcoming, and archived live streams
        live_status: str | None = entry.get("live_status")

        if live_status not in (None, "not_live"):
            logger.debug("Skipping {} video {} for {}", live_status, video_url, subscription.channel_url)
            continue

        videos.append(
            Video(
                video_title=title,
                video_url=HttpUrl(video_url),
                # Use YouTube's fixed small 16:9 thumbnail
                thumbnail_url=HttpUrl(f"https://i.ytimg.com/vi/{video_id}/mqdefault.jpg"),
            ),
        )

        if len(videos) >= requested_video_amount:
            break

    logger.info(
        "Fetched subscription status for {}: {} with {} videos",
        subscription.channel_url,
        channel_name,
        len(videos),
    )

    return SubscriptionStatus(
        videos=videos,
        name=channel_name,
    )
