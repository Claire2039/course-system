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
from decimal import Decimal

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import AsyncSessionLocal
from app.models import (  # noqa: F401  导入即注册模型
    Assignment,
    Course,
    CoursePrerequisite,
    Enrollment,
    Grade,
    PeriodDef,
    Section,
    Semester,
    Student,
    Submission,
    Teacher,
    TimeSlot,
    User,
)
from app.models.constants import (
    CourseCategory,
    EnrollmentStatus,
    SubmissionStatus,
    UserRole,
)

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
    # 公共基础必修课
    ("MAT101", "高等数学", 5, "公共基础", "极限、连续、一元与多元微积分、级数与常微分方程，工科最重要的数学基础。"),
    ("ENG101", "大学英语", 4, "公共基础", "听说读写译综合训练，培养学术英语交流与跨文化沟通能力。"),
    ("PED101", "体育", 2, "公共基础", "体质测评与多项运动技能训练，养成终身锻炼习惯。"),
    ("POL101", "思想道德与法治", 3, "公共基础", "人生观、价值观与法治素养教育，思想政治理论核心课程。"),
    # 通识教育课
    ("CUL101", "中国传统文化", 2, "通识教育", "儒道思想、传统艺术与民俗，理解中华文化的精神内核与当代价值。"),
    ("ART101", "艺术鉴赏", 2, "通识教育", "音乐、美术、戏剧作品的欣赏方法与审美体验。"),
    # 通识选修课
    ("PSY201", "大学生心理健康", 2, "通识教育", "自我认知、情绪管理与人际交往，促进心理健康发展。"),
    ("CAR201", "大学生职业规划", 1, "通识教育", "专业认知、职业探索与生涯决策，规划大学与未来发展。"),
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

UNIVERSITIES = [
    "华侨大学",
    "厦门大学",
    "清华大学",
    "浙江大学",
    "上海交通大学",
    "复旦大学",
    "北京大学",
    "华中科技大学",
]
VENUES = [
    "计算机学报",
    "电子学报",
    "机械工程学报",
    "土木工程学报",
    "中国科学",
    "高等教育研究",
]
SYLLABUS_TEMPLATE = [
    "导论：课程研究对象与学习方法",
    "基本概念与基本原理",
    "核心理论（一）",
    "核心理论（二）",
    "典型方法与计算",
    "应用与案例分析",
    "进阶专题（一）",
    "进阶专题（二）",
    "实验与实践环节",
    "综合大作业与讨论",
    "复习与期末考查",
]


def _category_for(code: str) -> CourseCategory:
    """按课程代码推断课程性质。"""
    if code.startswith(("MAT", "ENG", "PED", "POL")):
        return CourseCategory.PUBLIC_REQUIRED
    if code.startswith(("CUL", "ART")):
        return CourseCategory.GENERAL_EDU
    if code.startswith(("PSY", "CAR")):
        return CourseCategory.GENERAL_ELECTIVE
    num = int(code[-3:])
    return CourseCategory.MAJOR_REQUIRED if num <= 102 else CourseCategory.MAJOR_ELECTIVE


def _syllabus_for(title: str) -> list[dict]:
    topics = list(SYLLABUS_TEMPLATE)
    topics[0] = f"导论：{title}概述"
    return [{"week": i + 1, "title": t, "detail": None} for i, t in enumerate(topics)]


def _education_for(i: int) -> list[dict]:
    u = UNIVERSITIES[i % len(UNIVERSITIES)]
    base = 2000 + (i % 12)
    return [
        {"degree": "博士", "institution": u, "year": base + 6},
        {"degree": "硕士", "institution": u, "year": base + 3},
        {"degree": "本科", "institution": u, "year": base},
    ]


def _publications_for(i: int) -> list[dict]:
    topic = TOPICS[i % len(TOPICS)]
    y = 2018 + (i % 7)
    return [
        {"title": f"基于{topic}的关键技术研究", "venue": VENUES[i % len(VENUES)], "year": y},
        {
            "title": f"{topic}在本科教学中的应用实践",
            "venue": VENUES[(i + 1) % len(VENUES)],
            "year": y + 1,
        },
        {
            "title": f"{topic}发展前沿综述",
            "venue": VENUES[(i + 2) % len(VENUES)],
            "year": y + 2,
        },
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
                    research_interests=topic,
                    education=_education_for(i),
                    publications=_publications_for(i),
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
            Course(
                code=code,
                title=title,
                credits=credits,
                description=desc,
                department=dept,
                category=_category_for(code),
                syllabus=_syllabus_for(title),
                cover_url=f"/covers/{code}.svg",
            )
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


async def _seed_enrollments(
    session: AsyncSession, sections: list[Section]
) -> tuple[list[Section], list[int]]:
    """给前若干演示学生选几门课，便于登录后直接看到课表内容。

    直接插入 Enrollment 行并同步 seats_taken（绕过运行时选课服务/Redis）。
    只用容量充裕的教学班，跳过末尾 capacity=1 的超卖演示班。
    """
    pool = [s for s in sections if s.capacity > 1]
    if len(pool) < 5:
        return
    # 取 5 门不同课程的教学班，避免同一学生选到同课的不同班
    seen_courses: set[int] = set()
    chosen: list[Section] = []
    for s in pool:
        if s.course_id not in seen_courses:
            seen_courses.add(s.course_id)
            chosen.append(s)
        if len(chosen) == 5:
            break
    if len(chosen) < 5:
        return
    demo_student_ids = list(range(22, 22 + 5))  # student0001..student0005
    seats: dict[int, int] = {s.id: 0 for s in chosen}
    rows: list[Enrollment] = []
    for i, uid in enumerate(demo_student_ids):
        # 每个学生循环选 3 个班（步长 1，保证同一学生不重复）
        for j in range(3):
            sec = chosen[(i + j) % len(chosen)]
            rows.append(
                Enrollment(
                    student_id=uid,
                    section_id=sec.id,
                    status=EnrollmentStatus.ENROLLED,
                    waitlist_position=None,
                )
            )
            seats[sec.id] += 1
    session.add_all(rows)
    for s in chosen:
        s.seats_taken = seats[s.id]
    await session.flush()
    return chosen, demo_student_ids


async def _seed_assignments(
    session: AsyncSession, sections: list[Section], student_ids: list[int]
) -> None:
    """为演示教学班布置作业，并给演示学生生成提交与部分成绩，便于展示作业/批改流程。"""
    now = datetime.now(timezone.utc)
    assigns: list[Assignment] = []
    for i, sec in enumerate(sections):
        assigns.append(
            Assignment(
                section_id=sec.id,
                title=f"第{i + 1}次作业",
                description="请结合课程内容独立完成，论述需严谨、格式规范。",
                due_at=now + timedelta(days=7 + i),
                late_deadline=now + timedelta(days=10 + i) if i % 2 == 0 else None,
                allow_late=(i % 2 == 0),
            )
        )
    session.add_all(assigns)
    await session.flush()
    sec_to_assign = {sec.id: a for sec, a in zip(sections, assigns)}

    # 每个演示学生对所在班的作业各提交一次（约留 1/4 不交，呈现"未提交"）
    subs: list[Submission] = []
    sub_teacher: list[int] = []  # 与 subs 对齐：该班教师 user_id，用作出分人
    for i, uid in enumerate(student_ids):
        for j in range(3):
            if (i + j) % 4 == 0:
                continue
            sec = sections[(i + j) % len(sections)]
            a = sec_to_assign[sec.id]
            subs.append(
                Submission(
                    assignment_id=a.id,
                    student_id=uid,
                    file_key=None,
                    text_comment=f"{a.title}已完成，附思路说明。",
                    status=SubmissionStatus.SUBMITTED,
                )
            )
            sub_teacher.append(sec.teacher_id)
    session.add_all(subs)
    await session.flush()

    # 约一半给出成绩
    grades: list[Grade] = []
    for idx, sub in enumerate(subs):
        if idx % 2 != 0:
            continue
        grades.append(
            Grade(
                submission_id=sub.id,
                score=Decimal(80) + Decimal((idx * 13) % 20),
                feedback="整体完成较好，注意论述严谨性与格式规范。",
                graded_by=sub_teacher[idx],
            )
        )
    session.add_all(grades)
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
        demo_sections, demo_students = await _seed_enrollments(session, sections)
        await _seed_assignments(session, demo_sections, demo_students)

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
