"""Experimental data reference (Level 3 stub)."""

from transport.validation.case import ValidationContext
from transport.validation.references.base import (
    ReferenceCapability,
    ReferenceResult,
    ReferenceSolution,
    ReferenceType,
)


class ExperimentalReference(ReferenceSolution):
    def __init__(self, name: str = "experimental", data_path: str = ""):
        self._name = name
        self.data_path = data_path

    @property
    def name(self) -> str:
        return self._name

    @property
    def reference_type(self) -> ReferenceType:
        return ReferenceType.EXPERIMENTAL

    @property
    def capabilities(self) -> set:
        if self.data_path:
            return {ReferenceCapability.SUMMARY_OBSERVABLES}
        return set()

    def resolve(self, context: ValidationContext) -> ReferenceResult:
        return ReferenceResult(
            reference_type=self.reference_type,
            capabilities=self.capabilities,
            summary_observables={"stub": True, "path": self.data_path},
            metadata={"stub": not bool(self.data_path)},
        )
