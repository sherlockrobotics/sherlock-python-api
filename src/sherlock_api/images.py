"""Request models for Sherlock images."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any

__all__ = ["DecisionClass", "CreateImageRequest"]


class DecisionClass(Enum):
    """Inspection verdict attached to an image."""

    Ok = "Ok"
    NotOk = "NotOk"
    NaN = "NaN"


@dataclass
class CreateImageRequest:
    """Payload for :meth:`sherlock_api.SherlockAPIClient.post_image`.

    Args:
        batch_id: Id of the batch the image belongs to.
        image_name: Human-readable name of the image.
        decision_class: Inspection verdict for the image.
        image_hash: File hash of the already-uploaded image bytes, as returned
            by :meth:`~sherlock_api.SherlockAPIClient.post_file_from_memory`.
    """

    batch_id: str
    image_name: str
    decision_class: DecisionClass
    image_hash: str

    def to_dict(self) -> dict[str, Any]:
        """Serialize to the JSON body expected by ``POST /image``."""
        return {
            "batch_id": self.batch_id,
            "image_name": self.image_name,
            "decision_class": self.decision_class.value,
            # The wire field is named "image_data" but carries a file hash.
            "image_data": self.image_hash,
        }
