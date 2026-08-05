// 课程性质（category）的展示顺序与配色。后端 enum 值即中文标签。
export const CATEGORY_ORDER = [
  "公共基础必修课",
  "通识教育课",
  "通识选修课",
  "专业必修课",
  "专业选修课",
] as const;

export type CategoryTone =
  | "teal"
  | "violet"
  | "orange"
  | "blue"
  | "green"
  | "default";

export const CATEGORY_TONE: Record<string, CategoryTone> = {
  公共基础必修课: "teal",
  通识教育课: "violet",
  通识选修课: "orange",
  专业必修课: "blue",
  专业选修课: "green",
};
