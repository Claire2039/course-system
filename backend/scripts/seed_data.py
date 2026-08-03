"""种子数据脚本：一键生成可演示的初始数据集（华侨大学工学院版）。

在 api 容器内运行（镜像已含本脚本与依赖、且可连 DB）：

    python -m scripts.seed_data            # 已有当前学期则跳过（幂等）
    python -m scripts.seed_data --reset    # 清空后重建

生成：12 钟点 / 1 ADMIN / 20 教师（含教师简介）/ 2000 学生 / 1 当前学期（选课窗口已开）/
7 个工科专业共 ~30 门课程（含课程介绍）/ 少量先修关系 / ~45 教学班（含 1 个 capacity=1）/
若干时段。入门课程无先修，方便演示选课。
"""

import argparse
import asyncio
from datetime import datetime, time, timedelta, timezone

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import AsyncSessionLocal
from app.models import (  # noqa: F401  导入即注册模型
    Course,
    CoursePrerequisite,
    PeriodDef,
    Section,
    Semester,
    Student,
    Teacher,
    TimeSlot,
    User,
)
from app.models.constants import UserRole

# ---------- 生成参数 ----------
TEACHER_TITLES = ["教授", "副教授", "副教授", "讲师"]  # 权重：副教授多
GRADES = [2022, 2023, 2024, 2025]
CREDIT_OPTIONS = [3, 4, 2, 3, 4]
CAPACITY_TIERS = [30, 60, 120]

PERIOD_COUNT = 12
TEACHER_COUNT = 20
STUDENT_COUNT = 2000
BATCH_SIZE = 500

INITIAL_PASSWORD = "InitPass#2026"  # 所有学生/教师共用，首登强制改
ADMIN_EMAIL = "admin@seed.example.com"
ADMIN_PASSWORD = "Admin#2026"  # 演示账号，可直登

# 华侨大学工学院 —— 专业（即院系）
DEPARTMENTS = [
    "计算机科学与技术",
    "电子信息工程",
    "机械工程",
    "土木工程",
    "电气工程及其自动化",
    "材料与化工",
    "建筑学",
]

# 课程：(代码, 名称, 学分, 所属专业, 课程介绍)
COURSES = [
    ("CS101", "计算机程序设计基础", 3, "计算机科学与技术", "讲授 C/Python 编程基础、数据类型、控制结构、函数与基本算法，培养计算思维与动手编程能力。"),
    ("CS102", "数据结构", 4, "计算机科学与技术", "线性表、栈与队列、树与图、排序与查找等基本数据结构及其算法实现与分析。"),
    ("CS201", "计算机组成原理", 3, "计算机科学与技术", "从冯·诺依曼结构出发，讲解运算器、存储器、指令系统与 CPU 数据通路的设计原理。"),
    ("CS202", "操作系统", 4, "计算机科学与技术", "进程与线程、内存管理、文件系统与设备管理，理解现代操作系统的核心机制。"),
    ("CS301", "数据库系统", 3, "计算机科学与技术", "关系模型、SQL、事务与并发控制、数据库设计与优化。"),
    ("EE101", "电路分析基础", 4, "电子信息工程", "直流与交流电路、基尔霍夫定律、网络定理与暂态分析，建立电路分析的基本方法。"),
    ("EE102", "模拟电子技术", 4, "电子信息工程", "半导体器件、放大电路、反馈与振荡、集成运放及其应用。"),
    ("EE201", "数字电子技术", 3, "电子信息工程", "逻辑门、组合与时序逻辑电路、数模转换，数字系统的设计入门。"),
    ("EE202", "信号与系统", 3, "电子信息工程", "连续与离散信号、傅里叶变换、系统函数，信号分析与处理的理论基础。"),
    ("ME101", "工程制图", 3, "机械工程", "制图标准、三视图、零件图与装配图，培养空间想象与工程表达能力。"),
    ("ME102", "理论力学", 4, "机械工程", "静力学、运动学与动力学，研究物体机械运动的基本规律。"),
    ("ME201", "机械设计基础", 4, "机械工程", "连杆、齿轮、轴系等常用机构的原理与设计计算。"),
    ("ME202", "材料力学", 4, "机械工程", "拉压、扭转、弯曲与组合变形的应力与强度分析方法。"),
    ("CE101", "工程力学", 4, "土木工程", "静力学与材料力学基础，土木工程的核心力学入门。"),
    ("CE102", "结构力学", 4, "土木工程", "杆系结构的内力、位移与稳定分析，混凝土与钢结构设计的力学基础。"),
    ("CE201", "混凝土结构设计", 4, "土木工程", "受弯、受压构件的承载力计算与构造要求，混凝土结构设计原理。"),
    ("CE202", "测量学", 3, "土木工程", "水准测量、角度测量、地形图测绘与施工放样。"),
    ("AU101", "自动控制原理", 4, "电气工程及其自动化", "控制系统数学模型、时域与频域分析、稳定性与校正，自动化的理论核心。"),
    ("AU102", "电机与拖动", 3, "电气工程及其自动化", "直流电机、变压器、交流电机原理及其电力拖动系统。"),
    ("AU201", "电力电子技术", 3, "电气工程及其自动化", "整流、逆变、斩波与变频电路，功率半导体器件与应用。"),
    ("MC101", "物理化学", 4, "材料与化工", "热力学、相平衡、化学动力学与电化学，材料与化工的理论基础。"),
    ("MC102", "材料科学基础", 4, "材料与化工", "晶体结构、缺陷、相图与材料性能关系，材料工程入门。"),
    ("MC201", "化工原理", 4, "材料与化工", "流体流动、传热、传质与单元操作，化工过程的核心原理。"),
    ("MC202", "高分子材料", 3, "材料与化工", "高分子合成、结构与性能，常见高分子材料及其应用。"),
    ("AR101", "建筑设计基础", 4, "建筑学", "建筑空间、形式与功能，制图与模型表达，建筑设计入门。"),
    ("AR102", "中国建筑史", 3, "建筑学", "中国古代与近现代建筑演变、典型实例与建筑思想。"),
    ("AR201", "城市规划原理", 3, "建筑学", "城市空间结构、用地规划与总体规划方法。"),
    ("CS401", "软件工程", 3, "计算机科学与技术", "软件生命周期、需求分析、设计与测试方法，工程化软件开发实践。"),
    ("EE301", "通信原理", 3, "电子信息工程", "模拟与数字调制、信道与噪声、信息论基础。"),
    ("ME301", "制造技术基础", 3, "机械工程", "切削加工、铸造、锻压与 modern 制造工艺。"),
]

# 先修关系：(课程代码, 先修课代码) —— 仅高级课，入门课无先修，方便演示
PREREQS = [
    ("CS102", "CS101"),
    ("CS202", "CS102"),
    ("EE102", "EE101"),
    ("ME201", "ME102"),
    ("CE102", "CE101"),
]

# 教师研究方向（用于生成教师简介）
TOPICS = [
    "人工智能与机器学习", "大数据与分布式系统", "集成电路设计", "无线通信",
    "机械设计与机器人", "先进制造工艺", "结构工程与抗震", "岩土工程",
    "智能控制与优化", "电力系统自动化", "新能源材料", "化学工艺过程",
    "建筑设计及其理论", "城乡规划与遗产保护", "计算机视觉", "嵌入式系统",
    "微电子与半导体", "信号处理", "车辆工程", "工程力学",
]


def _hash_password(plain: str) -> str:
    from argon2 import PasswordHasher

    return PasswordHasher().hash(plain)


def _period_times() -> list[tuple[int, time, time]]:
    start = datetime(2000, 1, 1, 8, 0)
    slot = timedelta(minutes=45)
    gap = timedelta(minutes=10)
    out: list[tuple[int, time, time]] = []
    cur = start
    for i in range(PERIOD_COUNT):
        nxt = cur + slot
        out.append((i + 1, cur.time(), nxt.time()))
        cur = nxt + gap
    return out


# ---------- 幂等 / 重置 ----------
async def _already_seeded(session: AsyncSession) -> bool:
    res = await session.execute(select(Semester.id).where(Semester.is_current.is_(True)).limit(1))
    return res.first() is not None


async def _reset(session: AsyncSession) -> None:
    await session.execute(
        text(
            "TRUNCATE TABLE notifications, grades, submissions, assignments, enrollments, "
            "time_slots, sections, course_prerequisites, courses, period_defs, semesters, "
            "teachers, students, users RESTART IDENTITY CASCADE"
        )
    )
    await session.commit()


# ---------- 各实体播种 ----------
async def _seed_period_defs(session: AsyncSession) -> None:
    session.add_all(PeriodDef(period_no=n, start_time=s, end_time=e) for n, s, e in _period_times())
    await session.flush()


async def _seed_admin(session: AsyncSession, admin_hash: str) -> None:
    session.add(
        User(
            email=ADMIN_EMAIL,
            password_hash=admin_hash,
            role=UserRole.ADMIN,
            name="系统管理员",
            must_change_password=False,
        )
    )
    await session.flush()


async def _seed_teachers(session: AsyncSession, shared_hash: str) -> list[Teacher]:
    users: list[User] = []
    for i in range(TEACHER_COUNT):
        idx = i + 1
        dept = DEPARTMENTS[i % len(DEPARTMENTS)]
        title = TEACHER_TITLES[i % len(TEACHER_TITLES)]
        name = f"{['陈','林','黄','张','王','李','吴','刘','杨','周','赵','徐','孙','郑','许','何','郭','朱','胡','罗'][i % 20]}{['建华','志强','丽萍','文博','雅琴','国栋','晓东','慧敏','振华','雪梅','明辉','红梅','海燕','建国','春梅'][i % 15]}"
        topic = TOPICS[i % len(TOPICS)]
        bio = f"{name}，{title}，华侨大学工学院{dept}专业。主要研究方向为{topic}，长期从事本科教学，主讲多门专业核心课程，指导学生科创项目若干。"
        users.append(
            User(
                email=f"teacher{idx:04d}@seed.example.com",
                password_hash=shared_hash,
                role=UserRole.TEACHER,
                name=name,
                must_change_password=False,
                teacher=Teacher(
                    teacher_no=f"T{idx:04d}",
                    department=dept,
                    title=title,
                    bio=bio,
                ),
            )
        )
    session.add_all(users)
    await session.flush()
    return [u.teacher for u in users]  # type: ignore[list-item]


async def _seed_students(session: AsyncSession, shared_hash: str) -> None:
    surnames = "陈林黄张王李吴刘杨赵周徐孙马朱胡郭何高罗"
    given = ["伟","芳","娜","敏","静","杰","强","磊","洋","艳","勇","军","杰","娟","涛","明","超","秀英","霞","平"]
    batch: list[User] = []
    for i in range(STUDENT_COUNT):
        idx = i + 1
        batch.append(
            User(
                email=f"student{idx:04d}@seed.example.com",
                password_hash=shared_hash,
                role=UserRole.STUDENT,
                name=f"{surnames[i % len(surnames)]}{given[i % len(given)]}",
                must_change_password=False,
                student=Student(
                    student_no=f"S{idx:06d}",
                    grade=GRADES[i % len(GRADES)],
                    major=DEPARTMENTS[i % len(DEPARTMENTS)],
                ),
            )
        )
        if len(batch) >= BATCH_SIZE:
            session.add_all(batch)
            await session.flush()
            batch.clear()
    if batch:
        session.add_all(batch)
        await session.flush()


async def _seed_semester(session: AsyncSession) -> Semester:
    now = datetime.now(timezone.utc)
    semester = Semester(
        name="2025–2026 秋季学期",
        is_current=True,
        enroll_open_at=now - timedelta(days=1),
        enroll_close_at=now + timedelta(days=30),
        drop_deadline=now + timedelta(days=45),
        max_credits=30,
        max_courses=10,
    )
    session.add(semester)
    await session.flush()
    return semester


async def _seed_courses(session: AsyncSession) -> list[Course]:
    courses: list[Course] = []
    for code, title, credits, dept, desc in COURSES:
        courses.append(
            Course(code=code, title=title, credits=credits, description=desc, department=dept)
        )
    session.add_all(courses)
    await session.flush()
    return courses


async def _seed_prerequisites(session: AsyncSession, courses: list[Course]) -> None:
    by_code = {c.code: c for c in courses}
    for code, prereq in PREREQS:
        if code in by_code and prereq in by_code:
            session.add(
                CoursePrerequisite(
                    course_id=by_code[code].id, prereq_course_id=by_code[prereq].id
                )
            )
    await session.flush()


async def _seed_sections(
    session: AsyncSession, courses: list[Course], teachers: list[Teacher], semester: Semester
) -> list[Section]:
    sections: list[Section] = []
    sid = 0
    for ci, course in enumerate(courses):
        count = 2 if ci % 4 == 0 else 1  # 每四门有一门开 2 个班
        for _ in range(count):
            teacher = teachers[sid % len(teachers)]
            sections.append(
                Section(
                    course_id=course.id,
                    teacher_id=teacher.user_id,
                    semester_id=semester.id,
                    capacity=CAPACITY_TIERS[sid % len(CAPACITY_TIERS)],
                    seats_taken=0,
                    room=f"教学楼{(sid % 5) + 1}/{100 + sid}",
                )
            )
            sid += 1
    # 专门留一个 capacity=1 的班，供并发零超卖演示
    sections.append(
        Section(
            course_id=courses[0].id,
            teacher_id=teachers[0].user_id,
            semester_id=semester.id,
            capacity=1,
            seats_taken=0,
            room="教学楼1/1",
        )
    )
    session.add_all(sections)
    await session.flush()
    return sections


async def _seed_time_slots(session: AsyncSession, sections: list[Section]) -> None:
    slots: list[TimeSlot] = []
    for k, sec in enumerate(sections):
        day = (k % 5) + 1
        sp = (k % 10) + 1
        slots.append(
            TimeSlot(section_id=sec.id, day_of_week=day, start_period=sp, end_period=sp + 1)
        )
        if k % 2 == 0:
            slots.append(
                TimeSlot(
                    section_id=sec.id,
                    day_of_week=(day % 5) + 1,
                    start_period=((k + 3) % 10) + 1,
                    end_period=((k + 3) % 10) + 2,
                )
            )
    session.add_all(slots)
    await session.flush()


# ---------- 入口 ----------
async def main(reset: bool) -> None:
    async with AsyncSessionLocal() as session:
        if reset:
            await _reset(session)
        elif await _already_seeded(session):
            print("已存在当前学期，跳过播种。使用 --reset 强制重建。")
            return

        shared_hash = _hash_password(INITIAL_PASSWORD)
        admin_hash = _hash_password(ADMIN_PASSWORD)

        await _seed_period_defs(session)
        await _seed_admin(session, admin_hash)
        teachers = await _seed_teachers(session, shared_hash)
        await _seed_students(session, shared_hash)
        semester = await _seed_semester(session)
        courses = await _seed_courses(session)
        await _seed_prerequisites(session, courses)
        sections = await _seed_sections(session, courses, teachers, semester)
        await _seed_time_slots(session, sections)

        await session.commit()

    print("✅ 播种完成（华侨大学工学院数据）。")
    print(f"   ADMIN 登录：{ADMIN_EMAIL} / {ADMIN_PASSWORD}")
    print(f"   学生/教师 初始口令：{INITIAL_PASSWORD}（首登强制改密）")
    print(
        f"   专业数={len(DEPARTMENTS)}  教师数={TEACHER_COUNT}  学生数={STUDENT_COUNT}  "
        f"课程数={len(courses)}  教学班数={len(sections)}"
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="生成选课系统种子数据（华侨大学工学院）。")
    parser.add_argument(
        "--reset", action="store_true", help="清空全部表后重建（RESTART IDENTITY CASCADE）。"
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = _parse_args()
    asyncio.run(main(args.reset))
