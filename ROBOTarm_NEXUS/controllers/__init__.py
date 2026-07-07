"""Controller exports for the standalone SO101 package.

Exports:
    PlanarSideViewJointController — dual-backend IK:
        - compute_action()              → manual DLS (side-view panel mode)
        - compute_action_to_world_position() → official Lula position-only IK
"""
from .lula_ik import (
    PlanarSideViewJointController,
    PlanarPanelIKConfig,
    PlanarEeFeedback,
)
