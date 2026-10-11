(function () {
  var DB_KEY = 'browser_settings_demo_db_v1';
  var REQUEST_TTL = 5 * 60 * 1000;
  var PASSWORD_REGEX = /^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)(?=.*[^A-Za-z\d]).{8,32}$/;

  function now() {
    return Date.now();
  }

  function roundMb(value) {
    return Number(value).toFixed(2);
  }

  function uid(prefix) {
    return prefix + '_' + Math.random().toString(36).slice(2, 10) + '_' + now().toString(36);
  }

  function deepClone(value) {
    return JSON.parse(JSON.stringify(value));
  }

  function buildDocument(title, locale) {
    if (title === 'user_agreement') {
      return locale === 'en-US'
        ? '<h1>User Agreement</h1><p>This browser edition stores data locally for demonstration only.</p><h2>Service Scope</h2><p>The settings center supports account security, notifications, cache cleanup, theme, language, and version management.</p><h2>User Obligations</h2><p>Please keep your current password and local device secure.</p>'
        : '<h1>用户协议</h1><p>当前浏览器版仅在本地保存数据，用于演示设置系统完整功能。</p><h2>服务范围</h2><p>设置中心支持账号安全、通知、缓存清理、主题、语言与版本管理。</p><h2>用户义务</h2><p>请妥善保管当前密码和本地设备。</p>';
    }

    return locale === 'en-US'
      ? '<h1>Privacy Policy</h1><p>This demo stores preferences in browser localStorage only.</p><h2>Collected Data</h2><p>Phone, email, login devices, and notification preferences remain on your local machine.</p><h2>Offline Cache</h2><p>Legal documents can be cached for offline viewing and cleared at any time.</p>'
      : '<h1>隐私政策</h1><p>当前演示仅使用浏览器 localStorage 保存偏好信息。</p><h2>收集范围</h2><p>手机号、邮箱、登录设备和通知偏好均仅保留在本机。</p><h2>离线缓存</h2><p>协议文档支持离线缓存，并可随时手动清除。</p>';
  }

  function createInitialDb() {
    return {
      users: [
        {
          id: 1,
          username: 'demo_user',
          password: 'Demo@1234',
          phone: '13800138000',
          email: 'demo@example.com',
          themePreference: localStorage.getItem('theme_preference') || 'system',
          langPreference: localStorage.getItem('lang_preference') || 'zh-CN'
        }
      ],
      notificationPrefs: {
        1: {
          pushEnabled: true,
          systemEnabled: true,
          activityEnabled: true,
          aiReplyEnabled: true,
          version: 1,
          gatewayStatus: 'ready',
          lastSyncAt: now()
        }
      },
      loginDevices: [
        {
          id: uid('device'),
          userId: 1,
          deviceName: 'Chrome on Windows',
          systemVersion: 'Windows 11 / Chrome',
          ipAddress: '192.168.1.18',
          lastActiveAt: now() - 30 * 60 * 1000,
          refreshToken: uid('refresh'),
          active: true
        },
        {
          id: uid('device'),
          userId: 1,
          deviceName: 'Safari on iPhone',
          systemVersion: 'iOS 17 / Safari',
          ipAddress: '10.0.0.23',
          lastActiveAt: now() - 6 * 60 * 60 * 1000,
          refreshToken: uid('refresh'),
          active: true
        },
        {
          id: uid('device'),
          userId: 1,
          deviceName: 'Edge on macOS',
          systemVersion: 'macOS 14 / Edge',
          ipAddress: '172.16.8.9',
          lastActiveAt: now() - 26 * 60 * 60 * 1000,
          refreshToken: uid('refresh'),
          active: true
        }
      ],
      appVersions: [
        {
          id: uid('ver'),
          versionCode: 1,
          versionName: '1.0.0',
          platform: 'web',
          updateLog: 'Initial browser release.',
          forceUpdate: false,
          grayRatio: 100,
          downloadUrl: './index.html'
        },
        {
          id: uid('ver'),
          versionCode: 2,
          versionName: '1.1.0',
          platform: 'web',
          updateLog: 'Added offline document cache, anti-replay protection, and browser-native settings runtime.',
          forceUpdate: false,
          grayRatio: 100,
          downloadUrl: './index.html'
        }
      ],
      verificationCodes: [],
      idempotencyKeys: {},
      usedNonces: [],
      cacheBuckets: {
        images: [4.18, 6.25, 12.42],
        voice: [2.11, 3.38, 8.54],
        temp: [1.24, 9.81]
      },
      documentCache: {},
      documentSources: {
        user_agreement: {
          online: {
            'zh-CN': buildDocument('user_agreement', 'zh-CN'),
            'en-US': buildDocument('user_agreement', 'en-US')
          }
        },
        privacy_policy: {
          online: {
            'zh-CN': buildDocument('privacy_policy', 'zh-CN'),
            'en-US': buildDocument('privacy_policy', 'en-US')
          }
        }
      }
    };
  }

  function readDb() {
    try {
      var raw = localStorage.getItem(DB_KEY);
      if (!raw) {
        var created = createInitialDb();
        localStorage.setItem(DB_KEY, JSON.stringify(created));
        return created;
      }
      return JSON.parse(raw);
    } catch (error) {
      var fallback = createInitialDb();
      localStorage.setItem(DB_KEY, JSON.stringify(fallback));
      return fallback;
    }
  }

  function writeDb(db) {
    localStorage.setItem(DB_KEY, JSON.stringify(db));
  }

  function getUser(db) {
    return db.users[0];
  }

  function delay(result, timeout) {
    return new Promise(function (resolve) {
      window.setTimeout(function () {
        resolve(result);
      }, timeout || 120);
    });
  }

  function fail(message, code) {
    var error = new Error(message);
    error.code = code || 'REQUEST_FAILED';
    throw error;
  }

  function guardRequest(db, options) {
    var timestamp = options.timestamp || now();
    var nonce = options.nonce || uid('nonce');
    if (Math.abs(now() - timestamp) > REQUEST_TTL) {
      fail('REQUEST_EXPIRED', 'ANTI_REPLAY');
    }
    var existingNonce = db.usedNonces.find(function (item) {
      return item.nonce === nonce && Math.abs(timestamp - item.timestamp) <= REQUEST_TTL;
    });
    if (existingNonce) {
      fail('REQUEST_REPLAYED', 'ANTI_REPLAY');
    }
    db.usedNonces.push({ nonce: nonce, timestamp: timestamp });
    db.usedNonces = db.usedNonces.filter(function (item) {
      return now() - item.timestamp <= REQUEST_TTL;
    });
    return { timestamp: timestamp, nonce: nonce };
  }

  function rememberIdempotent(db, key, response) {
    if (!key) {
      return;
    }
    db.idempotencyKeys[key] = {
      response: deepClone(response),
      createdAt: now()
    };
  }

  function resolveIdempotent(db, key) {
    if (!key) {
      return null;
    }
    var record = db.idempotencyKeys[key];
    if (!record) {
      return null;
    }
    if (now() - record.createdAt > 24 * 60 * 60 * 1000) {
      delete db.idempotencyKeys[key];
      return null;
    }
    return deepClone(record.response);
  }

  function sanitizeTarget(target, mode) {
    var value = String(target || '').trim();
    if (mode === 'phone') {
      if (!/^1\d{10}$/.test(value)) {
        fail('INVALID_TARGET', 'VALIDATION');
      }
      return value;
    }
    if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(value)) {
      fail('INVALID_TARGET', 'VALIDATION');
    }
    return value.toLowerCase();
  }

  function sendVerificationCode(payload, meta) {
    var db = readDb();
    guardRequest(db, meta || {});
    var target = sanitizeTarget(payload.target, payload.mode);
    var existing = db.verificationCodes.find(function (item) {
      return item.target === target && item.action === payload.action;
    });
    var record = existing || {
      id: uid('otp'),
      target: target,
      action: payload.action,
      failedAttempts: 0,
      cooldownUntil: 0
    };
    if (record.cooldownUntil && record.cooldownUntil > now()) {
      writeDb(db);
      return delay({
        ok: false,
        code: 'COOLDOWN',
        cooldownUntil: record.cooldownUntil
      });
    }
    record.code = String(Math.floor(100000 + Math.random() * 900000));
    record.expiresAt = now() + 5 * 60 * 1000;
    record.failedAttempts = 0;
    record.cooldownUntil = 0;
    if (!existing) {
      db.verificationCodes.push(record);
    }
    writeDb(db);
    return delay({
      ok: true,
      code: record.code,
      expiresAt: record.expiresAt
    });
  }

  function bindTarget(payload, meta) {
    var db = readDb();
    var remembered = resolveIdempotent(db, meta && meta.idempotencyKey);
    if (remembered) {
      remembered.reused = true;
      return delay(remembered);
    }
    guardRequest(db, meta || {});
    var user = getUser(db);
    var target = sanitizeTarget(payload.target, payload.mode);
    var record = db.verificationCodes.find(function (item) {
      return item.target === target && item.action === payload.action;
    });
    if (!record || record.expiresAt < now()) {
      fail('INVALID_CODE', 'VALIDATION');
    }
    if (record.cooldownUntil && record.cooldownUntil > now()) {
      return delay({
        ok: false,
        code: 'COOLDOWN',
        cooldownUntil: record.cooldownUntil
      });
    }
    if (payload.currentPassword !== user.password) {
      fail('INVALID_PASSWORD', 'VALIDATION');
    }
    if (String(payload.code).trim() !== record.code) {
      record.failedAttempts += 1;
      if (record.failedAttempts >= 3) {
        record.cooldownUntil = now() + 60 * 1000;
      }
      writeDb(db);
      fail('INVALID_CODE', 'VALIDATION');
    }
    if (payload.mode === 'phone') {
      user.phone = target;
    } else {
      user.email = target;
    }
    db.verificationCodes = db.verificationCodes.filter(function (item) {
      return item.id !== record.id;
    });
    var response = {
      ok: true,
      user: deepClone(user)
    };
    rememberIdempotent(db, meta && meta.idempotencyKey, response);
    writeDb(db);
    return delay(response);
  }

  function scorePassword(password) {
    var score = 0;
    if (password.length >= 8) {
      score += 1;
    }
    if (/[a-z]/.test(password)) {
      score += 1;
    }
    if (/[A-Z]/.test(password)) {
      score += 1;
    }
    if (/\d/.test(password)) {
      score += 1;
    }
    if (/[^A-Za-z\d]/.test(password)) {
      score += 1;
    }
    return score;
  }

  function changePassword(payload, meta) {
    var db = readDb();
    var remembered = resolveIdempotent(db, meta && meta.idempotencyKey);
    if (remembered) {
      remembered.reused = true;
      return delay(remembered);
    }
    guardRequest(db, meta || {});
    var user = getUser(db);
    if (payload.currentPassword !== user.password) {
      fail('INVALID_PASSWORD', 'VALIDATION');
    }
    if (!PASSWORD_REGEX.test(payload.newPassword)) {
      fail('INVALID_NEW_PASSWORD', 'VALIDATION');
    }
    user.password = payload.newPassword;
    db.loginDevices.forEach(function (device) {
      if (device.userId === user.id) {
        device.active = false;
        device.refreshToken = '';
      }
    });
    var response = { ok: true };
    rememberIdempotent(db, meta && meta.idempotencyKey, response);
    writeDb(db);
    return delay(response, 160);
  }

  function getDevices() {
    var db = readDb();
    return delay(
      db.loginDevices
        .filter(function (device) {
          return device.userId === 1 && device.active;
        })
        .sort(function (left, right) {
          return right.lastActiveAt - left.lastActiveAt;
        })
    );
  }

  function logoutDevices(deviceIds, meta) {
    var db = readDb();
    var remembered = resolveIdempotent(db, meta && meta.idempotencyKey);
    if (remembered) {
      remembered.reused = true;
      return delay(remembered);
    }
    guardRequest(db, meta || {});
    db.loginDevices.forEach(function (device) {
      if (deviceIds.indexOf(device.id) >= 0) {
        device.active = false;
        device.refreshToken = '';
      }
    });
    var response = { ok: true, removed: deviceIds.slice() };
    rememberIdempotent(db, meta && meta.idempotencyKey, response);
    writeDb(db);
    return delay(response, 140);
  }

  function getNotificationPrefs() {
    var db = readDb();
    return delay(deepClone(db.notificationPrefs[1]));
  }

  function updateNotificationPrefs(payload, meta) {
    var db = readDb();
    guardRequest(db, meta || {});
    var prefs = db.notificationPrefs[1];
    var next = {
      pushEnabled: Boolean(payload.pushEnabled),
      systemEnabled: Boolean(payload.systemEnabled),
      activityEnabled: Boolean(payload.activityEnabled),
      aiReplyEnabled: Boolean(payload.aiReplyEnabled)
    };
    prefs.pushEnabled = next.pushEnabled;
    prefs.systemEnabled = next.pushEnabled ? next.systemEnabled : false;
    prefs.activityEnabled = next.pushEnabled ? next.activityEnabled : false;
    prefs.aiReplyEnabled = next.pushEnabled ? next.aiReplyEnabled : false;
    prefs.version += 1;
    prefs.gatewayStatus = 'pending';
    prefs.lastSyncAt = now();
    writeDb(db);
    window.setTimeout(function () {
      var latestDb = readDb();
      latestDb.notificationPrefs[1].gatewayStatus = 'ready';
      latestDb.notificationPrefs[1].lastSyncAt = now();
      writeDb(latestDb);
      window.dispatchEvent(new CustomEvent('pushGatewaySynced'));
    }, 1000);
    return delay(deepClone(prefs), 180);
  }

  function getCacheSummary() {
    var db = readDb();
    var images = db.cacheBuckets.images.reduce(function (sum, item) { return sum + item; }, 0);
    var voice = db.cacheBuckets.voice.reduce(function (sum, item) { return sum + item; }, 0);
    var temp = db.cacheBuckets.temp.reduce(function (sum, item) { return sum + item; }, 0);
    var total = images + voice + temp;
    return delay({
      images: roundMb(images),
      voice: roundMb(voice),
      temp: roundMb(temp),
      total: roundMb(total)
    }, 110);
  }

  function clearCache() {
    var db = readDb();
    var images = db.cacheBuckets.images.reduce(function (sum, item) { return sum + item; }, 0);
    var voice = db.cacheBuckets.voice.reduce(function (sum, item) { return sum + item; }, 0);
    var temp = db.cacheBuckets.temp.reduce(function (sum, item) { return sum + item; }, 0);
    var released = images + voice + temp;
    db.cacheBuckets.images = [];
    db.cacheBuckets.voice = [];
    db.cacheBuckets.temp = [];
    writeDb(db);
    window.dispatchEvent(new CustomEvent('cacheCleared', { detail: { released: roundMb(released) } }));
    return delay({
      released: roundMb(released)
    }, 260);
  }

  function getPreferences() {
    var db = readDb();
    var user = getUser(db);
    return delay({
      themePreference: user.themePreference,
      langPreference: user.langPreference
    });
  }

  function setThemePreference(value, meta) {
    var db = readDb();
    guardRequest(db, meta || {});
    var user = getUser(db);
    user.themePreference = value;
    writeDb(db);
    return delay({ ok: true, themePreference: value }, 100);
  }

  function setLanguagePreference(value, meta) {
    var db = readDb();
    guardRequest(db, meta || {});
    var user = getUser(db);
    user.langPreference = value;
    writeDb(db);
    return delay({ ok: true, langPreference: value }, 100);
  }

  function checkVersion(currentVersionCode) {
    var db = readDb();
    var versions = db.appVersions.slice().sort(function (left, right) {
      return right.versionCode - left.versionCode;
    });
    var latest = versions[0];
    if (!latest || latest.versionCode <= currentVersionCode) {
      return delay({ hasUpdate: false }, 90);
    }
    return delay({
      hasUpdate: true,
      latestVersion: latest.versionName,
      latestVersionCode: latest.versionCode,
      updateLog: latest.updateLog,
      forceUpdate: latest.forceUpdate,
      grayRatio: latest.grayRatio,
      downloadUrl: latest.downloadUrl
    }, 90);
  }

  function openDocument(key, locale) {
    var db = readDb();
    var cacheKey = key + ':' + locale;
    var cached = db.documentCache[cacheKey];
    if (cached) {
      return delay({
        title: key,
        source: 'cache',
        cachedAt: cached.cachedAt,
        html: cached.html
      });
    }
    var html = db.documentSources[key].online[locale] || db.documentSources[key].online['zh-CN'];
    db.documentCache[cacheKey] = {
      html: html,
      cachedAt: now()
    };
    writeDb(db);
    return delay({
      title: key,
      source: 'online',
      cachedAt: db.documentCache[cacheKey].cachedAt,
      html: html
    }, 120);
  }

  function clearDocumentCache() {
    var db = readDb();
    db.documentCache = {};
    writeDb(db);
    return delay({ ok: true }, 120);
  }

  window.SettingsService = {
    roundMb: roundMb,
    scorePassword: scorePassword,
    passwordRegex: PASSWORD_REGEX,
    uid: uid,
    init: function () {
      readDb();
    },
    getUserProfile: function () {
      var db = readDb();
      return delay(deepClone(getUser(db)));
    },
    sendVerificationCode: sendVerificationCode,
    bindTarget: bindTarget,
    changePassword: changePassword,
    getDevices: getDevices,
    logoutDevices: logoutDevices,
    getNotificationPrefs: getNotificationPrefs,
    updateNotificationPrefs: updateNotificationPrefs,
    getCacheSummary: getCacheSummary,
    clearCache: clearCache,
    getPreferences: getPreferences,
    setThemePreference: setThemePreference,
    setLanguagePreference: setLanguagePreference,
    checkVersion: checkVersion,
    openDocument: openDocument,
    clearDocumentCache: clearDocumentCache
  };
}());
