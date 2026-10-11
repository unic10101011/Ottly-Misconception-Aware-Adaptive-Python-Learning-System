# 部署手册 (Deployment Guide)

## 1. 后端部署 (Backend Deployment)

### 环境要求
- Node.js 18.x +
- MySQL 8.0 +

### 步骤
1. 进入 backend 目录: `cd backend`
2. 安装依赖: `npm install`
3. 配置环境: 复制 `.env` 并填写正确的数据库连接信息与密钥。
4. 初始化数据库: 执行 `database/schema.sql` 中的 SQL 语句。
5. 启动服务:
   - 开发模式: `npm run dev`
   - 生产模式: `npm start`
6. 访问 API 文档: `http://localhost:3000/api-docs`

---

## 2. 前端部署 (Frontend Deployment)

### 环境要求
- React Native 开发环境 (Android SDK / Xcode)
- Node.js 18.x +

### 步骤
1. 进入 frontend 目录: `cd frontend`
2. 安装依赖: `npm install`
3. 链接原生库 (如果需要): `npx react-native link` (React Native 0.60+ 通常自动链接)
4. iOS 特定步骤: `cd ios && pod install && cd ..`
5. 运行应用:
   - Android: `npm run android`
   - iOS: `npm run ios`

---

## 3. 安全与性能注意事项
- 生产环境务必将 `NODE_ENV` 设置为 `production`。
- 替换 `.env` 中的 `JWT_SECRET` 和 `REFRESH_TOKEN_SECRET` 为高强度随机字符串。
- 接口建议全部走 HTTPS 协议。
- 开启 Redis 缓存以进一步优化 `/version` 等高频接口的性能。
