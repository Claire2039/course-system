/** 全站页脚：版权信息与作者联系方式。 */
export function Footer() {
  const year = new Date().getFullYear();
  return (
    <footer className="border-t bg-card">
      <div className="mx-auto flex max-w-6xl flex-col items-center gap-1 px-6 py-4 text-center text-xs text-muted-foreground sm:flex-row sm:justify-between sm:text-left">
        <p>
          © {year} 选课系统 · 保留所有权利
        </p>
        <p className="flex items-center gap-1.5">
          <span className="font-medium text-foreground">Claire</span>
          <span aria-hidden>·</span>
          <a
            href="mailto:496839381@qq.com"
            className="transition-colors hover:text-foreground hover:underline"
          >
            496839381@qq.com
          </a>
        </p>
      </div>
    </footer>
  );
}
