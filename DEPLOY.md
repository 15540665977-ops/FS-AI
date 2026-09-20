# 线上部署指南

## 公开访问地址

应用可通过 GitHub Pages 对外访问：

**https://amyfxm0616.github.io/auto-parts-learning/#/**

应用使用 Hash 路由，因此页面地址会带有 `#/`；可直接分享首页链接，或分享某个功能页面的完整链接，例如：

- `https://amyfxm0616.github.io/auto-parts-learning/#/parts`
- `https://amyfxm0616.github.io/auto-parts-learning/#/materials`
- `https://amyfxm0616.github.io/auto-parts-learning/#/quiz`

## 自动发布

项目已配置 GitHub Actions 工作流：`.github/workflows/deploy.yml`。

每次将代码推送到 `main` 分支后，工作流会自动：

1. 安装 Node.js 22 和项目依赖；
2. 构建 Vite 静态站点；
3. 将构建产物 `dist/` 发布到 `gh-pages` 分支；
4. 由 GitHub Pages 提供公开访问。

本地更新并发布的常用命令：

```powershell
cd C:\Users\fushuang\auto-parts-learning
npm run build
git add <修改的文件>
git commit -m "feat: 更新学习平台"
git push origin main
```

推送后可在仓库的 **Actions** 页面查看发布进度。通常在工作流成功后几分钟内，线上站点便会更新。

## 首次启用 GitHub Pages（如尚未启用）

1. 打开仓库：<https://github.com/Amyfxm0616/auto-parts-learning>。
2. 进入 **Settings → Pages**。
3. 在 **Build and deployment** 中选择 **Deploy from a branch**。
4. 选择分支 `gh-pages`，目录选择 `/(root)`，然后保存。
5. GitHub 会显示站点访问地址；等待首次部署完成后即可对外分享。

## 数据与权限说明

- 网站是公开静态站点：题库、图片和随构建发布的学习内容可被所有访问者读取。
- 笔记、答题进度和主题偏好通过浏览器 `localStorage` 保存；每位访问者的数据只保留在自己的浏览器中，不会同步到服务器或其他设备。
- 不要将账号口令、个人数据、私密题目或 API 密钥提交到此公开仓库。
- 如果以后需要多人共享笔记、云端题库管理、登录或私有数据，需要另行部署带认证和数据库的后端服务。

## 本地开发

```powershell
npm install
npm run dev
```

开发服务器默认运行在 <http://localhost:5173/#/>；这是仅限本机（或局域网）的开发地址，不能替代线上公开链接。
