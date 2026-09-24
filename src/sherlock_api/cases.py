"""Request models for Sherlock cases."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any

__all__ = ["RobotPlatform", "CreateCaseRequest"]


class RobotPlatform(Enum):
    """Robot platform a case runs on."""

    UNIVERSAL_ROBOTS = "UniversalRobots"


@dataclass
class CreateCaseRequest:
    """Payload for :meth:`sherlock_api.SherlockAPIClient.post_case`.

    Args:
        case_name: Human-readable name of the case.
        robot_platform: Platform the case's procedure targets.
        robot_procedure: Hash of the robot procedure to run.
        thumbnail: Optional file hash of a thumbnail image, as returned by
            :meth:`~sherlock_api.SherlockAPIClient.post_file`.
    """

    case_name: str
    robot_platform: RobotPlatform
    robot_procedure: str
    thumbnail: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Serialize to the JSON body expected by ``POST /case``."""
        return {
            "case_name": self.case_name,
            "robot_platform": self.robot_platform.value,
            "robot_procedure": self.robot_procedure,
            "thumbnail": self.thumbnail,
        }
