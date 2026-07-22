"""Unified batch pipeline foundations."""

from .models import BatchItem, BatchManifest, InputManifest, PipelinePlan
from .planner import InvalidScopeError, PipelinePlanner, PlanningError, UnknownGroupError
from .provenance import (
    DirtyWorktreeError,
    GitHeadError,
    ProductIndexDriftError,
    ProvenanceDriftError,
    ProvenanceError,
    ProvenanceProvider,
)
from .state_store import (
    ImmutableManifestError,
    ManifestConflictError,
    ManifestValidationError,
    RepositoryLock,
    RepositoryLockError,
    StateStoreError,
    StateStore,
    UnknownBatchError,
    generate_batch_id,
)

__all__ = [
    "BatchItem",
    "BatchManifest",
    "DirtyWorktreeError",
    "ImmutableManifestError",
    "InputManifest",
    "InvalidScopeError",
    "GitHeadError",
    "ManifestConflictError",
    "ManifestValidationError",
    "PipelinePlan",
    "PipelinePlanner",
    "PlanningError",
    "ProductIndexDriftError",
    "ProvenanceDriftError",
    "ProvenanceError",
    "ProvenanceProvider",
    "RepositoryLock",
    "RepositoryLockError",
    "StateStore",
    "StateStoreError",
    "UnknownBatchError",
    "UnknownGroupError",
    "generate_batch_id",
]
