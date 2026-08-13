"""The only three verdict-relevant algorithm identities in v0.5.1."""

RECONSTRUCTION_PROFILE_VERSION = "independent-state-reconstruction-v1"
WIRE_TRANSFORM_VERSION = "independent-cms-wire-v1"
COMPARISON_VERSION = "independent-html-comparison-v1"

ALGORITHM_VERSIONS = {
    "reconstruction_profile_version": RECONSTRUCTION_PROFILE_VERSION,
    "wire_transform_version": WIRE_TRANSFORM_VERSION,
    "comparison_version": COMPARISON_VERSION,
}

V053_RECONSTRUCTION_PROFILE_VERSION = (
    "independent-four-family-reconstruction-v1"
)
V053_WIRE_TRANSFORM_VERSION = "independent-cms-wire-v2"
V053_COMPARISON_VERSION = "independent-content-comparison-v2"

V053_ALGORITHM_VERSIONS = {
    "reconstruction_profile_version": V053_RECONSTRUCTION_PROFILE_VERSION,
    "wire_transform_version": V053_WIRE_TRANSFORM_VERSION,
    "comparison_version": V053_COMPARISON_VERSION,
}

V055_RECONSTRUCTION_PROFILE_VERSION = (
    "independent-simple-page-global-reconstruction-v2"
)
V055_WIRE_TRANSFORM_VERSION = V053_WIRE_TRANSFORM_VERSION
V055_COMPARISON_VERSION = V053_COMPARISON_VERSION

V055_ALGORITHM_VERSIONS = {
    "reconstruction_profile_version": V055_RECONSTRUCTION_PROFILE_VERSION,
    "wire_transform_version": V055_WIRE_TRANSFORM_VERSION,
    "comparison_version": V055_COMPARISON_VERSION,
}


def algorithm_versions_for_reconstruction(
    reconstruction_profile_version: str,
) -> dict[str, str]:
    """Resolve only the two frozen four-family/simple-page contracts."""

    if reconstruction_profile_version == V053_RECONSTRUCTION_PROFILE_VERSION:
        return dict(V053_ALGORITHM_VERSIONS)
    if reconstruction_profile_version == V055_RECONSTRUCTION_PROFILE_VERSION:
        return dict(V055_ALGORITHM_VERSIONS)
    raise ValueError(
        "Unsupported Independent Fidelity reconstruction profile: "
        f"{reconstruction_profile_version!r}"
    )
