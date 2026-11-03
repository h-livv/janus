"""Transfer-matrix reference (stub for Level 2)."""

from transport.validation.case import ValidationContext
from transport.validation.references.base import (
    ReferenceCapability,
    ReferenceResult,
    ReferenceSolution,
    ReferenceType,
)


class TransferMatrixReference(ReferenceSolution):
    def __init__(self, name: str = "transfer_matrix", matrix=None):
        self._name = name
        self.matrix = matrix

    @property
    def name(self) -> str:
        return self._name

    @property
    def reference_type(self) -> ReferenceType:
        return ReferenceType.TRANSFER_MATRIX

    @property
    def capabilities(self) -> set:
        caps = {ReferenceCapability.MOMENT_PROPAGATION}
        if self.matrix is not None:
            caps.add(ReferenceCapability.SUMMARY_OBSERVABLES)
        return caps

    def resolve(self, context: ValidationContext) -> ReferenceResult:
        return ReferenceResult(
            reference_type=self.reference_type,
            capabilities=self.capabilities,
            moment_propagation=self.matrix,
            metadata={"stub": self.matrix is None},
        )
