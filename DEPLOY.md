# 部署到阿里云（公网 IP / HTTP）

目标：把整套系统部署到你的阿里云服务器，得到一个**公网链接**（`http://你的公网IP`），发给别人，对方用浏览器直接用，**不用装任何东西**。

本文按 **2GB 内存、公网 IP（HTTP，无域名）** 编写。命令在服务器终端里执行。

---

## 0. 你会得到什么

一条命令 `docker compose up -d --build` 把 6 个服务（数据库/缓存/对象存储/后端/前端/反代）全拉起；再跑两条命令建表+播种；浏览器打开 `http://公网IP` 即可登录使用。

---

## 1. 阿里云控制台：开放端口 + 记下公网 IP

1. **公网 IP**：控制台 → 云服务器 ECS → 找到你的实例 → 记下「公网 IP」。
2. **安全组**（**最常见的坑**：不做这步网页打不开）：实例详情 → 安全组 → 配置规则 → 入方向，**放行 TCP 80 端口**（来源 `0.0.0.0/0`）。SSH 的 22 一般默认已开。
   - **不要**放行 9001（MinIO 控制台）——它仅作内部/调试，不对外。
3. （可选）查操作系统：实例详情里看「镜像」，或登录后执行 `cat /etc/os-release`。

> 国内服务器用**公网 IP 走 HTTP** 通常无需 ICP 备案；以后想要域名+HTTPS 再补备案。

---

## 2. 登录服务器

在你**本地电脑**（Windows 用 PowerShell/Git Bash，Mac 用终端）：
```bash
ssh root@你的公网IP
```
输入实例密码（控制台可重置）。进去后你就在服务器上了。

---

## 3. 安装 Docker（含国内加速）

一行命令（自动适配 Ubuntu / CentOS / Alibaba Cloud Linux）：
```bash
curl -fsSL https://get.docker.com | bash -s docker --mirror Aliyun
```
把自己加进 docker 组（免得每次 sudo），然后**重新登录一次** SSH：
```bash
usermod -aG docker $USER
exit
# 重新 ssh root@你的公网IP
docker --version && docker compose version   # 看到版本号即成功
```

**配置镜像加速**（国内拉镜像更快，强烈建议）：去 [阿里云容器镜像服务 → 加速器](https://cr.console.aliyun.com/cn-hangzhou/instances/mirrors) 拿你的专属加速地址，然后：
```bash
mkdir -p /etc/docker
tee /etc/docker/daemon.json <<EOF
{ "registry-mirrors": ["https://你拿到的专属地址.mirror.aliyuncs.com"] }
EOF
systemctl daemon-reload && systemctl restart docker
```

---

## 4. 加 swap（2GB 内存必备）

前端构建（`next build`）较吃内存，2GB 容易爆。加 2GB 虚拟内存：
```bash
fallocate -l 2G /swapfile && chmod 600 /swapfile && mkswap /swapfile && swapon /swapfile
echo '/swapfile none swap sw 0 0' >> /etc/fstab   # 重启后仍生效
free -h   # 看到 Swap 一行有约 2G 即成功
```

---

## 5. 把代码放到服务器

服务器上装 git 并克隆（如果有 GitHub 仓库）；或在你**本地**把项目文件夹用 `scp` 传上去。最简单——本地打包上传：
```bash
# 本地执行（PowerShell/Git Bash），把项目传到服务器：
scp -r 选课系统 root@你的公网IP:/root/course-system
```
（若用 Git：`git clone <你的仓库>` 到 `/root/course-system`。）

服务器上进入项目目录：
```bash
cd /root/course-system
```

---

## 6. 配置 `.env`（改密码 + 生成会话密钥）

```bash
cp .env.example .env
# 生成一个随机会话密钥，写进 .env 的 SESSION_SECRET
SECRET=$(openssl rand -hex 32) && sed -i "s/^SESSION_SECRET=.*/SESSION_SECRET=$SECRET/" .env
# 把数据库等默认密码改成你自己的（至少别用 change_me_in_prod）
sed -i 's/change_me_in_prod/你的强密码A/g' .env
sed -i 's/please_generate_a_long_random_string/已上面替换/' .env
cat .env   # 检查：SITE_ADDRESS=:80（HTTP，公网IP正好）、密码已改、SESSION_SECRET 已填
```
> `SITE_ADDRESS=:80` 保持不变 —— Caddy 据此走 HTTP（公网 IP 不需要域名/HTTPS）。

---

## 7. 构建并启动（核心一步）

```bash
docker compose up -d --build
```
首次会下载/构建镜像（几分钟～十几分钟）。完成后看状态，等都是 healthy：
```bash
docker compose ps
```
> 若卡在拉镜像/`npm install` 很慢：见文末「常见问题」配 npm 镜像。

---

## 8. 建表 + 播种数据

```bash
docker compose exec api alembic upgrade head          # 创建所有表
docker compose exec api python -m scripts.seed_data   # 生成演示数据（2000学生/30课程/…）
```
播种完会打印演示账号：
- 管理员：`admin@seed.example.com` / `Admin#2026`
- 学生/教师初始口令：`InitPass#2026`（首登强制改密）

---

## 9. 访问 & 分享

浏览器打开：
```
http://你的公网IP
```
用上面的管理员账号登录 → 进入系统。**把这个链接发给别人**，对方用浏览器打开即可（无需安装）。给学生账号让他们体验选课。

> 想验证"实时"：开两个浏览器分别登录两个学生，同时抢同一个教学班 → 另一边座位数实时变化（SSE）。

---

## 10. 常用维护

```bash
docker compose logs -f api          # 看后端日志
docker compose logs -f web          # 看前端日志
docker compose restart api          # 重启某服务
docker compose down                 # 停掉全部（数据卷保留）
docker compose up -d --build        # 改完代码后重新构建上线
docker compose exec api python -m scripts.seed_data --reset   # 清空并重新播种
```
代码更新：在服务器 `git pull`（或重新 scp）后，再 `docker compose up -d --build`。

---

## 11. 压测演示（可选，演示防超卖）

在**本机**（能访问到服务器 API）跑 locust，模拟大量学生抢某个教学班：
```bash
pip install locust
# 找一个 capacity 较小的教学班 id（管理员页面可见），比如 id=1：
locust -f loadtest/locustfile.py --host http://你的公网IP --headless -u 500 -r 50 -t 1m
```
随后查该班的已选数：
```bash
docker compose exec db psql -U course -d coursedb -c "select id,capacity,seats_taken from sections where id=1;"
```
能看到 `seats_taken` 始终 ≤ `capacity`（**零超卖**），其余学生进入候补。

---

## 常见问题

- **网页打不开（超时）**：99% 是安全组没放行 80 端口（第 1 步）。
- **`docker compose up` 卡住/拉镜像很慢**：没配镜像加速（第 3 步），或镜像加速地址不对。
- **前端构建失败/被 kill（内存）**：swap 没加成功（第 4 步）；或加到 3–4G。
- **`npm install` 很慢（构建 web 阶段）**：在 `frontend/Dockerfile` 里加一行 `ENV npm_config_registry=https://registry.npmmirror.com` 后重新构建。
- **登录提示会话问题**：确认 Redis 容器 healthy（`docker compose ps`）。
- **想换数据/重置**：`docker compose exec api python -m scripts.seed_data --reset`。
