from typing import TYPE_CHECKING, ClassVar

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    HttpUrl,
    NaiveDatetime,
    PositiveInt,
    field_validator,
)

if TYPE_CHECKING:
    from collections.abc import Mapping


class _AppBaseModel(BaseModel):
    """Shared stricter Pydantic configuration."""

    model_config: ClassVar[ConfigDict] = ConfigDict(
        # Reject inputs that require implicit type coercion
        strict=True,
        # Prevent models from being mutated after construction
        frozen=True,
        # Reject undeclared fields instead of silently discarding them
        extra="forbid",
    )


class SubscriptionInput(_AppBaseModel):
    """
    A single YouTube subscription (channel URL) used as an input row for the SQLite database.

    Attributes:
        channel_url (HttpUrl): YouTube channel URL (e.g., `https://www.youtube.com/@noriyaro`).
    """

    channel_url: HttpUrl

    @field_validator("channel_url")
    @classmethod
    def _validate_channel_url(cls, value: HttpUrl) -> HttpUrl:
        """Validate and normalize a YouTube channel URL."""
        # Accept only YouTube's normal desktop, root, and mobile hosts
        if value.host not in ("youtube.com", "www.youtube.com", "m.youtube.com"):
            msg: str = f"URL {value.host} does not point to youtube.com"
            raise ValueError(msg)

        # Convert `/@noriyaro/videos` to `["@noriyaro", "videos"]`
        path_parts: list[str] = (value.path or "").strip("/").split("/")

        channel_path: str

        if path_parts[0].startswith("@") and len(path_parts[0]) > 1:
            # Modern channel URLs use a handle such as `/@noriyaro`
            channel_path = path_parts[0]

        elif len(path_parts) > 1 and path_parts[0] in ("channel", "c", "user") and path_parts[1]:
            # Older channel URLs use `/channel/<id>`, `/c/<name>`, or `/user/<name>`
            channel_path = f"{path_parts[0]}/{path_parts[1]}"

        else:
            # Reject other YouTube URLs such as videos, playlists, search pages, and bare channel prefixes
            msg: str = f"URL {value.path} must point to a YouTube channel"
            raise ValueError(msg)

        return HttpUrl(f"https://www.youtube.com/{channel_path}")

    @property
    def channel_videos_url(self) -> HttpUrl:
        """Return the channel URL pointing to its videos page (e.g., `https://www.youtube.com/@noriyaro/videos`)."""
        # `channel_url` is always stored without a trailing slash, so `/videos` can be appended safely
        return HttpUrl(f"{self.channel_url}/videos")


class Subscription(SubscriptionInput):
    """
    A single YouTube subscription (channel URL) read as output from the SQLite database.

    Attributes:
        channel_url (HttpUrl): YouTube channel URL (e.g., `https://www.youtube.com/@noriyaro`).
        id (PositiveInt): Unique SQLite row identifier for the subscription (e.g., `1`).
        created_at (NaiveDatetime): Date and time when the subscription was created (e.g., `2026-09-03 12:34:56`).
        updated_at (NaiveDatetime): Date and time when the subscription was last updated (e.g., `2026-09-03 12:34:56`).
    """

    id: PositiveInt
    # We use SQLite's UTC time zone as-is
    created_at: NaiveDatetime
    updated_at: NaiveDatetime

    def with_changes(self, changes: Mapping[str, object]) -> Subscription:
        """Create a subscription with changes applied to the current values."""
        subscription_data: dict[str, object] = self.model_dump()
        subscription_data.update(changes)
        return Subscription.model_validate(subscription_data)


class Video(_AppBaseModel):
    """
    A single YouTube video.

    Attributes:
        video_url (HttpUrl): YouTube video URL (e.g., `https://www.youtube.com/watch?v=...`).
        thumbnail_url (HttpUrl): YouTube video thumbnail image URL (e.g., `https://i.ytimg.com/vi/.../mqdefault.jpg`).
        video_title (str): YouTube video title (e.g., `I bought a PVC Daihatsu Mira`).
    """

    video_url: HttpUrl
    thumbnail_url: HttpUrl
    video_title: str = Field(min_length=1)


class SubscriptionStatus(_AppBaseModel):
    """
    A single YouTube subscription status: current name and the latest N videos.

    Attributes:
        name (str): YouTube channel name (e.g., `Noriyaro`).
        videos (list[Video]): Latest N YouTube videos.
    """

    name: str = Field(min_length=1)
    videos: list[Video] = Field(min_length=1)
