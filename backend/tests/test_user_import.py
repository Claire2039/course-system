"""user_import 的纯解析/校验测试（无 DB、无 TestClient）。"""

import pytest

from app.models.constants import UserRole
from app.services import user_import

CSV_STUDENT = "role,name,email,student_no,grade,major\nSTUDENT,S1,s1@seed.example.com,S0001,2024,CS\n"
CSV_TEACHER = "role,name,email,teacher_no,department,title\nTEACHER,T1,t1@seed.example.com,T001,CS,Lecturer\n"
CSV_ADMIN = "role,name,email\nADMIN,A1,a1@seed.example.com\n"


def test_parse_csv_valid() -> None:
    rows = user_import.parse_csv(CSV_STUDENT)
    assert len(rows) == 1
    assert rows[0]["email"] == "s1@seed.example.com"


def test_parse_csv_bad_header() -> None:
    with pytest.raises(ValueError):
        user_import.parse_csv("foo,bar\n1,2\n")


def test_validate_student_ok() -> None:
    users, errors = user_import.validate_rows(user_import.parse_csv(CSV_STUDENT))
    assert not errors
    assert len(users) == 1
    u = users[0]
    assert u.role is UserRole.STUDENT
    assert u.student_no == "S0001"
    assert u.grade == 2024
    assert u.initial_password  # 生成了初始口令


def test_validate_teacher_ok() -> None:
    users, errors = user_import.validate_rows(user_import.parse_csv(CSV_TEACHER))
    assert not errors and len(users) == 1
    assert users[0].role is UserRole.TEACHER


def test_validate_admin_ok() -> None:
    users, errors = user_import.validate_rows(user_import.parse_csv(CSV_ADMIN))
    assert not errors and len(users) == 1
    assert users[0].role is UserRole.ADMIN


def test_validate_missing_student_field() -> None:
    csv = "role,name,email,student_no,grade,major\nSTUDENT,S1,s1@seed.example.com,S0001,,CS\n"
    _, errors = user_import.validate_rows(user_import.parse_csv(csv))
    assert any(e.code == "missing_field" for e in errors)


def test_validate_bad_role() -> None:
    csv = "role,name,email\nWIZARD,W,w@seed.example.com\n"
    _, errors = user_import.validate_rows(user_import.parse_csv(csv))
    assert any(e.code == "invalid_role" for e in errors)


def test_validate_bad_email() -> None:
    csv = "role,name,email\nADMIN,A,not-an-email\n"
    _, errors = user_import.validate_rows(user_import.parse_csv(csv))
    assert any(e.code == "invalid_email" for e in errors)


def test_validate_duplicate_email_in_batch() -> None:
    csv = "role,name,email\nADMIN,A1,a@seed.example.com\nADMIN,A2,a@seed.example.com\n"
    _, errors = user_import.validate_rows(user_import.parse_csv(csv))
    assert any(e.code == "duplicate_email" for e in errors)


def test_build_users_sets_hash_and_flag() -> None:
    users, _ = user_import.validate_rows(user_import.parse_csv(CSV_STUDENT))
    built = user_import.build_users(users)
    assert len(built) == 1
    u = built[0]
    assert u.must_change_password is True
    assert u.password_hash and u.password_hash != users[0].initial_password
    assert u.student is not None and u.student.student_no == "S0001"
