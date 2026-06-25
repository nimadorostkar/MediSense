"""Role-based access control (spec §4.2, §8).

The permission matrix is authoritative and enforced at the API boundary.
Least-privilege: only Physician confirms a diagnosis / signs an Rx; only
Pharmacist verifies/holds; audit export is limited to Admin/Safety/IT. Separation
of duties: the role that authors a model release cannot approve it.
"""

from __future__ import annotations

from enum import StrEnum


class Role(StrEnum):
    PHYSICIAN = "physician"
    NURSE = "nurse"
    PHARMACIST = "pharmacist"
    ADMIN = "admin"
    SAFETY = "safety"  # Safety / ML governance
    IT = "it"  # IT / Operator


class Permission(StrEnum):
    VIEW_TRIAGE = "view_triage"
    CAPTURE_INTAKE = "capture_intake"
    VIEW_DIFFERENTIAL = "view_differential"
    CONFIRM_DIAGNOSIS = "confirm_diagnosis"
    REQUEST_RX = "request_rx"
    SIGN_RX = "sign_rx"
    VERIFY_RX = "verify_rx"
    OVERRIDE_SAFETY = "override_safety"
    CAPTURE_OUTCOME = "capture_outcome"
    CAPTURE_EPISODE = "capture_episode"
    APPROVE_MODEL = "approve_model"
    EXPORT_AUDIT = "export_audit"


# Permission → set of roles allowed (spec §4.2 matrix).
MATRIX: dict[Permission, set[Role]] = {
    Permission.VIEW_TRIAGE: {Role.PHYSICIAN, Role.NURSE, Role.PHARMACIST, Role.ADMIN},
    Permission.CAPTURE_INTAKE: {Role.PHYSICIAN, Role.NURSE},
    Permission.VIEW_DIFFERENTIAL: {Role.PHYSICIAN, Role.NURSE},
    Permission.CONFIRM_DIAGNOSIS: {Role.PHYSICIAN},
    Permission.REQUEST_RX: {Role.PHYSICIAN},
    Permission.SIGN_RX: {Role.PHYSICIAN},
    Permission.VERIFY_RX: {Role.PHARMACIST},
    Permission.OVERRIDE_SAFETY: {Role.PHYSICIAN, Role.PHARMACIST},
    Permission.CAPTURE_OUTCOME: {Role.PHYSICIAN, Role.NURSE},
    Permission.CAPTURE_EPISODE: {Role.PHYSICIAN, Role.SAFETY, Role.ADMIN},
    Permission.APPROVE_MODEL: {Role.SAFETY},
    Permission.EXPORT_AUDIT: {Role.ADMIN, Role.SAFETY, Role.IT},
}


def has_permission(role: str, permission: Permission) -> bool:
    try:
        r = Role(role)
    except ValueError:
        return False
    return r in MATRIX.get(permission, set())
