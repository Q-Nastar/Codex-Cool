let editingProvider = null;
let statusInterval = null;
let currentLang = localStorage.getItem('codex-cool-lang') || 'zh';

const i18n = {
  zh: {
    running: '运行中',
    stopped: '已停止',
    langLabel: '中文',
    themeDark: '深色',
    themeLight: '浅色',
    addProvider: '添加供应商',
    docs: '文档',
    dashboard: '仪表盘',
    provider: 'API 供应商',
    uptime: '运行时间',
    proxyPort: '代理端口',
    injectTitle: 'Codex App 代理注入',
    quickAccess: '快速接入',
    providers: 'API 供应商',
    add: '添加',
    settings: '设置',
    listenAddr: '监听地址',
    port: '端口',
    logLevel: '日志级别',
    defaultProvider: '默认供应商',
    save: '保存',
    quickAdd: '快速添加供应商',
    noProvider: '暂无供应商，请先添加',
    selectModel: '-- 请先添加供应商 --',
    model: '模型',
    apiKey: 'API Key',
    apiKeyOptional: '(可选)',
    inject: '注入代理',
    restore: '恢复配置',
    detecting: '检测中...',
    injected: '● 已注入',
    notInjected: '○ 未注入',
    injectedMsg: '代理已注入',
    noConfig: '未检测到 Codex 配置文件',
    noClaudeConfig: '未检测到 Claude App 配置文件',
    currentProxy: '当前代理',
    currentConfig: '当前',
    hasBackup: '✅ 有备份',
    default: '默认',
    models: '模型',
    circuitOpen: '⚠ 熔断',
    test: '测试',
    edit: '编辑',
    delete: '删除',
    copied: '已复制到剪贴板',
    saved: '设置已保存',
    restartRequired: '（部分设置需重启生效）',
    providerAdded: '供应商已添加',
    providerUpdated: '供应商已更新',
    providerDeleted: '供应商已删除',
    testing: '正在测试连接...',
    connectOk: '连接成功',
    connectFail: '连接异常',
    confirmDelete: '确定要删除供应商',
    confirmRestore: '确定要恢复 Codex 原始配置吗？',
    restored: '已恢复原始配置',
    removed: '已移除代理配置',
    selectModelErr: '请选择模型',
    injectedSuccess: '代理已注入！模型:',
    nameRequired: '名称和 Base URL 不能为空',
    apiKeyRequired: '请输入 API Key',
    cancel: '取消',
    confirm: '确认添加',
    addProviderTitle: '添加供应商',
    editProviderTitle: '编辑供应商',
    quickSetup: '快速配置',
    quickSetupDesc: '输入 API Key 即可快速启动',
    name: '名称',
    baseUrl: 'Base URL',
    apiFormat: 'API 格式',
    modelMapping: '模型映射',
    modelMappingHint: '(可选，每行 alias=model_id)',
    envHint: '支持 env:VAR_NAME 引用环境变量',
    enabled: '启用',
    docsTitle: '使用文档',
    fetchingModels: '正在获取模型...',
    noModelsFound: '未获取到模型',
    modelsLoaded: '已加载 {n} 个模型',
    fetchModelsFailed: '获取模型失败',
    fillBaseUrl: '请先填写 Base URL',
    noDefaultProvider: '无默认供应商',
    mode3p: '第三方网关',
    mode1p: '官方登录',
    claudePrefix: 'Claude App',
    confirmClaudeRestore: '确定要恢复 Claude App 原始配置吗？',
    statusRunning: '运行中',
    toggleLangTitle: '切换语言',
    themeLightLabel: '浅色',
    themeToggleTitle: '切换主题',
    addProviderBtn: '添加供应商',
    docsBtn: '文档',
    statApiProviders: 'API 供应商',
    statUptime: '运行时间',
    statProxyPort: '代理端口',
    detectingText: '检测中...',
    selectInjectModel: '选择注入模型',
    injectProxyBtn: '注入代理',
    testConnBtn: '测试连接',
    loadModelsBtn: '载入可用模型',
    restoreDefaultConfig: '恢复默认配置',
    selectModelMultiHint: '(可多选)',
    quickAccess: '快速接入',
    copyBtn: '复制',
    apiProvidersTitle: 'API 供应商',
    addBtn: '添加',
    noProviderHint: '暂无供应商，请先添加',
    settingsTitle: '设置',
    listenAddrLabel: '监听地址',
    portLabel: '端口',
    logLevelLabel: '日志级别',
    defaultProviderLabel: '默认供应商',
    saveSettingsBtn: '保存设置',
    modalAddProviderTitle: '添加供应商',
    modalEditProviderTitle: '编辑供应商',
    nameLabel: '名称',
    apiFormatLabel: 'API 格式',
    modelListLabel: '模型列表',
    modelListHint: '(点击自动获取，或手动输入)',
    autoFetchModelsBtn: '自动获取模型',
    selectAllBtn: '全选/取消',
    manualInputPlaceholder: '手动输入模型，每行一个',
    enableLabel: '启用',
    cancelBtn: '取消',
    saveBtn: '保存',
    claudeInjectTitle: 'Claude App 代理注入',
    docsCodexApp: 'Codex App',
    docsCodexCli: 'Codex CLI',
    docsClaudeApp: 'Claude App',
    docsClaudeCode: 'Claude Code',
    docsEnvVar: '环境变量',
    docsCodexAppDesc1: '在仪表盘点击「注入代理」按钮，自动写入 ~/.codex/config.toml',
    docsCodexAppDesc2: '启动 Codex App，在模型选择器中选择 Codex-Cool 提供的模型即可。如需切回原始配置，点击「恢复配置」。',
    docsCodexCliDesc1: '编辑 ~/.codex/config.toml：',
    docsClaudeAppDesc1: '在仪表盘点击「注入代理」按钮，自动配置 Claude App 第三方推理网关',
    docsClaudeAppDesc2: '注入后重启 Claude App 即可使用第三方 API，无需登录。如需切回官方登录，点击「恢复配置」。',
    docsClaudeCodeDesc1: '设置环境变量后启动：',
    docsClaudeCodeDesc2: '或在 ~/.claude/settings.json 中添加：',
    docsEnvVarDesc1: '写入 shell 配置（如 ~/.zshrc 或 ~/.bashrc）：',
    docsEnvVarDesc2: '之后从 Dock 启动 Codex App 也能读到 Key',
    multimodalWarning: '⚠️ {providers} 不支持多模态（图片/文件），发送图片时将被替换为占位符。确定继续？',
    docsCodexAppDesc3: '支持的 API 格式：Responses（推荐）、Chat Completions',
    docsCodexAppDesc4: '检查点功能：通过 previous_response_id 实现链式对话上下文传递',
    docsCodexCliDesc2: '配置完成后直接在终端使用 codex 命令即可',
    docsClaudeAppDesc3: '⚠️ 注入前请确保 Claude Desktop 已关闭，否则可能写入失败',
    docsClaudeAppDesc4: '注入自动完成：切换 3P 模式 → 开启 Developer Mode → 设置 NODE_ENV=production（macOS）',
    docsClaudeAppDesc5: '支持多模型注入：可选择多个模型映射到 Claude 的 Opus/Sonnet/Haiku 等级',
    docsClaudeCodeDesc3: 'Claude Code 使用 Anthropic Messages 协议，自动转换为上游 Provider 格式',
    docsEnvVarDesc3: '也可在供应商配置中使用 env:VAR_NAME 引用环境变量，避免明文写入配置文件',
    docsApiProxy: 'API 代理',
    docsApiProxyDesc1: '任何兼容 OpenAI / Anthropic 的第三方客户端均可连接：',
    docsApiProxyDesc2: '支持协议：OpenAI Responses、OpenAI Chat Completions、Anthropic Messages',
    docsApiProxyDesc3: '协议自动转换：无论客户端发什么格式，都会自动转换成上游 Provider 需要的格式',
    docsMultimodal: '多模态处理',
    docsMultimodalDesc1: '以下 Provider 不支持图片/文件输入，发送时自动转换为占位符：',
    docsMultimodalDesc2: '首次选择此类模型时会弹出提醒，后续不再重复提示。图片会被替换为 [image] 占位符文本。',
  },
  en: {
    running: 'Running',
    stopped: 'Stopped',
    langLabel: 'EN',
    themeDark: 'Dark',
    themeLight: 'Light',
    addProvider: 'Add Provider',
    docs: 'Docs',
    dashboard: 'Dashboard',
    provider: 'Provider',
    uptime: 'Uptime',
    proxyPort: 'Port',
    injectTitle: 'Codex App Proxy Injection',
    quickAccess: 'Quick Access',
    providers: 'Providers',
    add: 'Add',
    settings: 'Settings',
    listenAddr: 'Listen Address',
    port: 'Port',
    logLevel: 'Log Level',
    defaultProvider: 'Default Provider',
    save: 'Save',
    quickAdd: 'Quick Add Provider',
    noProvider: 'No providers yet',
    selectModel: '-- Add a Provider first --',
    model: 'Model',
    apiKey: 'API Key',
    apiKeyOptional: '(optional)',
    inject: 'Inject Proxy',
    restore: 'Restore Config',
    detecting: 'Detecting...',
    injected: '● Injected',
    notInjected: '○ Not injected',
    injectedMsg: 'Proxy injected',
    noConfig: 'No Codex config found',
    noClaudeConfig: 'No Claude App config found',
    currentProxy: 'Current proxy',
    currentConfig: 'Current',
    hasBackup: '✅ Backup exists',
    default: 'Default',
    models: 'models',
    circuitOpen: '⚠ Circuit open',
    test: 'Test',
    edit: 'Edit',
    delete: 'Delete',
    copied: 'Copied to clipboard',
    saved: 'Settings saved',
    restartRequired: '(some changes require restart)',
    providerAdded: 'Provider added',
    providerUpdated: 'Provider updated',
    providerDeleted: 'Provider deleted',
    testing: 'Testing connection...',
    connectOk: 'Connected',
    connectFail: 'Connection failed',
    confirmDelete: 'Delete provider',
    confirmRestore: 'Restore original Codex config?',
    restored: 'Original config restored',
    removed: 'Proxy config removed',
    selectModelErr: 'Please select a model',
    injectedSuccess: 'Proxy injected! Model:',
    nameRequired: 'Name and Base URL are required',
    apiKeyRequired: 'Please enter API Key',
    cancel: 'Cancel',
    confirm: 'Add',
    addProviderTitle: 'Add Provider',
    editProviderTitle: 'Edit Provider',
    quickSetup: 'Quick Setup',
    quickSetupDesc: 'Enter API Key to get started',
    name: 'Name',
    baseUrl: 'Base URL',
    apiFormat: 'API Format',
    modelMapping: 'Model Mapping',
    modelMappingHint: '(optional, one alias=model_id per line)',
    envHint: 'Supports env:VAR_NAME for env variables',
    enabled: 'Enabled',
    docsTitle: 'Documentation',
    fetchingModels: 'Fetching models...',
    noModelsFound: 'No models found',
    modelsLoaded: '{n} model(s) loaded',
    fetchModelsFailed: 'Failed to fetch models',
    fillBaseUrl: 'Fill Base URL first',
    noDefaultProvider: 'No default provider',
    mode3p: '3rd Party Gateway',
    mode1p: 'Official Login',
    claudePrefix: 'Claude App',
    confirmClaudeRestore: 'Restore original Claude App config?',
    statusRunning: 'Running',
    toggleLangTitle: 'Switch Language',
    themeLightLabel: 'Light',
    themeToggleTitle: 'Toggle Theme',
    addProviderBtn: 'Add Provider',
    docsBtn: 'Docs',
    statApiProviders: 'API Providers',
    statUptime: 'Uptime',
    statProxyPort: 'Proxy Port',
    detectingText: 'Detecting...',
    selectInjectModel: 'Select Model',
    injectProxyBtn: 'Inject Proxy',
    testConnBtn: 'Test Connection',
    loadModelsBtn: 'Load Models',
    restoreDefaultConfig: 'Restore Default Config',
    selectModelMultiHint: '(multi-select)',
    quickAccess: 'Quick Access',
    copyBtn: 'Copy',
    apiProvidersTitle: 'API Providers',
    addBtn: 'Add',
    noProviderHint: 'No providers yet, please add first',
    settingsTitle: 'Settings',
    listenAddrLabel: 'Listen Address',
    portLabel: 'Port',
    logLevelLabel: 'Log Level',
    defaultProviderLabel: 'Default Provider',
    saveSettingsBtn: 'Save Settings',
    modalAddProviderTitle: 'Add Provider',
    modalEditProviderTitle: 'Edit Provider',
    nameLabel: 'Name',
    apiFormatLabel: 'API Format',
    modelListLabel: 'Model List',
    modelListHint: '(click to auto-fetch, or type manually)',
    autoFetchModelsBtn: 'Auto Fetch Models',
    selectAllBtn: 'Select All / Deselect',
    manualInputPlaceholder: 'Enter models manually, one per line',
    enableLabel: 'Enabled',
    cancelBtn: 'Cancel',
    saveBtn: 'Save',
    claudeInjectTitle: 'Claude App Proxy Injection',
    docsCodexApp: 'Codex App',
    docsCodexCli: 'Codex CLI',
    docsClaudeApp: 'Claude App',
    docsClaudeCode: 'Claude Code',
    docsEnvVar: 'Environment Variables',
    docsCodexAppDesc1: 'Click "Inject Proxy" on dashboard to write ~/.codex/config.toml automatically',
    docsCodexAppDesc2: 'Launch Codex App and select a Codex-Cool model from the model picker. Click "Restore Config" to revert.',
    docsCodexCliDesc1: 'Edit ~/.codex/config.toml:',
    docsClaudeAppDesc1: 'Click "Inject Proxy" on dashboard to configure Claude App third-party inference gateway',
    docsClaudeAppDesc2: 'Restart Claude App after injection to use third-party API without login. Click "Restore Config" to revert.',
    docsClaudeCodeDesc1: 'Set environment variables then launch:',
    docsClaudeCodeDesc2: 'Or add to ~/.claude/settings.json:',
    docsEnvVarDesc1: 'Write to shell config (e.g. ~/.zshrc or ~/.bashrc):',
    docsEnvVarDesc2: 'Launch Codex App from Dock will also read the Key',
    multimodalWarning: '⚠️ {providers} does not support multimodal input (images/files). Images will be replaced with placeholders. Continue?',
    docsCodexAppDesc3: 'Supported API formats: Responses (recommended), Chat Completions',
    docsCodexAppDesc4: 'Checkpoint: chain conversation context via previous_response_id',
    docsCodexCliDesc2: 'After configuration, use the codex command directly in terminal',
    docsClaudeAppDesc3: '⚠️ Make sure Claude Desktop is closed before injection, otherwise writing may fail',
    docsClaudeAppDesc4: 'Auto-injection: switch to 3P mode → enable Developer Mode → set NODE_ENV=production (macOS)',
    docsClaudeAppDesc5: 'Multi-model injection: map selected models to Claude Opus/Sonnet/Haiku tiers',
    docsClaudeCodeDesc3: 'Claude Code uses Anthropic Messages protocol, auto-converted to upstream Provider format',
    docsEnvVarDesc3: 'Use env:VAR_NAME in provider config to reference env vars, avoid plaintext keys',
    docsApiProxy: 'API Proxy',
    docsApiProxyDesc1: 'Any OpenAI / Anthropic compatible client can connect:',
    docsApiProxyDesc2: 'Protocols: OpenAI Responses, Chat Completions, Anthropic Messages',
    docsApiProxyDesc3: 'Auto conversion: any client format is converted to upstream Provider format',
    docsMultimodal: 'Multimodal Handling',
    docsMultimodalDesc1: 'These Providers do not support image/file input, auto-converted to placeholders:',
    docsMultimodalDesc2: 'A warning pops up on first selection. Images are replaced with [image] placeholder text.',
  }
};

function t(key) { return i18n[currentLang][key] || key; }

function applyI18n() {
  document.querySelectorAll('[data-i18n]').forEach(el => {
    const key = el.getAttribute('data-i18n');
    const translated = t(key);
    if (translated !== key) el.textContent = translated;
  });
  document.querySelectorAll('[data-i18n-placeholder]').forEach(el => {
    const key = el.getAttribute('data-i18n-placeholder');
    const translated = t(key);
    if (translated !== key) el.placeholder = translated;
  });
}

function initTheme() {
  const saved = localStorage.getItem('codex-cool-theme');
  const theme = saved || 'light';
  document.documentElement.setAttribute('data-theme', theme);
  updateThemeIcon(theme);
}

function toggleTheme() {
  const current = document.documentElement.getAttribute('data-theme') || 'light';
  const next = current === 'dark' ? 'light' : 'dark';
  document.documentElement.setAttribute('data-theme', next);
  localStorage.setItem('codex-cool-theme', next);
  updateThemeIcon(next);
}

function updateThemeIcon(theme) {
  const sun = document.getElementById('theme-icon-sun');
  const moon = document.getElementById('theme-icon-moon');
  const label = document.getElementById('theme-label');
  if (theme === 'light') {
    sun.style.display = 'none';
    moon.style.display = 'block';
    if (label) label.textContent = t('themeLight');
  } else {
    sun.style.display = 'block';
    moon.style.display = 'none';
    if (label) label.textContent = t('themeDark');
  }
}

function toggleLang() {
  currentLang = currentLang === 'zh' ? 'en' : 'zh';
  localStorage.setItem('codex-cool-lang', currentLang);
  document.getElementById('lang-label').textContent = t('langLabel');
  loadStatus();
  loadInjectStatus();
  loadClaudeInjectStatus();
  loadProviders();
  applyI18n();
}

function toggleCollapse(header) {
  header.parentElement.classList.toggle('open');
}

function showDocsModal() {
  document.getElementById('modal-docs').classList.add('active');
}

initTheme();

document.addEventListener('DOMContentLoaded', () => {
  document.getElementById('lang-label').textContent = t('langLabel');
  loadStatus();
  loadProviders();
  loadSettings();
  loadInjectStatus();
  loadClaudeInjectStatus();
  statusInterval = setInterval(loadStatus, 5000);
  applyI18n();
});

async function api(method, path, body) {
  const opts = { method, headers: { 'Content-Type': 'application/json' } };
  if (body) opts.body = JSON.stringify(body);
  const resp = await fetch('/api' + path, opts);
  const data = await resp.json();
  if (!resp.ok) {
    showToast(data.error || 'Request failed', 'error');
    throw data;
  }
  return data;
}

async function loadStatus() {
  try {
    const s = await api('GET', '/status');
    document.getElementById('stat-providers').textContent = s.providers.length;
    document.getElementById('stat-uptime').textContent = formatUptime(s.uptime);
    document.getElementById('stat-port').textContent = s.port;
    document.getElementById('proxy-url').textContent = `http://127.0.0.1:${s.port}/v1`;

    const sidebarDot = document.querySelector('.status-dot');
    const sidebarText = document.querySelector('.status-text');
    if (s.running) {
      sidebarDot.className = 'status-dot running';
      sidebarText.textContent = t('running');
    } else {
      sidebarDot.className = 'status-dot stopped';
      sidebarText.textContent = t('stopped');
    }

    renderDashboardProviders(s.providers);
    updateModelSelect(s.providers);
  } catch (e) { /* ignore */ }
}

function formatUptime(seconds) {
  const h = Math.floor(seconds / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  const s = seconds % 60;
  return `${String(h).padStart(2,'0')}:${String(m).padStart(2,'0')}:${String(s).padStart(2,'0')}`;
}

function renderDashboardProviders(providers) {
  const el = document.getElementById('dashboard-providers');
  if (!providers || providers.length === 0) {
    el.innerHTML = `<p class="text-secondary" style="padding:8px 0">${t('noProvider')}</p>`;
    return;
  }
  el.innerHTML = providers.map(p => `
    <div class="provider-row">
      <div class="provider-row-info">
        <span class="provider-row-name">${p.name}${p.is_default ? ` <span class="default-badge">${t('default')}</span>` : ''}</span>
        <span class="format-tag format-${p.api_format}">${p.api_format}</span>
        <span class="provider-row-meta">${Object.keys(p.models).length} ${t('models')}${p.circuit_breaker && p.circuit_breaker !== 'closed' ? ' · ' + t('circuitOpen') : ''}</span>
      </div>
      <div class="provider-row-actions">
        <button class="btn btn-ghost btn-sm" onclick="testProvider('${p.name}')">${t('test')}</button>
        <button class="btn btn-ghost btn-sm" onclick="editProvider('${p.name}')">${t('edit')}</button>
        <button class="btn btn-danger btn-sm" onclick="deleteProvider('${p.name}')">${t('delete')}</button>
      </div>
    </div>
  `).join('');
}

async function loadInjectStatus() {
  try {
    const status = await api('GET', '/inject/status');
    const badge = document.getElementById('inject-badge');
    const info = document.getElementById('inject-status-info');
    const btnInject = document.getElementById('btn-inject');
    const btnUninject = document.getElementById('btn-uninject');
    const injectForm = document.getElementById('inject-form');

    if (status.injected) {
      badge.className = 'badge badge-success';
      badge.textContent = t('injected');
      info.innerHTML = `
        <div style="background:var(--success-bg); border:1px solid rgba(34,197,94,0.3); border-radius:var(--radius-sm); padding:10px 12px; font-size:13px">
          <div style="color:var(--success); font-weight:600; margin-bottom:2px">${t('injectedMsg')}</div>
          <div style="color:var(--text-secondary); font-size:12px">${t('model')}: <code style="color:var(--accent-hover)">${status.current_model || '-'}</code> · Base URL: <code style="color:var(--accent-hover)">${status.current_base_url}</code></div>
        </div>
      `;
      btnInject.style.display = 'none';
      btnUninject.style.display = 'inline-flex';
      injectForm.style.display = 'none';
    } else {
      badge.className = 'badge badge-warning';
      badge.textContent = t('notInjected');
      if (status.config_exists) {
        info.innerHTML = `
          <div style="background:var(--bg-primary); border:1px solid var(--border); border-radius:var(--radius-sm); padding:10px 12px; font-size:12px; color:var(--text-secondary)">
            ${t('currentConfig')}: Provider=<code style="color:var(--accent-hover)">${status.current_provider || t('default')}</code> · ${t('model')}=<code style="color:var(--accent-hover)">${status.current_model || t('default')}</code>
            ${status.backup_exists ? ' · <span style="color:var(--success)">' + t('hasBackup') + '</span>' : ''}
          </div>
        `;
      } else {
        info.innerHTML = '';
      }
      btnInject.style.display = 'inline-flex';
      btnUninject.style.display = 'none';
      injectForm.style.display = 'block';
    }
  } catch (e) {
    const badge = document.getElementById('inject-badge');
    if (badge) badge.textContent = t('notInjected');
  }
}

function _renderModelCheckboxes(container, models, multi = true) {
  if (!container) return;

  const prevChecked = new Set();
  container.querySelectorAll(`.${container.id}-cb:checked`).forEach(cb => prevChecked.add(cb.value));

  if (models.length === 0) {
    container.innerHTML = `<p class="text-secondary" style="font-size:13px; padding:4px 0">${t('noProvider')}</p>`;
  } else {
    const inputType = multi ? 'checkbox' : 'radio';
    const inputName = container.id + '-input';
    container.innerHTML = models.map((m, i) => {
      const isChecked = prevChecked.size > 0 ? prevChecked.has(m.alias) : (i === 0);
      return `
      <label style="display:flex; align-items:center; gap:6px; padding:3px 0; font-size:13px; cursor:pointer">
        <input type="${inputType}" name="${inputName}" class="${container.id}-cb" value="${m.alias}" ${isChecked ? 'checked' : ''}>
        <span>${m.alias}${m.alias !== m.real ? ' → ' + m.real : ''} <span class="text-secondary">(${m.provider})</span></span>
      </label>`;
    }).join('');
  }
}

function updateModelSelect(providers) {
  const codexContainer = document.getElementById('codex-model-checkboxes');
  const claudeContainer = document.getElementById('claude-model-checkboxes');
  const allModels = [];
  const seen = new Set();
  for (const p of providers) {
    if (!p.enabled) continue;
    for (const [alias, real] of Object.entries(p.models || {})) {
      if (!seen.has(alias)) {
        seen.add(alias);
        allModels.push({ alias, real, provider: p.name });
      }
    }
  }

  const codexModels = allModels.filter(m => m.alias === m.real);
  _allModels = allModels;
  _renderModelCheckboxes(codexContainer, codexModels, false);
  _renderModelCheckboxes(claudeContainer, codexModels, true);
}

let _allModels = [];

const NON_MULTIMODAL_PROVIDERS = ['deepseek', 'kimi', 'zhipu', 'qwen', 'doubao'];

function _isNonMultimodalProvider(providerName) {
  return NON_MULTIMODAL_PROVIDERS.some(p => providerName.toLowerCase().includes(p));
}

function _checkMultimodalWarning(modelNames, callback) {
  const nonMultimodal = _allModels.filter(m => modelNames.includes(m.alias) && _isNonMultimodalProvider(m.provider));
  if (nonMultimodal.length === 0) { callback(); return; }
  const storageKey = 'codex-cool-multimodal-warned';
  if (localStorage.getItem(storageKey)) { callback(); return; }
  const providerNames = [...new Set(nonMultimodal.map(m => m.provider))].join(', ');
  const msg = t('multimodalWarning').replace('{providers}', providerNames);
  if (confirm(msg)) {
    localStorage.setItem(storageKey, '1');
    callback();
  }
}

async function doInject() {
  const selected = document.querySelector('#codex-model-checkboxes .codex-model-checkboxes-cb:checked');
  if (!selected) { showToast(t('selectModelErr'), 'error'); return; }
  const model = selected.value;
  _checkMultimodalWarning([model], async () => {
    try {
      const result = await api('POST', '/inject', { model });
      showToast(`${t('injectedSuccess')} ${result.model}`, 'success');
      loadInjectStatus();
    } catch (e) {}
  });
}

async function testInjectProxy() {
  try {
    const config = await api('GET', '/config');
    const defaultProvider = config.default_provider;
    if (!defaultProvider) {
      showToast(`${t('connectFail')} - ${t('noDefaultProvider')}`, 'warning');
      return;
    }
    showToast(t('testing'), 'info');
    const result = await api('POST', `/providers/${encodeURIComponent(defaultProvider)}/test`);
    if (result.ok) {
      showToast(`${defaultProvider}: ${t('connectOk')} - ${result.message || 'HTTP ' + result.status_code}`, 'success');
    } else {
      showToast(`${defaultProvider}: ${t('connectFail')} - ${result.message || 'HTTP ' + result.status_code}`, 'error');
    }
  } catch (e) {
    const msg = (e && e.error) ? e.error : (e && e.message) ? e.message : String(e);
    showToast(t('connectFail') + ': ' + msg, 'error');
  }
}

async function _fetchProviderModels(containerId, multi) {
  try {
    const config = await api('GET', '/config');
    const defaultProvider = config.default_provider;
    if (!defaultProvider) {
      showToast(`${t('connectFail')} - ${t('noDefaultProvider')}`, 'warning');
      return;
    }
    showToast(`${t('fetchingModels')} ${defaultProvider}...`, 'info');
    const result = await api('POST', `/providers/${encodeURIComponent(defaultProvider)}/models`);
    const remoteModels = result.models || [];
    if (remoteModels.length === 0) {
      showToast(`${t('noModelsFound')} (${defaultProvider})`, 'warning');
      return;
    }
    const container = document.getElementById(containerId);
    const models = remoteModels.map(id => ({ alias: id, real: id, provider: defaultProvider }));
    _renderModelCheckboxes(container, models, multi);
    showToast(t('modelsLoaded').replace('{n}', remoteModels.length) + ` (${defaultProvider})`, 'success');
  } catch (e) {
    const msg = (e && e.error) ? e.error : (e && e.message) ? e.message : String(e);
    showToast(`${t('fetchModelsFailed')}: ` + msg, 'error');
  }
}

async function loadInjectModels() {
  await _fetchProviderModels('codex-model-checkboxes', false);
}

async function doUninject() {
  if (!confirm(t('confirmRestore'))) return;
  try {
    const result = await api('POST', '/uninject');
    showToast(result.restored ? t('restored') : t('removed'), 'success');
    loadInjectStatus();
  } catch (e) {}
}

async function loadClaudeInjectStatus() {
  try {
    const status = await api('GET', '/claude/inject/status');
    const badge = document.getElementById('claude-inject-badge');
    const info = document.getElementById('claude-inject-status-info');
    const btnInject = document.getElementById('btn-claude-inject');
    const btnUninject = document.getElementById('btn-claude-uninject');
    const form = document.getElementById('claude-inject-form');

    if (status.injected) {
      badge.textContent = t('injected');
      badge.className = 'badge badge-success';
      btnInject.style.display = 'none';
      btnUninject.style.display = '';
      form.style.display = 'none';
      const modelsList = (status.current_models || []).join(', ') || '-';
      info.innerHTML = `
        <div style="background:var(--success-bg); border:1px solid rgba(34,197,94,0.3); border-radius:var(--radius-sm); padding:10px 12px; font-size:13px">
          <div style="color:var(--success); font-weight:600; margin-bottom:2px">${t('injectedMsg')}</div>
          <div style="color:var(--text-secondary); font-size:12px">${t('currentProxy')}: <code style="color:var(--accent-hover)">${status.current_base_url}</code> · ${t('models')}: <code style="color:var(--accent-hover)">${modelsList}</code></div>
        </div>
      `;
    } else if (status.config_exists) {
      badge.textContent = t('notInjected');
      badge.className = 'badge badge-warning';
      btnInject.style.display = '';
      btnUninject.style.display = 'none';
      form.style.display = 'block';
      const mode = status.current_deployment_mode || '1p';
      const modeLabel = mode === '3p' ? t('mode3p') : t('mode1p');
      const devWarning = !status.dev_mode_enabled ? `<div style="background:var(--warning-bg); border:1px solid rgba(245,158,11,0.3); border-radius:var(--radius-sm); padding:8px 12px; font-size:12px; color:var(--warning); margin-top:8px">⚠️ Developer Mode 未开启，注入时将自动启用</div>` : '';
      info.innerHTML = `
        <div style="background:var(--bg-primary); border:1px solid var(--border); border-radius:var(--radius-sm); padding:10px 12px; font-size:12px; color:var(--text-secondary)">
          ${t('currentConfig')}: 模式=<code style="color:var(--accent-hover)">${modeLabel}</code>
        </div>
        ${devWarning}
      `;
    } else {
      badge.textContent = t('noConfig');
      badge.className = 'badge badge-secondary';
      btnInject.style.display = '';
      btnUninject.style.display = 'none';
      form.style.display = 'block';
      info.innerHTML = `<span class="text-secondary">${t('noClaudeConfig')}</span>`;
    }
  } catch (e) {
    const badge = document.getElementById('claude-inject-badge');
    if (badge) badge.textContent = t('notInjected');
  }
}

async function doClaudeInject() {
  const checked = document.querySelectorAll('#claude-model-checkboxes .claude-model-checkboxes-cb:checked');
  const models = Array.from(checked).map(cb => cb.value);
  if (models.length === 0) { showToast(t('selectModelErr'), 'error'); return; }
  _checkMultimodalWarning(models, async () => {
    try {
      const result = await api('POST', '/claude/inject', { models });
      if (result.ok === false && result.error === 'permission_denied') {
        showToast(result.message || 'Permission denied', 'error');
        return;
      }
      showToast(`${t('claudePrefix')} ${t('injectedSuccess')} ${result.models.join(', ')}`, 'success');
      loadClaudeInjectStatus();
    } catch (e) {}
  });
}

async function loadClaudeInjectModels() {
  await _fetchProviderModels('claude-model-checkboxes', true);
}

async function doClaudeUninject() {
  if (!confirm(t('confirmClaudeRestore'))) return;
  try {
    const result = await api('POST', '/claude/uninject');
    showToast(result.restored ? t('restored') : t('removed'), 'success');
    loadClaudeInjectStatus();
  } catch (e) {}
}

const TEMPLATE_PRESETS = {
  deepseek: { name: 'deepseek', base_url: 'https://api.deepseek.com/v1', api_format: 'chat', models: 'deepseek-chat\ndeepseek-reasoner' },
  openai: { name: 'openai', base_url: 'https://api.openai.com/v1', api_format: 'chat', models: 'gpt-4o\ngpt-4o-mini\no1\no3-mini' },
  anthropic: { name: 'anthropic', base_url: 'https://api.anthropic.com/v1', api_format: 'anthropic', models: 'claude-sonnet-4-20250514\nclaude-3-5-haiku-20241022' },
  gemini: { name: 'gemini', base_url: 'https://generativelanguage.googleapis.com/v1beta/openai', api_format: 'chat', models: 'gemini-2.5-pro\ngemini-2.5-flash\ngemini-2.0-flash' },
  kimi: { name: 'kimi', base_url: 'https://api.moonshot.cn/v1', api_format: 'chat', models: 'moonshot-v1-8k\nmoonshot-v1-32k\nmoonshot-v1-128k' },
  zhipu: { name: 'zhipu', base_url: 'https://open.bigmodel.cn/api/paas/v4', api_format: 'chat', models: 'glm-4-plus\nglm-4-flash\nglm-4-long' },
  qwen: { name: 'qwen', base_url: 'https://dashscope.aliyuncs.com/compatible-mode/v1', api_format: 'chat', models: 'qwen-turbo\nqwen-plus\nqwen-max' },
  doubao: { name: 'doubao', base_url: 'https://ark.cn-beijing.volces.com/api/v3', api_format: 'chat', models: '' },
};

function fillTemplate(key, el) {
  const preset = TEMPLATE_PRESETS[key];
  if (!preset) return;
  document.querySelectorAll('.quick-tag').forEach(e => e.classList.remove('active'));
  if (el) el.classList.add('active');
  document.getElementById('provider-name').value = preset.name;
  document.getElementById('provider-base-url').value = preset.base_url;
  document.getElementById('provider-api-format').value = preset.api_format;
  document.getElementById('provider-models').value = preset.models;
  document.getElementById('provider-name').disabled = false;
  document.getElementById('model-list-container').style.display = 'none';
  document.getElementById('btn-select-all-models').style.display = 'none';
}

async function fetchModels() {
  const baseUrl = document.getElementById('provider-base-url').value.trim();
  const apiKey = document.getElementById('provider-api-key').value.trim();
  const apiFormat = document.getElementById('provider-api-format').value;
  if (!baseUrl) { showToast(t('fillBaseUrl'), 'error'); return; }

  const btn = document.getElementById('btn-fetch-models');
  btn.disabled = true;
  btn.textContent = '获取中...';

  try {
    const result = await api('POST', '/fetch-models', { base_url: baseUrl, api_key: apiKey, api_format: apiFormat, provider_name: editingProvider || '' });
    const models = result.models || [];
    if (models.length === 0) {
      showToast(`${t('noModelsFound')} (${defaultProvider})`, 'error');
      return;
    }

    const container = document.getElementById('model-checkboxes');
    const existingText = document.getElementById('provider-models').value.trim();
    const existingModels = new Set(existingText.split('\n').map(l => l.split('=')[0].trim()).filter(Boolean));

    container.innerHTML = models.map(m => `
      <label style="display:flex; align-items:center; gap:6px; padding:3px 0; font-size:13px; cursor:pointer">
        <input type="checkbox" class="model-cb" value="${m}" ${existingModels.has(m) ? 'checked' : ''}>
        <span>${m}</span>
      </label>
    `).join('');

    document.getElementById('model-list-container').style.display = '';
    document.getElementById('btn-select-all-models').style.display = '';

    container.querySelectorAll('.model-cb').forEach(cb => {
      cb.addEventListener('change', syncModelsFromCheckboxes);
    });
    syncModelsFromCheckboxes();
  } catch (e) {
    showToast(`${t('fetchModelsFailed')}: ` + ((e && e.error) ? e.error : (e && e.message) ? e.message : String(e)), 'error');
  } finally {
    btn.disabled = false;
    btn.textContent = '自动获取模型';
  }
}

function syncModelsFromCheckboxes() {
  const checked = document.querySelectorAll('#model-checkboxes .model-cb:checked');
  const lines = Array.from(checked).map(cb => cb.value);
  document.getElementById('provider-models').value = lines.join('\n');
}

function toggleAllModels() {
  const cbs = document.querySelectorAll('#model-checkboxes .model-cb');
  const allChecked = Array.from(cbs).every(cb => cb.checked);
  cbs.forEach(cb => cb.checked = !allChecked);
  syncModelsFromCheckboxes();
}

async function loadProviders() {
  try {
    const providers = await api('GET', '/providers');
    const config = await api('GET', '/config');
    const status = await api('GET', '/status');
    const merged = providers.map(p => {
      const sp = status.providers.find(s => s.name === p.name);
      return { ...p, circuit_breaker: sp ? sp.circuit_breaker : 'closed' };
    });
    renderDashboardProviders(merged);
    const sel = document.getElementById('setting-default-provider');
    sel.innerHTML = merged.map(p =>
      `<option value="${p.name}" ${p.name === config.default_provider ? 'selected' : ''}>${p.name}</option>`
    ).join('');
  } catch (e) {}
}

async function loadSettings() {
  try {
    const config = await api('GET', '/config');
    document.getElementById('setting-host').value = config.host;
    document.getElementById('setting-port').value = config.port;
    document.getElementById('setting-log-level').value = config.log_level;
  } catch (e) {}
}

function showAddProviderModal() {
  editingProvider = null;
  document.getElementById('modal-title').textContent = t('addProviderTitle');
  document.getElementById('provider-name').value = '';
  document.getElementById('provider-name').disabled = false;
  document.getElementById('provider-base-url').value = '';
  document.getElementById('provider-api-key').value = '';
  document.getElementById('provider-api-format').value = 'chat';
  document.getElementById('provider-models').value = '';
  document.getElementById('provider-enabled').checked = true;
  document.querySelectorAll('.quick-tag').forEach(el => el.classList.remove('active'));
  document.getElementById('quick-tags').style.display = '';
  document.getElementById('model-list-container').style.display = 'none';
  document.getElementById('btn-select-all-models').style.display = 'none';
  document.getElementById('model-checkboxes').innerHTML = '';
  document.getElementById('modal-add-provider').classList.add('active');
}

async function editProvider(name) {
  try {
    const providers = await api('GET', '/providers');
    const p = providers.find(x => x.name === name);
    if (!p) return;
    editingProvider = name;
    document.getElementById('modal-title').textContent = t('editProviderTitle');
    document.getElementById('provider-name').value = p.name;
    document.getElementById('provider-name').disabled = true;
    document.getElementById('provider-base-url').value = p.base_url;
    document.getElementById('provider-api-key').value = '';
    document.getElementById('provider-api-format').value = p.api_format;
    const models = Object.entries(p.models).map(([k,v]) => k === v ? k : `${k}=${v}`).join('\n');
    document.getElementById('provider-models').value = models;
    document.getElementById('provider-enabled').checked = p.enabled;
    document.getElementById('quick-tags').style.display = 'none';
    document.getElementById('model-list-container').style.display = 'none';
    document.getElementById('btn-select-all-models').style.display = 'none';
    document.getElementById('model-checkboxes').innerHTML = '';
    document.getElementById('modal-add-provider').classList.add('active');
  } catch (e) {}
}

async function saveProvider() {
  const name = document.getElementById('provider-name').value.trim();
  const baseUrl = document.getElementById('provider-base-url').value.trim();
  const apiKey = document.getElementById('provider-api-key').value.trim();
  const apiFormat = document.getElementById('provider-api-format').value;
  const modelsText = document.getElementById('provider-models').value.trim();
  const enabled = document.getElementById('provider-enabled').checked;
  if (!name || !baseUrl) { showToast(t('nameRequired'), 'error'); return; }
  const models = {};
  if (modelsText) {
    modelsText.split('\n').forEach(line => {
      line = line.trim();
      if (!line) return;
      if (line.includes('=')) {
        const [alias, real] = line.split('=', 2);
        models[alias.trim()] = real.trim();
      } else {
        models[line] = line;
      }
    });
  }
  try {
    if (editingProvider) {
      const body = { base_url: baseUrl, api_format: apiFormat, models, enabled };
      if (apiKey) body.api_key = apiKey;
      await api('PUT', '/providers/' + editingProvider, body);
      showToast(t('providerUpdated'), 'success');
    } else {
      await api('POST', '/providers', { name, base_url: baseUrl, api_key: apiKey, api_format: apiFormat, models, enabled });
      showToast(t('providerAdded'), 'success');
    }
    closeModal();
    loadProviders();
    loadStatus();
  } catch (e) {}
}

async function deleteProvider(name) {
  if (!confirm(`${t('confirmDelete')} "${name}"?`)) return;
  try {
    await api('DELETE', '/providers/' + name);
    showToast(t('providerDeleted'), 'success');
    loadProviders();
    loadStatus();
  } catch (e) {}
}

async function testProvider(name) {
  showToast(t('testing'), 'info');
  try {
    const result = await api('POST', '/providers/' + name + '/test');
    showToast(result.ok ? `${t('connectOk')} (HTTP ${result.status_code})` : `${t('connectFail')} (HTTP ${result.status_code})`, result.ok ? 'success' : 'error');
  } catch (e) {}
}


async function saveSettings() {
  const host = document.getElementById('setting-host').value.trim();
  const port = parseInt(document.getElementById('setting-port').value);
  const logLevel = document.getElementById('setting-log-level').value;
  const defaultProvider = document.getElementById('setting-default-provider').value;
  try {
    const result = await api('PUT', '/config', { host, port, log_level: logLevel, default_provider: defaultProvider });
    showToast(t('saved') + (result.restart_required ? t('restartRequired') : ''), 'success');
    loadStatus();
  } catch (e) {}
}

function closeModal() {
  document.querySelectorAll('.modal-overlay').forEach(m => m.classList.remove('active'));
  editingProvider = null;
}

function closeModalOnOverlay(e) {
  if (e.target.classList.contains('modal-overlay')) closeModal();
}

function copyText(elementId) {
  const text = document.getElementById(elementId).textContent;
  navigator.clipboard.writeText(text).then(() => {
    showToast(t('copied'), 'success');
  }).catch(() => {
    const ta = document.createElement('textarea');
    ta.value = text;
    document.body.appendChild(ta);
    ta.select();
    document.execCommand('copy');
    document.body.removeChild(ta);
    showToast(t('copied'), 'success');
  });
}

function showToast(message, type) {
  const container = document.getElementById('toast-container');
  const toast = document.createElement('div');
  toast.className = 'toast toast-' + (type || 'info');
  toast.textContent = message;
  container.appendChild(toast);
  setTimeout(() => { if (toast.parentNode) toast.remove(); }, 3000);
}
