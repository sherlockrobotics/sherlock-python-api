"""Request models for Sherlock measurements."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

__all__ = ["CreateMeasurementRequest"]


@dataclass
class CreateMeasurementRequest:
    """Payload for :meth:`sherlock_api.SherlockAPIClient.post_measurement`.

    Args:
        image_id: Id of the image the measurement belongs to.
        key: Name of the measured quantity.
        value: Measured value. Numbers are stringified on serialization.
    """

    image_id: str
    key: str
    value: str | float | int

    def to_dict(self) -> dict[str, Any]:
        """Serialize to the JSON body expected by ``POST /measurement``."""
        return {
            "image_id": self.image_id,
            "key": self.key,
            "value": str(self.value),
        }
