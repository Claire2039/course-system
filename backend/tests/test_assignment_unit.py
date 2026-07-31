"""compute_submit_status 纯单测（无 DB）。"""

from datetime import datetime, timedelta, timezone

import pytest

from app.models.constants import SubmissionStatus
from app.services.assignment_service import AssignmentError, compute_submit_status

NOW = datetime(2026, 7, 31, 12, tzinfo=timezone.utc)


def test_on_time_is_submitted() -> None:
    due = NOW + timedelta(days=1)
    assert compute_submit_status(NOW, due, None, False) == SubmissionStatus.SUBMITTED


def test_late_when_allow_late_within_late_deadline() -> None:
    due = NOW - timedelta(hours=1)
    late = NOW + timedelta(days=1)
    assert compute_submit_status(NOW, due, late, True) == SubmissionStatus.LATE


def test_rejected_past_hard_deadline_no_late() -> None:
    due = NOW - timedelta(hours=1)
    with pytest.raises(AssignmentError) as ei:
        compute_submit_status(NOW, due, None, False)
    assert ei.value.code == "deadline_passed"


def test_rejected_past_late_deadline() -> None:
    due = NOW - timedelta(days=2)
    late = NOW - timedelta(hours=1)
    with pytest.raises(AssignmentError):
        compute_submit_status(NOW, due, late, True)


def test_rejected_when_allow_late_but_no_late_deadline() -> None:
    due = NOW - timedelta(hours=1)
    with pytest.raises(AssignmentError):
        compute_submit_status(NOW, due, None, True)
