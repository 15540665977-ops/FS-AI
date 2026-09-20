# 谱图智能分析系统

FTIR、DSC、TGA 谱图的 AI 辅助分析应用。项目现在同时提供：

- **Windows/局域网模式**：适合内部试用；
- **Docker 公网生产模式**：使用自有 Linux 服务器、域名、HTTPS 与登录账户，供授权成员通过链接访问。

> 上传谱图、案例报告、标准谱图和 AI 分析可能包含内部资料。公网部署前务必遵守公司数据安全、供应商保密和跨境数据政策。**不要将 API 密钥、生产 `.env`、`data/` 或上传内容提交至 Git。**

## 功能与权限

线上模式默认需要登录：

| 角色 | 权限 |
| --- | --- |
| 普通用户 | 使用分析、知识库、交叉对比；读取共享案例与标准库 |
| 管理员 | 以上全部权限；创建、停用、重置用户；录入、编辑和删除标准谱图库 |

案例和标准谱图库为全员共享数据。系统记录新案例和标准库记录的实际创建用户名。

## GitHub Pages 在线预览

前端可发布至 GitHub Pages，使用仓库 `15540665977-ops/FS-AI` 后，预览入口为：

```text
https://15540665977-ops.github.io/FS-AI/
```

GitHub Pages **只能承载静态前端**，不能运行 FastAPI、保存上传谱图、保存用户数据或持有 Claude API 密钥。因此，该链接以“发布预览”模式打开，明确提示登录、上传和 AI 分析不可用；它不会把文件或密钥发送给 GitHub。

### 发布前端到 GitHub Pages

1. 将此项目安全推送到仓库 `15540665977-ops/FS-AI` 的 `main` 分支；确认 `.env`、`.env.production`、`backend/uploads/`、数据库和 `data/` 未被提交。
2. GitHub 仓库中依次进入 **Settings → Pages → Build and deployment**，选择 **GitHub Actions**。
3. 推送 `main` 后，`.github/workflows/deploy-pages.yml` 会构建并发布前端。首次部署通常需要数分钟。
4. 在 **Actions** 中确认 `Deploy GitHub Pages` 成功后，访问上述 URL。

本地可模拟 Pages 构建：

```powershell
cd D:\spectral_analysis_system\frontend
$env:VITE_BASE_PATH = '/FS-AI/'
$env:VITE_API_BASE_URL = ''
npm run build -- --mode github-pages
```

### 后端上线后接通完整功能

将 Docker 后端部署至独立 HTTPS 域名后（例如 `https://api.spectra.example.com`）：

1. 在后端 `.env.production` 设置：

   ```dotenv
   CORS_ALLOW_ORIGINS=https://15540665977-ops.github.io
   SESSION_COOKIE_SAME_SITE=none
   SESSION_COOKIE_SECURE=true
   ```

2. 在 GitHub 仓库的 **Settings → Secrets and variables → Actions → Variables** 新建：

   ```text
   VITE_API_BASE_URL=https://api.spectra.example.com
   ```

3. 重新运行 `Deploy GitHub Pages` workflow 或向 `main` 推送一次。此变量只包含公开 API 地址；**不要**把 API 密钥、用户密码或会话密钥放入 GitHub Variables/Pages。

前端会通过 HTTPS 跨域 Cookie 调用后端。生产后端仍必须在服务器 `.env.production` 中保存 `ANTHROPIC_API_KEY`、`SESSION_SECRET` 和初始管理员凭据。

## 本地 Windows / 局域网运行

### 环境要求

- Windows 10/11
- Python **3.10 或 3.11**（推荐）
- Node.js **18+**（推荐 20 LTS）

### 首次安装

```powershell
cd D:\spectral_analysis_system\backend
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
Copy-Item .env.example .env

cd ..\frontend
npm ci
```

编辑 `backend/.env`，至少填写：

```dotenv
ANTHROPIC_API_KEY=你的_Claude_API_密钥
SESSION_SECRET=本地开发也建议使用的长随机值
INITIAL_ADMIN_USERNAME=admin
INITIAL_ADMIN_PASSWORD=至少10位的初始管理员密码
```

> 初始管理员只会在 `users` 表为空时创建一次。之后改动 `INITIAL_ADMIN_*` 不会修改已有账户；使用网页“用户管理”创建或重置用户。

### 启动和局域网访问

双击项目根目录 `启动系统.bat`，或分别启动 `backend\start-backend-lan.bat` 与 `frontend\start-frontend-lan.bat`。

局域网用户访问：

```text
http://<运行电脑的IPv4地址>:5173
```

首次使用请以配置的初始管理员账号登录。管理员随后可在地址栏访问 `/admin/users` 管理成员账户。

Windows 防火墙应只在受信任网络放行 TCP `5173`。不要将 Windows 开发服务器或端口 `8000` 直接暴露到互联网。

## 公网生产部署（Docker + Caddy HTTPS）

### 架构

```text
浏览器 → HTTPS 域名 → Caddy（自动 TLS / 静态前端 / 反向代理）
                              └→ FastAPI（认证 / AI / SQLite / 上传 / ChromaDB）
```

Docker Compose 只向公网暴露 `80` 和 `443`；后端端口 `8000` 仅在 Docker 内网可见。所有生产数据持久化在服务器项目目录的 `data/`：数据库、上传文件与 ChromaDB 都需要纳入备份。

### 服务器前置条件

1. 一台受支持 Linux 云主机或服务器（推荐 Ubuntu 22.04/24.04），至少 **2 vCPU、4 GB RAM、30 GB SSD**；高并发或大量谱图建议提高配置。
2. 安装 Docker Engine 和 Docker Compose Plugin。
3. 已购买/管理域名，并将该域名的 `A` 记录（以及如有 IPv6 的 `AAAA`）指向服务器公网 IP。
4. 云安全组和服务器防火墙仅对公网放行 TCP `80`、`443`、`22`（SSH 限制为管理员来源更佳）；**不要**放行 `8000`。
5. 服务器能够访问 Claude API；如启用联网搜索，还需访问 Tavily。

### 部署步骤

在服务器上取得源码（私有 Git 仓库或安全拷贝），进入项目根目录：

```bash
cp .env.production.example .env.production
chmod 600 .env.production
```

编辑 `.env.production`，必须填写：

```dotenv
DOMAIN=spectra.example.com
ACME_EMAIL=ops@example.com
ANTHROPIC_API_KEY=真实密钥
SESSION_SECRET=至少48字符的随机值
INITIAL_ADMIN_USERNAME=admin
INITIAL_ADMIN_PASSWORD=至少10字符的强密码
```

生成随机会话密钥：

```bash
python3 -c 'import secrets; print(secrets.token_urlsafe(48))'
```

启动服务：

```bash
docker compose up -d --build
docker compose ps
docker compose logs -f backend caddy
```

DNS 已生效且 80/443 可达时，Caddy 会自动申请并续期 HTTPS 证书。访问：

```text
https://你的域名
```

使用 `INITIAL_ADMIN_USERNAME` / `INITIAL_ADMIN_PASSWORD` 首次登录。登录后立即通过 `https://你的域名/admin/users` 创建日常管理员和普通成员账号；妥善保管初始密码。

### 维护命令

```bash
# 查看服务和日志
docker compose ps
docker compose logs -f backend caddy

# 更新代码后的重建与滚动重启
git pull
docker compose up -d --build

# 停止服务（保留数据）
docker compose down

# 创建数据备份（建议在低峰期或先停止后端）
tar -czf spectral-data-$(date +%F).tar.gz data/
```

**不要**运行 `docker compose down -v`，否则会删除 Caddy 证书卷；也不要删除 `data/`，其中包含业务数据。

### 生产安全核对

- [ ] 域名 DNS 指向正确服务器，HTTPS 证书有效。
- [ ] `.env.production` 权限为 `600`，不在 Git 中。
- [ ] `SESSION_SECRET` 是唯一且强随机值。
- [ ] `INITIAL_ADMIN_PASSWORD` 为唯一强密码，并已创建替代管理员。
- [ ] 公网只开放 80/443；Docker 不公开 8000。
- [ ] `data/` 有加密、受控访问且定期验证可恢复的备份。
- [ ] 仅授予需要人员账号，并在人员变动时停用账户。

## 环境变量

| 变量 | 生产环境 | 说明 |
| --- | --- | --- |
| `ANTHROPIC_API_KEY` | 必填 | AI 分析调用密钥 |
| `TAVILY_API_KEY` | 可选 | 联网技术资料检索 |
| `SESSION_SECRET` | 必填 | Cookie 会话签名密钥 |
| `INITIAL_ADMIN_USERNAME` / `INITIAL_ADMIN_PASSWORD` | 首次启动必填 | 空用户库的初始管理员 |
| `MAX_UPLOAD_BYTES` | 可选 | 单文件上传上限，默认 20 MiB |
| `MAX_UPLOAD_FILES` | 可选 | 单请求文件数上限，默认 10 |
| `SPECTRAL_DATA_DIR` | Docker 已设置 | 数据根目录，Docker 为 `/data` |
| `SPECTRAL_DATABASE_URL` | 可选 | 显式覆盖 SQLite 连接 URL |

## 验证

```powershell
cd D:\spectral_analysis_system\backend
.\.venv\Scripts\python.exe -m pytest tests -q

cd ..\frontend
npm run build
```

Docker 环境可再执行：

```bash
docker compose config
docker compose up -d --build
curl -fsS http://127.0.0.1/healthz
```

## 登录后启动（Windows）

仅 Windows 内网试用时，可为当前用户配置登录后后台启动：

```powershell
cd D:\spectral_analysis_system
powershell -NoProfile -ExecutionPolicy Bypass -File .\configure-login-autostart.ps1
```

移除：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\remove-login-autostart.ps1
```

该功能不会替代生产服务器部署，且不会自动打开浏览器。
