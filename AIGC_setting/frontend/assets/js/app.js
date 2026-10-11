(function () {
  var root = document.getElementById('app');
  var service = window.SettingsService;
  var state = {
    locale: localStorage.getItem('lang_preference') || 'zh-CN',
    themePreference: localStorage.getItem('theme_preference') || 'system',
    systemTheme: window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light',
    activeSection: 'overview',
    user: null,
    notification: null,
    cache: null,
    devices: [],
    selectedDevices: [],
    loading: false,
    loadingText: '',
    toasts: [],
    currentDocument: null,
    updateInfo: null,
    bindForm: {
      mode: 'phone',
      action: 'bind',
      target: '',
      code: '',
      currentPassword: 'Demo@1234'
    },
    passwordForm: {
      currentPassword: 'Demo@1234',
      newPassword: ''
    }
  };

  function t(key, payload) {
    return window.SettingsI18n.get(state.locale, key, payload);
  }

  function escapeHtml(value) {
    return String(value == null ? '' : value)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#39;');
  }

  function setLoading(flag, text) {
    state.loading = flag;
    state.loadingText = text || t('loading');
    render();
  }

  function pushToast(type, title, message) {
    var id = service.uid('toast');
    state.toasts = state.toasts.concat([{ id: id, type: type, title: title, message: message }]).slice(-4);
    render();
    window.setTimeout(function () {
      state.toasts = state.toasts.filter(function (item) { return item.id !== id; });
      render();
    }, 3200);
  }

  function formatDate(value) {
    return new Intl.DateTimeFormat(state.locale, {
      year: 'numeric',
      month: '2-digit',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit'
    }).format(new Date(value));
  }

  function formatNumber(value) {
    return new Intl.NumberFormat(state.locale, {
      maximumFractionDigits: 2
    }).format(Number(value));
  }

  function formatCurrency(value) {
    return new Intl.NumberFormat(state.locale, {
      style: 'currency',
      currency: state.locale === 'zh-CN' ? 'CNY' : 'USD'
    }).format(Number(value));
  }

  function getEffectiveTheme() {
    if (state.themePreference === 'system') {
      return state.systemTheme;
    }
    return state.themePreference === 'dark' ? 'dark' : 'light';
  }

  function applyTheme() {
    var effective = getEffectiveTheme();
    document.documentElement.setAttribute('data-theme', effective);
    document.documentElement.lang = state.locale;
    localStorage.setItem('theme_preference', state.themePreference);
    localStorage.setItem('lang_preference', state.locale);
  }

  function buildRequestMeta(useIdempotency) {
    var meta = {
      timestamp: Date.now(),
      nonce: service.uid('nonce')
    };
    if (useIdempotency) {
      meta.idempotencyKey = service.uid('idempotency');
    }
    return meta;
  }

  function handleServiceError(error) {
    if (!error) {
      return t('operation_failed');
    }
    if (error.message === 'INVALID_TARGET') {
      return t('invalid_target');
    }
    if (error.message === 'INVALID_PASSWORD') {
      return t('invalid_password');
    }
    if (error.message === 'INVALID_CODE') {
      return t('invalid_code');
    }
    if (error.code === 'ANTI_REPLAY' || error.message === 'REQUEST_EXPIRED' || error.message === 'REQUEST_REPLAYED') {
      return t('anti_replay_error');
    }
    if (error.message === 'INVALID_NEW_PASSWORD') {
      return t('password_rule');
    }
    return t('operation_failed');
  }

  function passwordStrength() {
    return service.scorePassword(state.passwordForm.newPassword);
  }

  function updateSelectedDevices(deviceId, checked) {
    if (checked) {
      if (state.selectedDevices.indexOf(deviceId) < 0) {
        state.selectedDevices.push(deviceId);
      }
      return;
    }
    state.selectedDevices = state.selectedDevices.filter(function (item) { return item !== deviceId; });
  }

  function currentVersionCode() {
    return window.APP_VERSION && window.APP_VERSION.versionCode ? window.APP_VERSION.versionCode : 1;
  }

  function renderOverview() {
    return '' +
      '<section class="card">' +
        '<div class="section-header">' +
          '<div>' +
            '<h2 class="section-title">' + t('section_overview_title') + '</h2>' +
            '<div class="card-subtitle">' + t('section_overview_desc') + '</div>' +
          '</div>' +
          '<span class="tag">' + t('runtime_ready') + '</span>' +
        '</div>' +
        '<div class="tile-grid">' +
          '<div class="metric-tile"><strong>' + t('overview_local') + '</strong><span class="metric-value">file://</span><div class="muted">' + t('overview_local_desc') + '</div></div>' +
          '<div class="metric-tile"><strong>' + t('overview_secure') + '</strong><span class="metric-value">OTP / Nonce</span><div class="muted">' + t('overview_secure_desc') + '</div></div>' +
          '<div class="metric-tile"><strong>' + t('overview_theme') + '</strong><span class="metric-value">' + escapeHtml(state.themePreference) + ' / ' + escapeHtml(state.locale) + '</span><div class="muted">' + t('overview_theme_desc') + '</div></div>' +
          '<div class="metric-tile"><strong>' + t('overview_cache') + '</strong><span class="metric-value">' + (state.cache ? state.cache.total : '0.00') + ' MB</span><div class="muted">' + t('overview_cache_desc') + '</div></div>' +
        '</div>' +
      '</section>' +
      '<section class="card">' +
        '<div class="section-header">' +
          '<div>' +
            '<h2 class="section-title">' + t('simulated_backend') + '</h2>' +
            '<div class="card-subtitle">' + t('simulated_backend_desc') + '</div>' +
          '</div>' +
        '</div>' +
        '<div class="grid-two">' +
          '<div>' +
            '<div class="field-hint">' + t('weak_network') + '</div>' +
            '<div class="status-line">' + t('current_version') + ': <span class="mono">v' + escapeHtml(window.APP_VERSION.version) + '</span></div>' +
          '</div>' +
          '<div>' +
            '<div class="status-line">' + t('push_gateway_state') + ': ' + (state.notification && state.notification.gatewayStatus === 'ready' ? t('gateway_ready') : t('gateway_pending')) + '</div>' +
            '<div class="status-line">' + t('last_sync') + ': ' + (state.notification ? formatDate(state.notification.lastSyncAt) : '-') + '</div>' +
          '</div>' +
        '</div>' +
      '</section>';
  }

  function renderAccount() {
    var strength = passwordStrength();
    var deviceItems = state.devices.length ? state.devices.map(function (device) {
      return '' +
        '<div class="device-card">' +
          '<label><input type="checkbox" data-action="toggle-device" data-id="' + escapeHtml(device.id) + '"' + (state.selectedDevices.indexOf(device.id) >= 0 ? ' checked' : '') + '></label>' +
          '<div>' +
            '<h4>' + escapeHtml(device.deviceName) + '</h4>' +
            '<p>' + t('system_version') + ': ' + escapeHtml(device.systemVersion) + '</p>' +
            '<p>' + t('ip_address') + ': ' + escapeHtml(device.ipAddress) + '</p>' +
            '<p>' + t('last_active') + ': ' + formatDate(device.lastActiveAt) + '</p>' +
          '</div>' +
          '<div class="button-row"><button class="ghost-btn" data-action="logout-one" data-id="' + escapeHtml(device.id) + '">' + t('logout_device') + '</button></div>' +
        '</div>';
    }).join('') : '<div class="empty-state">' + t('no_devices') + '</div>';

    return '' +
      '<section class="card">' +
        '<div class="section-header">' +
          '<div><h2 class="section-title">' + t('account_title') + '</h2><div class="card-subtitle">' + t('account_desc') + '</div></div>' +
        '</div>' +
        '<div class="grid-two">' +
          '<div>' +
            '<h3>' + t('bind_title') + '</h3>' +
            '<div class="field-group"><label class="field-label">' + t('bind_type_label') + '</label>' +
              '<select class="select" data-field="bind.mode">' +
                '<option value="phone"' + (state.bindForm.mode === 'phone' ? ' selected' : '') + '>' + t('bind_mode_phone') + '</option>' +
                '<option value="email"' + (state.bindForm.mode === 'email' ? ' selected' : '') + '>' + t('bind_mode_email') + '</option>' +
              '</select>' +
            '</div>' +
            '<div class="field-group"><label class="field-label">' + t('bind_action_bind') + ' / ' + t('bind_action_rebind') + '</label>' +
              '<select class="select" data-field="bind.action">' +
                '<option value="bind"' + (state.bindForm.action === 'bind' ? ' selected' : '') + '>' + t('bind_action_bind') + '</option>' +
                '<option value="rebind"' + (state.bindForm.action === 'rebind' ? ' selected' : '') + '>' + t('bind_action_rebind') + '</option>' +
              '</select>' +
            '</div>' +
            '<div class="field-group"><label class="field-label">' + t('bind_target_label') + '</label><input class="input" data-field="bind.target" value="' + escapeHtml(state.bindForm.target) + '" placeholder="' + (state.bindForm.mode === 'phone' ? '13800138000' : 'demo@example.com') + '"></div>' +
            '<div class="inline-row">' +
              '<div class="field-group" style="flex:1"><label class="field-label">' + t('verify_code_label') + '</label><input class="input" data-field="bind.code" value="' + escapeHtml(state.bindForm.code) + '" placeholder="123456"></div>' +
              '<button class="secondary-btn" data-action="send-code">' + t('send_code') + '</button>' +
            '</div>' +
            '<div class="field-group"><label class="field-label">' + t('current_password_label') + '</label><input type="password" class="input" data-field="bind.currentPassword" value="' + escapeHtml(state.bindForm.currentPassword) + '"></div>' +
            '<div class="button-row"><button class="action-btn" data-action="submit-bind">' + t('submit_bind') + '</button></div>' +
          '</div>' +
          '<div>' +
            '<h3>' + t('password_title') + '</h3>' +
            '<div class="field-group"><label class="field-label">' + t('current_password_label') + '</label><input type="password" class="input" data-field="password.currentPassword" value="' + escapeHtml(state.passwordForm.currentPassword) + '"></div>' +
            '<div class="field-group"><label class="field-label">' + t('new_password_label') + '</label><input type="password" class="input" data-field="password.newPassword" value="' + escapeHtml(state.passwordForm.newPassword) + '" placeholder="Demo@1234"></div>' +
            '<div class="field-hint">' + t('password_rule') + '</div>' +
            '<div class="progress"><div class="progress-bar" style="width:' + (strength * 20) + '%"></div></div>' +
            '<div class="status-line">' + t('password_strength') + ': ' + t('strength_' + strength) + '</div>' +
            '<div class="button-row"><button class="action-btn" data-action="change-password">' + t('change_password') + '</button></div>' +
          '</div>' +
        '</div>' +
      '</section>' +
      '<section class="card">' +
        '<div class="section-header">' +
          '<div><h2 class="section-title">' + t('devices_title') + '</h2><div class="card-subtitle">' + t('devices_desc') + '</div></div>' +
          '<div class="device-toolbar">' +
            '<span class="muted">' + t('selected_count', { count: state.selectedDevices.length }) + '</span>' +
            '<button class="secondary-btn" data-action="logout-selected"' + (state.selectedDevices.length ? '' : ' disabled') + '>' + t('logout_selected') + '</button>' +
          '</div>' +
        '</div>' +
        '<div class="device-list">' + deviceItems + '</div>' +
      '</section>';
  }

  function renderNotifications() {
    var prefs = state.notification || {
      pushEnabled: true,
      systemEnabled: true,
      activityEnabled: true,
      aiReplyEnabled: true,
      gatewayStatus: 'ready',
      lastSyncAt: Date.now()
    };
    var childDisabled = !prefs.pushEnabled;
    function switchRow(key, title) {
      return '' +
        '<div class="switch-row">' +
          '<div class="switch-meta"><strong>' + title + '</strong><span class="muted">' + t('save_success') + '</span></div>' +
          '<label class="switch"><input type="checkbox" data-action="toggle-notification" data-key="' + key + '"' + (prefs[key] ? ' checked' : '') + (key !== 'pushEnabled' && childDisabled ? ' disabled' : '') + '><span class="slider"></span></label>' +
        '</div>';
    }
    return '' +
      '<section class="card">' +
        '<div class="section-header">' +
          '<div><h2 class="section-title">' + t('notification_title') + '</h2><div class="card-subtitle">' + t('notification_desc') + '</div></div>' +
          '<span class="tag">' + (prefs.gatewayStatus === 'ready' ? t('gateway_ready') : t('gateway_pending')) + '</span>' +
        '</div>' +
        switchRow('pushEnabled', t('push_master')) +
        switchRow('systemEnabled', t('system_message')) +
        switchRow('activityEnabled', t('activity_message')) +
        switchRow('aiReplyEnabled', t('ai_reply')) +
        '<div class="status-line">' + t('sync_hint') + '</div>' +
        '<div class="status-line">' + t('last_sync') + ': ' + formatDate(prefs.lastSyncAt) + '</div>' +
      '</section>';
  }

  function renderCache() {
    var summary = state.cache || { images: '0.00', voice: '0.00', temp: '0.00', total: '0.00' };
    return '' +
      '<section class="card">' +
        '<div class="section-header">' +
          '<div><h2 class="section-title">' + t('cache_title') + '</h2><div class="card-subtitle">' + t('cache_desc') + '</div></div>' +
          '<div class="button-row">' +
            '<button class="secondary-btn" data-action="rescan-cache">' + t('rescan_cache') + '</button>' +
            '<button class="action-btn" data-action="clear-cache">' + t('clear_cache') + '</button>' +
          '</div>' +
        '</div>' +
        '<div class="tile-grid">' +
          '<div class="metric-tile"><strong>' + t('cache_images') + '</strong><span class="metric-value">' + summary.images + ' MB</span></div>' +
          '<div class="metric-tile"><strong>' + t('cache_voice') + '</strong><span class="metric-value">' + summary.voice + ' MB</span></div>' +
          '<div class="metric-tile"><strong>' + t('cache_temp') + '</strong><span class="metric-value">' + summary.temp + ' MB</span></div>' +
          '<div class="metric-tile"><strong>' + t('cache_total') + '</strong><span class="metric-value">' + summary.total + ' MB</span><div class="muted">' + t('cache_event') + '</div></div>' +
        '</div>' +
      '</section>';
  }

  function renderTheme() {
    function pill(value, title, desc) {
      return '' +
        '<button class="choice-pill' + (state.themePreference === value ? ' is-active' : '') + '" data-action="set-theme" data-value="' + value + '">' +
          '<strong>' + title + '</strong>' +
          '<span class="muted">' + desc + '</span>' +
        '</button>';
    }
    return '' +
      '<section class="card">' +
        '<div class="section-header">' +
          '<div><h2 class="section-title">' + t('theme_title') + '</h2><div class="card-subtitle">' + t('theme_desc') + '</div></div>' +
          '<span class="tag">' + getEffectiveTheme() + '</span>' +
        '</div>' +
        '<div class="theme-choices">' +
          pill('system', t('theme_system'), state.systemTheme) +
          pill('light', t('theme_light'), 'light') +
          pill('dark', t('theme_dark'), 'dark') +
        '</div>' +
      '</section>';
  }

  function renderLanguage() {
    var sampleDate = formatDate(Date.now());
    var sampleNumber = formatNumber(1234567.89);
    var sampleCurrency = formatCurrency(1288.5);
    return '' +
      '<section class="card">' +
        '<div class="section-header">' +
          '<div><h2 class="section-title">' + t('language_title') + '</h2><div class="card-subtitle">' + t('language_desc') + '</div></div>' +
          '<span class="tag">' + escapeHtml(state.locale) + '</span>' +
        '</div>' +
        '<div class="lang-choices">' +
          '<button class="lang-pill' + (state.locale === 'zh-CN' ? ' is-active' : '') + '" data-action="set-language" data-value="zh-CN"><strong>' + t('lang_zh') + '</strong><span class="muted">zh-CN</span></button>' +
          '<button class="lang-pill' + (state.locale === 'en-US' ? ' is-active' : '') + '" data-action="set-language" data-value="en-US"><strong>' + t('lang_en') + '</strong><span class="muted">en-US</span></button>' +
        '</div>' +
        '<div class="tile-grid" style="margin-top:18px">' +
          '<div class="metric-tile"><strong>' + t('locale_preview_date') + '</strong><span class="metric-value" style="font-size:18px">' + sampleDate + '</span></div>' +
          '<div class="metric-tile"><strong>' + t('locale_preview_number') + '</strong><span class="metric-value" style="font-size:18px">' + sampleNumber + '</span></div>' +
          '<div class="metric-tile"><strong>' + t('locale_preview_currency') + '</strong><span class="metric-value" style="font-size:18px">' + sampleCurrency + '</span></div>' +
        '</div>' +
      '</section>';
  }

  function renderAbout() {
    var updateInfo = state.updateInfo;
    var updateBlock = updateInfo ? '' +
      '<div class="card" style="margin-top:18px">' +
        '<div class="section-header">' +
          '<div><h3 style="margin:0">' + t('latest_version') + ': ' + escapeHtml(updateInfo.latestVersion) + '</h3><div class="card-subtitle">' + t('gray_ratio') + ': ' + escapeHtml(updateInfo.grayRatio) + '%</div></div>' +
          '<span class="tag">' + (updateInfo.forceUpdate ? t('force_update') : t('save_success')) + '</span>' +
        '</div>' +
        '<div><strong>' + t('update_log') + '</strong><p>' + escapeHtml(updateInfo.updateLog) + '</p></div>' +
        '<div class="button-row">' +
          (updateInfo.forceUpdate ? '' : '<button class="secondary-btn" data-action="dismiss-update">' + t('later') + '</button>') +
          '<button class="action-btn" data-action="apply-update">' + t('update_now') + '</button>' +
        '</div>' +
      '</div>' : '';

    return '' +
      '<section class="card">' +
        '<div class="section-header">' +
          '<div><h2 class="section-title">' + t('about_title') + '</h2><div class="card-subtitle">' + t('about_desc') + '</div></div>' +
          '<span class="tag">v' + escapeHtml(window.APP_VERSION.version) + '</span>' +
        '</div>' +
        '<div class="tile-grid">' +
          '<div class="metric-tile"><strong>' + t('current_version') + '</strong><span class="metric-value">v' + escapeHtml(window.APP_VERSION.version) + '</span></div>' +
          '<div class="metric-tile"><strong>' + t('simulated_backend') + '</strong><span class="metric-value">localStorage</span><div class="muted">' + t('doc_intro') + '</div></div>' +
        '</div>' +
        '<div class="button-row" style="margin-top:18px">' +
          '<button class="action-btn" data-action="check-update">' + t('check_update') + '</button>' +
          '<button class="secondary-btn" data-action="open-document" data-doc="user_agreement">' + t('user_agreement') + '</button>' +
          '<button class="secondary-btn" data-action="open-document" data-doc="privacy_policy">' + t('privacy_policy') + '</button>' +
          '<button class="ghost-btn" data-action="clear-doc-cache">' + t('clear_doc_cache') + '</button>' +
        '</div>' +
        updateBlock +
      '</section>';
  }

  function renderContent() {
    if (state.activeSection === 'account') {
      return renderAccount();
    }
    if (state.activeSection === 'notification') {
      return renderNotifications();
    }
    if (state.activeSection === 'cache') {
      return renderCache();
    }
    if (state.activeSection === 'theme') {
      return renderTheme();
    }
    if (state.activeSection === 'language') {
      return renderLanguage();
    }
    if (state.activeSection === 'about') {
      return renderAbout();
    }
    return renderOverview();
  }

  function renderDocumentModal() {
    if (!state.currentDocument) {
      return '';
    }
    return '' +
      '<div class="modal" data-action="close-document">' +
        '<div class="modal-card large" onclick="event.stopPropagation()">' +
          '<div class="modal-header">' +
            '<div>' +
              '<h3 class="doc-title">' + (state.currentDocument.key === 'user_agreement' ? t('user_agreement') : t('privacy_policy')) + '</h3>' +
              '<div class="doc-meta">' + (state.currentDocument.source === 'cache' ? t('offline_doc') : t('online_doc')) + ' · ' + t('last_sync') + ': ' + formatDate(state.currentDocument.cachedAt) + '</div>' +
            '</div>' +
            '<button class="ghost-btn" data-action="close-document">' + t('close') + '</button>' +
          '</div>' +
          '<div class="modal-body"><div class="doc-frame">' + state.currentDocument.html + '</div></div>' +
        '</div>' +
      '</div>';
  }

  function renderToasts() {
    return '<div class="toast-stack">' + state.toasts.map(function (toast) {
      return '' +
        '<div class="toast is-' + toast.type + '">' +
          '<span class="toast-title">' + escapeHtml(toast.title) + '</span>' +
          '<div>' + escapeHtml(toast.message) + '</div>' +
        '</div>';
    }).join('') + '</div>';
  }

  function render() {
    applyTheme();
    root.innerHTML = '' +
      renderToasts() +
      '<div class="app-shell">' +
        '<header class="topbar">' +
          '<div class="brand-block">' +
            '<h1>' + t('app_title') + '</h1>' +
            '<p>' + t('app_subtitle') + '</p>' +
          '</div>' +
          '<div class="toolbar">' +
            '<div class="badge"><span class="dot"></span><span>' + t('runtime_ready_desc') + '</span></div>' +
          '</div>' +
        '</header>' +
        '<div class="page-grid">' +
          '<aside class="sidebar">' +
            '<div class="panel">' +
              '<div class="nav-list">' +
                navButton('overview', t('nav_overview')) +
                navButton('account', t('nav_account')) +
                navButton('notification', t('nav_notification')) +
                navButton('cache', t('nav_cache')) +
                navButton('theme', t('nav_theme')) +
                navButton('language', t('nav_language')) +
                navButton('about', t('nav_about')) +
              '</div>' +
            '</div>' +
          '</aside>' +
          '<main class="content">' + renderContent() + '</main>' +
        '</div>' +
      '</div>' +
      (state.loading ? '<div class="loading-mask"><div class="modal-card"><div class="spinner"></div><h3>' + t('loading') + '</h3><p>' + escapeHtml(state.loadingText) + '</p></div></div>' : '') +
      renderDocumentModal();
  }

  function navButton(key, label) {
    return '<button class="nav-item' + (state.activeSection === key ? ' is-active' : '') + '" data-action="navigate" data-section="' + key + '"><span>' + label + '</span><span class="hide-on-small">›</span></button>';
  }

  function refreshAll() {
    setLoading(true, t('loading'));
    return Promise.all([
      service.getUserProfile(),
      service.getNotificationPrefs(),
      service.getCacheSummary(),
      service.getDevices()
    ]).then(function (results) {
      state.user = results[0];
      state.notification = results[1];
      state.cache = results[2];
      state.devices = results[3];
      if (!state.bindForm.target) {
        state.bindForm.target = state.bindForm.mode === 'phone' ? state.user.phone : state.user.email;
      }
      setLoading(false, '');
    }).catch(function (error) {
      setLoading(false, '');
      pushToast('error', t('feedback_error'), handleServiceError(error));
    });
  }

  function onFieldInput(target) {
    var field = target.getAttribute('data-field');
    if (!field) {
      return;
    }
    var value = target.value;
    if (field === 'bind.mode') {
      state.bindForm.mode = value;
      state.bindForm.target = value === 'phone' ? (state.user ? state.user.phone : '') : (state.user ? state.user.email : '');
      render();
      return;
    }
    if (field === 'bind.action') {
      state.bindForm.action = value;
      return;
    }
    if (field === 'bind.target') {
      state.bindForm.target = value;
      return;
    }
    if (field === 'bind.code') {
      state.bindForm.code = value;
      return;
    }
    if (field === 'bind.currentPassword') {
      state.bindForm.currentPassword = value;
      return;
    }
    if (field === 'password.currentPassword') {
      state.passwordForm.currentPassword = value;
      return;
    }
    if (field === 'password.newPassword') {
      state.passwordForm.newPassword = value;
      render();
    }
  }

  function onActionClick(target) {
    var action = target.getAttribute('data-action');
    if (!action) {
      return;
    }
    if (action === 'navigate') {
      state.activeSection = target.getAttribute('data-section');
      render();
      return;
    }
    if (action === 'send-code') {
      setLoading(true, t('loading'));
      service.sendVerificationCode({
        target: state.bindForm.target,
        mode: state.bindForm.mode,
        action: state.bindForm.action
      }, buildRequestMeta(false)).then(function (response) {
        setLoading(false, '');
        if (!response.ok && response.code === 'COOLDOWN') {
          pushToast('error', t('feedback_error'), t('cooldown_active', { seconds: Math.ceil((response.cooldownUntil - Date.now()) / 1000) }));
          return;
        }
        pushToast('success', t('feedback_success'), t('code_sent_demo', { code: response.code }));
      }).catch(function (error) {
        setLoading(false, '');
        pushToast('error', t('feedback_error'), handleServiceError(error));
      });
      return;
    }
    if (action === 'submit-bind') {
      setLoading(true, t('loading'));
      service.bindTarget({
        target: state.bindForm.target,
        mode: state.bindForm.mode,
        action: state.bindForm.action,
        code: state.bindForm.code,
        currentPassword: state.bindForm.currentPassword
      }, buildRequestMeta(true)).then(function (response) {
        setLoading(false, '');
        if (!response.ok && response.code === 'COOLDOWN') {
          pushToast('error', t('feedback_error'), t('cooldown_active', { seconds: Math.ceil((response.cooldownUntil - Date.now()) / 1000) }));
          return;
        }
        state.user = response.user;
        state.bindForm.code = '';
        pushToast('success', t('feedback_success'), response.reused ? t('idempotent_reused') : t('bind_success'));
        render();
      }).catch(function (error) {
        setLoading(false, '');
        pushToast('error', t('feedback_error'), handleServiceError(error));
      });
      return;
    }
    if (action === 'change-password') {
      setLoading(true, t('loading'));
      service.changePassword({
        currentPassword: state.passwordForm.currentPassword,
        newPassword: state.passwordForm.newPassword
      }, buildRequestMeta(true)).then(function (response) {
        setLoading(false, '');
        state.passwordForm.newPassword = '';
        pushToast('success', t('feedback_success'), response.reused ? t('idempotent_reused') : t('password_changed'));
        refreshAll();
      }).catch(function (error) {
        setLoading(false, '');
        pushToast('error', t('feedback_error'), handleServiceError(error));
      });
      return;
    }
    if (action === 'toggle-device') {
      updateSelectedDevices(target.getAttribute('data-id'), target.checked);
      render();
      return;
    }
    if (action === 'logout-one') {
      var deviceId = target.getAttribute('data-id');
      setLoading(true, t('loading'));
      service.logoutDevices([deviceId], buildRequestMeta(true)).then(function () {
        setLoading(false, '');
        state.selectedDevices = state.selectedDevices.filter(function (item) { return item !== deviceId; });
        pushToast('success', t('feedback_success'), t('device_logged_out'));
        refreshAll();
      }).catch(function (error) {
        setLoading(false, '');
        pushToast('error', t('feedback_error'), handleServiceError(error));
      });
      return;
    }
    if (action === 'logout-selected') {
      if (!state.selectedDevices.length) {
        return;
      }
      setLoading(true, t('loading'));
      service.logoutDevices(state.selectedDevices.slice(), buildRequestMeta(true)).then(function () {
        setLoading(false, '');
        state.selectedDevices = [];
        pushToast('success', t('feedback_success'), t('batch_done'));
        refreshAll();
      }).catch(function (error) {
        setLoading(false, '');
        pushToast('error', t('feedback_error'), handleServiceError(error));
      });
      return;
    }
    if (action === 'toggle-notification') {
      var key = target.getAttribute('data-key');
      var nextPrefs = {
        pushEnabled: state.notification.pushEnabled,
        systemEnabled: state.notification.systemEnabled,
        activityEnabled: state.notification.activityEnabled,
        aiReplyEnabled: state.notification.aiReplyEnabled
      };
      nextPrefs[key] = target.checked;
      if (key === 'pushEnabled' && !target.checked) {
        nextPrefs.systemEnabled = false;
        nextPrefs.activityEnabled = false;
        nextPrefs.aiReplyEnabled = false;
      }
      setLoading(true, t('loading'));
      service.updateNotificationPrefs(nextPrefs, buildRequestMeta(false)).then(function (prefs) {
        state.notification = prefs;
        setLoading(false, '');
        pushToast('success', t('feedback_success'), t('save_success'));
        render();
      }).catch(function (error) {
        setLoading(false, '');
        pushToast('error', t('feedback_error'), handleServiceError(error));
      });
      return;
    }
    if (action === 'rescan-cache') {
      setLoading(true, t('loading'));
      service.getCacheSummary().then(function (summary) {
        state.cache = summary;
        setLoading(false, '');
        pushToast('success', t('feedback_success'), t('save_success'));
        render();
      }).catch(function (error) {
        setLoading(false, '');
        pushToast('error', t('feedback_error'), handleServiceError(error));
      });
      return;
    }
    if (action === 'clear-cache') {
      setLoading(true, t('loading'));
      service.clearCache().then(function (summary) {
        setLoading(false, '');
        pushToast('success', t('feedback_success'), t('cache_cleared', { size: summary.released }));
        refreshAll();
      }).catch(function (error) {
        setLoading(false, '');
        pushToast('error', t('feedback_error'), handleServiceError(error));
      });
      return;
    }
    if (action === 'set-theme') {
      var themeValue = target.getAttribute('data-value');
      setLoading(true, t('loading'));
      service.setThemePreference(themeValue, buildRequestMeta(false)).then(function () {
        state.themePreference = themeValue;
        localStorage.setItem('theme_preference', themeValue);
        setLoading(false, '');
        pushToast('success', t('feedback_success'), t('theme_saved'));
        render();
      }).catch(function (error) {
        setLoading(false, '');
        pushToast('error', t('feedback_error'), handleServiceError(error));
      });
      return;
    }
    if (action === 'set-language') {
      var localeValue = target.getAttribute('data-value');
      setLoading(true, t('loading'));
      service.setLanguagePreference(localeValue, buildRequestMeta(false)).then(function () {
        state.locale = localeValue;
        localStorage.setItem('lang_preference', localeValue);
        setLoading(false, '');
        pushToast('success', t('feedback_success'), t('save_success'));
        render();
      }).catch(function (error) {
        setLoading(false, '');
        pushToast('error', t('feedback_error'), handleServiceError(error));
      });
      return;
    }
    if (action === 'check-update') {
      setLoading(true, t('loading'));
      service.checkVersion(currentVersionCode()).then(function (info) {
        setLoading(false, '');
        if (!info.hasUpdate) {
          state.updateInfo = null;
          pushToast('success', t('feedback_success'), t('no_update'));
          render();
          return;
        }
        state.updateInfo = info;
        render();
      }).catch(function (error) {
        setLoading(false, '');
        pushToast('error', t('feedback_error'), handleServiceError(error));
      });
      return;
    }
    if (action === 'dismiss-update') {
      state.updateInfo = null;
      render();
      return;
    }
    if (action === 'apply-update') {
      pushToast('success', t('feedback_success'), (state.updateInfo && state.updateInfo.forceUpdate ? t('force_update') + ' · ' : '') + (state.updateInfo ? state.updateInfo.downloadUrl : './index.html'));
      return;
    }
    if (action === 'open-document') {
      var docKey = target.getAttribute('data-doc');
      setLoading(true, t('loading'));
      service.openDocument(docKey, state.locale).then(function (documentInfo) {
        setLoading(false, '');
        state.currentDocument = {
          key: docKey,
          source: documentInfo.source,
          cachedAt: documentInfo.cachedAt,
          html: documentInfo.html
        };
        pushToast('success', t('feedback_success'), t('doc_cached'));
        render();
      }).catch(function (error) {
        setLoading(false, '');
        pushToast('error', t('feedback_error'), handleServiceError(error));
      });
      return;
    }
    if (action === 'close-document') {
      state.currentDocument = null;
      render();
      return;
    }
    if (action === 'clear-doc-cache') {
      setLoading(true, t('loading'));
      service.clearDocumentCache().then(function () {
        setLoading(false, '');
        pushToast('success', t('feedback_success'), t('doc_cache_cleared'));
      }).catch(function (error) {
        setLoading(false, '');
        pushToast('error', t('feedback_error'), handleServiceError(error));
      });
      return;
    }
  }

  function attachEvents() {
    document.addEventListener('click', function (event) {
      var actionTarget = event.target.closest('[data-action]');
      if (actionTarget) {
        onActionClick(actionTarget);
      }
    });
    document.addEventListener('input', function (event) {
      onFieldInput(event.target);
    });
    var mediaQuery = window.matchMedia ? window.matchMedia('(prefers-color-scheme: dark)') : null;
    if (mediaQuery && mediaQuery.addEventListener) {
      mediaQuery.addEventListener('change', function (event) {
        state.systemTheme = event.matches ? 'dark' : 'light';
        render();
      });
    }
    window.addEventListener('pushGatewaySynced', function () {
      service.getNotificationPrefs().then(function (prefs) {
        state.notification = prefs;
        render();
      });
    });
    window.addEventListener('cacheCleared', function (event) {
      if (event && event.detail && event.detail.released) {
        pushToast('success', t('feedback_success'), t('cache_cleared', { size: event.detail.released }));
      }
    });
  }

  function boot() {
    try {
      service.init();
      attachEvents();
      render();
      refreshAll();
    } catch (error) {
      root.innerHTML = '<div class="app-shell"><div class="error-banner">' + escapeHtml(handleServiceError(error)) + '</div></div>';
    }
  }

  boot();
}());
