"""Request models for Sherlock batches."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

__all__ = ["CreateBatchRequest"]


@dataclass
class CreateBatchRequest:
    """Payload for :meth:`sherlock_api.SherlockAPIClient.post_batch`.

    Args:
        case_id: Id of the case the batch belongs to.
        batch_name: Human-readable name of the batch.
    """

    case_id: str
    batch_name: str

    def to_dict(self) -> dict[str, Any]:
        """Serialize to the JSON body expected by ``POST /batch``."""
        return {
            "case_id": self.case_id,
            "batch_name": self.batch_name,
        }
