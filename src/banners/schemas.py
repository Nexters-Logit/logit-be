"""배너 응답 스키마."""

from datetime import datetime

from pydantic import BaseModel


class BannerResponse(BaseModel):
    id: int
    image_url: str
    link_url: str | None
    is_visible: bool
    display_order: int
    created_at: datetime

    @classmethod
    def from_model(cls, banner: object) -> "BannerResponse":
        return cls(
            id=banner.id,
            image_url=banner.image_url,
            link_url=banner.link_url,
            is_visible=banner.is_visible,
            display_order=banner.display_order,
            created_at=banner.created_at,
        )
