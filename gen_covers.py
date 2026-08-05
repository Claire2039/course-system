#!/usr/bin/env python3
"""生成课程封面 SVG（静态资源）。

用法： python gen_covers.py
输出： frontend/public/covers/<CODE>.svg
设计：按课程性质着色的渐变 + 装饰圆 + 课程代码 + 标题（自动换行）+ 分类药丸。
"""
from __future__ import annotations

import os
import textwrap

# (code, title) —— 与 seed_data.COURSES 一致
COURSES = [
    ("CS101", "计算机程序设计基础"), ("CS102", "数据结构"), ("CS201", "计算机组成原理"),
    ("CS202", "操作系统"), ("CS301", "数据库系统"), ("CS401", "软件工程"),
    ("EE101", "电路分析基础"), ("EE102", "模拟电子技术"), ("EE201", "数字电子技术"),
    ("EE202", "信号与系统"), ("EE301", "通信原理"),
    ("ME101", "工程制图"), ("ME102", "理论力学"), ("ME201", "机械设计基础"),
    ("ME202", "材料力学"), ("ME301", "制造技术基础"),
    ("CE101", "工程力学"), ("CE102", "结构力学"), ("CE201", "混凝土结构设计"),
    ("CE202", "测量学"),
    ("AU101", "自动控制原理"), ("AU102", "电机与拖动"), ("AU201", "电力电子技术"),
    ("MC101", "物理化学"), ("MC102", "材料科学基础"), ("MC201", "化工原理"),
    ("MC202", "高分子材料"),
    ("AR101", "建筑设计基础"), ("AR102", "中国建筑史"), ("AR201", "城市规划原理"),
    ("MAT101", "高等数学"), ("ENG101", "大学英语"), ("PED101", "体育"),
    ("POL101", "思想道德与法治"), ("CUL101", "中国传统文化"), ("ART101", "艺术鉴赏"),
    ("PSY201", "大学生心理健康"), ("CAR201", "大学生职业规划"),
]

# 分类 -> (浅色, 深色) 渐变 + 标签
CATEGORY = {
    "GENERAL_EDU": ("#8b5cf6", "#6d28d9", "通识教育课"),
    "PUBLIC_REQUIRED": ("#0d9488", "#0f766e", "公共基础必修课"),
    "MAJOR_REQUIRED": ("#2563eb", "#1e40af", "专业必修课"),
    "MAJOR_ELECTIVE": ("#16a34a", "#15803d", "专业选修课"),
    "GENERAL_ELECTIVE": ("#ea580c", "#c2410c", "通识选修课"),
}


def category_for(code: str) -> str:
    if code.startswith(("MAT", "ENG", "PED", "POL")):
        return "PUBLIC_REQUIRED"
    if code.startswith(("CUL", "ART")):
        return "GENERAL_EDU"
    if code.startswith(("PSY", "CAR")):
        return "GENERAL_ELECTIVE"
    num = int(code[-3:])
    return "MAJOR_REQUIRED" if num <= 102 else "MAJOR_ELECTIVE"


def wrap_title(title: str, width: int = 9) -> list[str]:
    # 中文按字符宽度换行
    lines = textwrap.wrap(title, width) or [title]
    return lines[:2]


FONT = "'PingFang SC','Microsoft YaHei','Hiragino Sans GB','Noto Sans CJK SC',sans-serif"

SVG = """<svg xmlns="http://www.w3.org/2000/svg" width="480" height="270" viewBox="0 0 480 270">
  <defs>
    <linearGradient id="g" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0" stop-color="{c1}"/>
      <stop offset="1" stop-color="{c2}"/>
    </linearGradient>
  </defs>
  <rect width="480" height="270" fill="url(#g)"/>
  <circle cx="410" cy="40" r="110" fill="white" opacity="0.07"/>
  <circle cx="450" cy="230" r="70" fill="white" opacity="0.06"/>
  <text x="36" y="96" font-family="{font}" font-size="58" font-weight="700" fill="white" letter-spacing="1">{code}</text>
  {title_lines}
  <g>
    <rect x="36" y="214" rx="12" ry="12" width="{pw}" height="28" fill="white" opacity="0.18"/>
    <text x="48" y="233" font-family="{font}" font-size="14" fill="white">{cat_label}</text>
  </g>
</svg>
"""


def title_svg(title: str) -> str:
    lines = wrap_title(title)
    parts = []
    y = 140
    for ln in lines:
        parts.append(
            f'<text x="36" y="{y}" font-family="{FONT}" font-size="24" '
            f'font-weight="600" fill="white">{ln}</text>'
        )
        y += 32
    return "\n  ".join(parts)


def main() -> None:
    out_dir = os.path.join("frontend", "public", "covers")
    os.makedirs(out_dir, exist_ok=True)
    for code, title in COURSES:
        c1, c2, label = CATEGORY[category_for(code)]
        pw = 24 + len(label) * 15  # 药丸宽度估算（中文字符约 15px）
        svg = SVG.format(
            c1=c1, c2=c2, code=code, font=FONT, cat_label=label,
            pw=pw, title_lines=title_svg(title),
        )
        with open(os.path.join(out_dir, f"{code}.svg"), "w", encoding="utf-8") as f:
            f.write(svg)
    print(f"generated {len(COURSES)} covers in {out_dir}")


if __name__ == "__main__":
    main()
