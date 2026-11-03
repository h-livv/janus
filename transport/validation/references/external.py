"""External simulation reference (MAD-X/Elegant/GPT stub)."""

from transport.validation.case import ValidationContext
from transport.validation.references.base import (
    ReferenceCapability,
    ReferenceResult,
    ReferenceSolution,
    ReferenceType,
)


class ExternalSimulationReference(ReferenceSolution):
    def __init__(self, name: str = "external", source_path: str = ""):
        self._name = name
        self.source_path = source_path

    @property
    def name(self) -> str:
        return self._name

    @property
    def reference_type(self) -> ReferenceType:
        return ReferenceType.EXTERNAL

    @property
    def capabilities(self) -> set:
        if self.source_path:
            return {
                ReferenceCapability.POINTWISE_TRAJECTORY,
                ReferenceCapability.SUMMARY_OBSERVABLES,
            }
        return set()

    def resolve(self, context: ValidationContext) -> ReferenceResult:
        return ReferenceResult(
            reference_type=self.reference_type,
            capabilities=self.capabilities,
            metadata={"stub": True, "path": self.source_path},
        )
