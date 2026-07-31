"""slots_conflict 纯单元测试（无 DB）。"""

from app.services.enrollment_service import slots_conflict


def test_no_conflict_different_days() -> None:
    assert slots_conflict([(1, 1, 2)], [(2, 1, 2)]) is False


def test_no_conflict_same_day_non_overlapping() -> None:
    assert slots_conflict([(1, 1, 2)], [(1, 3, 4)]) is False


def test_conflict_same_day_overlapping() -> None:
    assert slots_conflict([(1, 1, 3)], [(1, 2, 4)]) is True


def test_touching_periods_do_not_conflict() -> None:
    # [1,2] 与 [2,3] 首尾相接，不算冲突（背靠背上课）。
    assert slots_conflict([(1, 1, 2)], [(1, 2, 3)]) is False


def test_empty_does_not_conflict() -> None:
    assert slots_conflict([], [(1, 1, 2)]) is False
    assert slots_conflict([(1, 1, 2)], []) is False


def test_multiple_slots() -> None:
    a = [(1, 1, 2), (3, 3, 4)]
    b = [(1, 2, 3), (3, 4, 5)]  # 均首尾相接 → 无冲突
    assert slots_conflict(a, b) is False
    c = [(3, 3, 5)]  # 与 a 的 (3,3,4) 重叠
    assert slots_conflict(a, c) is True
