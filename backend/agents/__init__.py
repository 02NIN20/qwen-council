"""Council agents package.

Each agent inherits from BaseAgent and implements the `analyze` method
that calls the Qwen Cloud API with a specialised prompt.
"""

from backend.agents.architecture_agent import ArchitectureAgent
from backend.agents.performance_agent import PerformanceAgent
from backend.agents.quality_agent import QualityAgent
from backend.agents.security_agent import SecurityAgent
from backend.agents.ux_agent import UXAgent
from backend.agents.vision_agent import VisionAgent

__all__ = [
    "ArchitectureAgent",
    "PerformanceAgent",
    "QualityAgent",
    "SecurityAgent",
    "UXAgent",
    "VisionAgent",
]
