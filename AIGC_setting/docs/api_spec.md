# API 规范与接口说明 (API Spec)

## 1. 通用响应格式
```json
{
  "code": 200,
  "message": "success",
  "data": { ... }
}
```

## 2. 核心接口说明 (Core APIs)

### 2.1 账号与安全 (Account & Security)
- `POST /api/v1/user/bind`: 绑定手机/邮箱。
  - 参数: `target`, `code`, `password`, `type` (bind/unbind)。
  - 安全: 支持接口幂等 (X-Idempotency-Key), 防重放 (X-Timestamp + X-Nonce)。
- `POST /api/v1/user/change-password`: 修改密码。
  - 安全: 修改后强制全端 AccessToken 失效。
- `GET /api/v1/user/devices`: 获取最近登录设备列表。
- `POST /api/v1/user/logout-device`: 远程登出指定设备。

### 2.2 通知设置 (Notifications)
- `GET /api/v1/notification/preference`: 获取用户通知偏好。
- `PUT /api/v1/notification/preference`: 更新通知偏好。
  - 说明: 即时同步推送网关。

### 2.3 关于我们 (About Us)
- `GET /api/v1/version`: 检查更新。
  - 响应: `latest_version`, `is_force_update`, `grayscale_ratio`, `update_log`, `download_url`。
  - 性能: 99th 延迟 ≤ 100 ms。

---

## 3. 安全策略 (Security Policies)
- **鉴权**: JWT Bearer Token。
- **加密**: 密码 bcrypt(12) 加密。
- **冷却**: 验证码失败 3 次触发 60 s 冷却。
- **过期**: 验证码有效期 5 min。
- **幂等**: 使用 `X-Idempotency-Key` 保证接口幂等。
