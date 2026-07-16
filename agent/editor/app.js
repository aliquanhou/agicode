/* AgiCode Web — Full web-based UI with Monaco Editor + SSE */

(function () {
  'use strict';

  // ── State ──
  let chatEditor, chatModel, diffEditor, sseSource;
  let isAtBottom = true, newMsgCount = 0, busy = false;
  let lastInput = '', thinkingStart = 0;

  // ── Monaco Theme ──
  const THEME = {
    base: 'vs-dark', inherit: true,
    rules: [
      { token: 'user', foreground: '4CAF50', fontStyle: 'bold' },
      { token: 'assistant', foreground: 'E0E0E0' },
      { token: 'thinking', foreground: '888888', fontStyle: 'italic' },
      { token: 'tool', foreground: 'FF9800', fontStyle: 'bold' },
      { token: 'result', foreground: 'FFB74D' },
      { token: 'error', foreground: 'F44336', fontStyle: 'bold' },
      { token: 'system', foreground: '64B5F6' },
      { token: 'dim', foreground: '666666' },
      { token: 'sep', foreground: '333333' },
    ],
    colors: {
      'editor.background': '#1e1e1e', 'editor.foreground': '#e0e0e0',
      'editor.lineHighlightBackground': '#2a2a2a',
      'editor.selectionBackground': '#264f78',
      'editorWidget.background': '#252526',
      'input.background': '#3c3c3c', 'input.foreground': '#e0e0e0',
    },
  };

  // ── Chat Token Provider ──
  class ChatTokenProvider {
    constructor() {
      this.map = {};
      for (const [k, v] of Object.entries(STYLES)) {
        if (v.prefix) this.map[v.prefix] = v.token;
      }
    }
    getInitialState() { return 0; }
    tokenize(line, state) {
      for (const [prefix, token] of Object.entries(this.map)) {
        if (line.startsWith(prefix)) {
          return { tokens: [{ startIndex: 0, scopes: token }, { startIndex: line.length, scopes: token }], endState: 0 };
        }
      }
      return { tokens: [{ startIndex: 0, scopes: 'assistant' }, { startIndex: line.length, scopes: 'assistant' }], endState: 0 };
    }
  }

  const STYLES = {
    user: { prefix: '//[U] ', token: 'user' },
    assistant: { prefix: '', token: 'assistant' },
    thinking: { prefix: '//[T] ', token: 'thinking' },
    tool: { prefix: '//[!] ', token: 'tool' },
    result: { prefix: '//[R] ', token: 'result' },
    error: { prefix: '//[E] ', token: 'error' },
    system: { prefix: '//[S] ', token: 'system' },
    dim: { prefix: '//[D] ', token: 'dim' },
    sep: { prefix: '//[-] ', token: 'sep' },
  };

  // ── Init Monaco ──
  function initMonaco() {
    require.config({ paths: { vs: 'https://cdn.jsdelivr.net/npm/monaco-editor@0.52.2/min/vs' } });
    require(['vs/editor/editor.main'], function () {
      monaco.editor.defineTheme('agicode', THEME);
      monaco.languages.register({ id: 'agicode-chat' });
      monaco.languages.setTokensProvider('agicode-chat', new ChatTokenProvider());

      chatModel = monaco.editor.createModel('', 'agicode-chat');
      chatEditor = monaco.editor.create(document.getElementById('chat-editor'), {
        model: chatModel, theme: 'agicode', language: 'agicode-chat',
        readOnly: true, fontSize: 13, fontFamily: 'Consolas, "Microsoft YaHei", monospace',
        lineNumbers: 'off', minimap: { enabled: false }, wordWrap: 'on',
        scrollBeyondLastLine: false, contextmenu: false, folding: false,
        lineDecorationsWidth: 0, glyphMargin: false,
        padding: { top: 4, bottom: 4 }, automaticLayout: true,
        scrollbar: { verticalScrollbarSize: 8, alwaysConsumeMouseWheel: false },
        suggest: { showWords: false }, quickSuggestions: false,
      });

      diffEditor = monaco.editor.createDiffEditor(document.getElementById('diff-editor'), {
        theme: 'agicode', fontSize: 13, fontFamily: 'Consolas, "Microsoft YaHei", monospace',
        readOnly: true, renderSideBySide: false, minimap: { enabled: false },
        lineNumbers: 'on', wordWrap: 'on', scrollBeyondLastLine: false, automaticLayout: true,
      });

      chatEditor.onDidScrollChange(function (e) {
        var h = chatEditor.getContentHeight(), v = chatEditor.getLayoutInfo().height;
        isAtBottom = (e.scrollTop + v >= h - 30);
        if (!isAtBottom && newMsgCount > 0) showScrollIndicator();
        else hideScrollIndicator();
      });

      // Input: Enter to send, Ctrl+Enter for newline
      document.getElementById('input-box').addEventListener('keydown', function (e) {
        if (e.key === 'Enter' && !e.ctrlKey && !e.shiftKey) { e.preventDefault(); sendMessage(); }
      });

      // Tab switching
      document.querySelectorAll('.tab').forEach(function (t) {
        t.addEventListener('click', function () {
          document.querySelectorAll('.tab').forEach(function (x) { x.classList.remove('active'); });
          document.querySelectorAll('.tab-content').forEach(function (x) { x.classList.remove('active'); });
          t.classList.add('active');
          document.getElementById('tab-' + t.dataset.tab).classList.add('active');
        });
      });

      // Populate tool panel
      buildToolPanel();

      // Connect SSE
      connectSSE();

      // Fetch context
      fetchContext();
    });
  }

  // ── Tool Panel ──
  const CATEGORIES = {
    '📂 文件系统': { color: '#42A5F5', tools: ['read', 'write', 'edit', 'glob', 'grep'] },
    '⚡ 命令执行': { color: '#EF5350', tools: ['bash', 'background'] },
    '🖥️ 系统控制': { color: '#AB47BC', tools: ['process', 'service', 'registry', 'gui', 'monitor'] },
    '🧠 网络/浏览器': { color: '#FFA726', tools: ['web', 'web_search', 'browser'] },
    '🔬 代码分析': { color: '#FF7043', tools: ['ast', 'dep_graph', 'call_chain'] },
    '📋 工具链': { color: '#66BB6A', tools: ['plan', 'task', 'subagent', 'mcp'] },
  };
  const TOOL_ICONS = { read:'📖',write:'✏️',edit:'🔧',glob:'🔍',grep:'🔎',bash:'💻',background:'⏳',process:'⚙️',service:'⚙️',registry:'📋',gui:'🖱️',monitor:'📊',web:'🌐',web_search:'🔍',browser:'🌍',ast:'🌳',dep_graph:'🕸',call_chain:'🔗',plan:'📋',task:'✅',subagent:'🧠',mcp:'🔌' };

  function buildToolPanel() {
    var container = document.getElementById('tab-tools');
    for (var [catName, cat] of Object.entries(CATEGORIES)) {
      var hdr = document.createElement('div');
      hdr.className = 'tool-cat';
      hdr.style.color = cat.color;
      hdr.textContent = catName;
      container.appendChild(hdr);
      for (var i = 0; i < cat.tools.length; i += 2) {
        var row = document.createElement('div');
        row.className = 'tool-row';
        for (var j = i; j < Math.min(i + 2, cat.tools.length); j++) {
          var name = cat.tools[j];
          var card = document.createElement('div');
          card.className = 'tool-card';
          card.id = 'tool-' + name;
          card.innerHTML = '<span class="tool-dot" id="dot-' + name + '">○</span><span class="tool-name">' + (TOOL_ICONS[name]||'⚡') + ' ' + name + '</span><span class="tool-desc">' + name + '</span>';
          row.appendChild(card);
        }
        container.appendChild(row);
      }
    }
  }

  function setToolStatus(name, status) {
    var dot = document.getElementById('dot-' + name);
    if (!dot) return;
    var dots = { idle: '○', running: '●', done: '✓', error: '✗' };
    var colors = { idle: '#555', running: '#FFC107', done: '#4CAF50', error: '#F44336' };
    dot.textContent = dots[status] || '○';
    dot.className = 'tool-dot ' + status;
  }

  function logActivity(tool, status, detail) {
    var log = document.getElementById('activity-log');
    var ts = new Date().toLocaleTimeString();
    var icons = { running: '▶', done: '✓', error: '✗' };
    var line = document.createElement('div');
    line.className = 'log-line ' + status;
    line.textContent = ts + ' ' + (icons[status]||'·') + ' ' + tool + (detail ? '  ' + detail.substring(0, 80) : '');
    log.appendChild(line);
    log.scrollTop = log.scrollHeight;
  }

  // ── Append text to Monaco ──
  function appendText(text, style) {
    if (!chatEditor) return;
    var info = STYLES[style] || STYLES.assistant;
    var prefix = info.prefix;
    var lines = text.split('\n');
    var fullText = lines.map(function (l) { return prefix + l; }).join('\n');
    chatEditor.executeEdits('append', [
      { range: getEndRange(), text: fullText, forceMoveMarkers: true },
    ]);
    if (isAtBottom) chatEditor.setScrollTop(chatEditor.getContentHeight());
  }

  function appendLine(text, style) { appendText(text + '\n', style); }

  function getEndRange() {
    var lineCount = chatModel.getLineCount();
    var lastLine = chatModel.getLineContent(lineCount);
    return new monaco.Range(lineCount, lastLine.length + 1, lineCount, lastLine.length + 1);
  }

  function appendToolStart(name, input) {
    var icon = TOOL_ICONS[name] || '⚡';
    var path = (input && (input.file_path || input.command || input.url || input.pattern || input.query)) || '';
    var line = '  ' + icon + ' ' + name + (path ? '  ' + path : '');
    appendLine(line, 'tool');
    // Extra params
    if (input) {
      var extra = {};
      for (var k in input) {
        if (!['file_path','command','url','pattern','query','path','content'].includes(k) && input[k]) {
          extra[k] = input[k];
        }
      }
      var keys = Object.keys(extra);
      if (keys.length) {
        var meta = keys.map(function (k) { return k + '=' + extra[k]; }).join(' ');
        if (meta.length > 150) meta = meta.substring(0, 150) + '...';
        appendLine('    ' + meta, 'dim');
      }
    }
  }

  function appendToolResult(result, toolName, elapsed) {
    var isErr = /错误|error|失败|❌/i.test(result.substring(0, 100));
    var icon = TOOL_ICONS[toolName] || '⚡';
    if (isErr) {
      appendLine('    ' + icon + ' ' + toolName + ' ❌ 失败' + (elapsed||''), 'error');
      var s = result.substring(0, 200).replace(/\n/g, ' ');
      appendLine('    ' + s, 'error');
    } else {
      appendLine('    ' + icon + ' ' + toolName + ' ✅ 完成' + (elapsed||''), 'result');
    }
    // Diff detection
    if (result.includes('--- DIFF START ---')) {
      openDiffFromUnified(result);
    }
  }

  // ── Diff ──
  function parseUnifiedDiff(diffText) {
    var cleaned = diffText;
    var si = cleaned.indexOf('--- DIFF START ---');
    var ei = cleaned.indexOf('--- DIFF END ---');
    if (si >= 0) cleaned = cleaned.substring(si + 18, ei >= 0 ? ei : undefined);
    if (ei >= 0) cleaned = cleaned.substring(0, ei);
    var orig = [], mod = [];
    cleaned.split('\n').forEach(function (line) {
      if (line.startsWith('--- ') || line.startsWith('+++ ') || line.startsWith('@@ ')) return;
      if (line.startsWith('\\ ')) return;
      if (line.startsWith('-')) orig.push(line.substring(1));
      else if (line.startsWith('+')) mod.push(line.substring(1));
      else { var ctx = line.startsWith(' ') ? line.substring(1) : line; orig.push(ctx); mod.push(ctx); }
    });
    return { original: orig.join('\n'), modified: mod.join('\n') };
  }

  function openDiffFromUnified(diffText, filePath) {
    if (!diffEditor) return;
    var result = parseUnifiedDiff(diffText);
    if (!result.original && !result.modified) { appendText(diffText, 'result'); return; }
    var lang = detectLanguage(filePath);
    var om = monaco.editor.createModel(result.original, lang);
    var mm = monaco.editor.createModel(result.modified, lang);
    diffEditor.setModel({ original: om, modified: mm });
    document.getElementById('chat-container').className = 'hidden';
    document.getElementById('diff-container').className = 'active';
    var fp = document.getElementById('diff-filepath');
    if (fp) fp.textContent = filePath || '';
    if (chatEditor) setTimeout(function () { chatEditor.layout(); }, 100);
  }

  function closeDiff() {
    if (!diffEditor) return;
    var m = diffEditor.getModel();
    if (m) { if (m.original) m.original.dispose(); if (m.modified) m.modified.dispose(); diffEditor.setModel({ original: null, modified: null }); }
    document.getElementById('diff-container').className = 'hidden';
    document.getElementById('chat-container').className = 'active';
    if (chatEditor) { chatEditor.layout(); setTimeout(function () { chatEditor.setScrollTop(chatEditor.getContentHeight()); }, 100); }
  }

  function detectLanguage(fp) {
    if (!fp) return 'plaintext';
    var ext = fp.split('.').pop().toLowerCase();
    var map = { py:'python',js:'javascript',ts:'typescript',jsx:'javascript',tsx:'typescript',html:'html',css:'css',json:'json',md:'markdown',yaml:'yaml',yml:'yaml',toml:'ini',c:'c',cpp:'cpp',java:'java',rs:'rust',go:'go',sh:'shell',ps1:'powershell',bat:'bat' };
    return map[ext] || 'plaintext';
  }

  // ── SSE ──
  function connectSSE() {
    sseSource = new EventSource('/api/stream');
    sseSource.addEventListener('text', function (e) { try { var d = JSON.parse(e.data); if (d.delta) appendText(d.delta, 'assistant'); } catch (x) {} });
    sseSource.addEventListener('thought', function (e) { try { var d = JSON.parse(e.data); if (d.delta && d.delta.length > 20) appendLine('  🧠 思考: ' + d.delta.substring(0, 100) + '...', 'thinking'); } catch (x) {} });
    sseSource.addEventListener('tool', function (e) {
      try {
        var d = JSON.parse(e.data);
        if (d.subtype === 'start') { setToolStatus(d.tool_name, 'running'); logActivity(d.tool_name, 'running', ''); }
        if (d.subtype === 'result') {
          setToolStatus(d.tool_name, d.error_type ? 'error' : 'done');
          logActivity(d.tool_name, d.error_type ? 'error' : 'done', (d.result || '').substring(0, 80));
        }
      } catch (x) {}
    });
    sseSource.addEventListener('error', function (e) { try { var d = JSON.parse(e.data); if (d.message) appendLine('错误: ' + d.message, 'error'); } catch (x) {} });
    sseSource.addEventListener('session', function (e) {
      try {
        var d = JSON.parse(e.data);
        if (d.subtype === 'end') {
          busy = false;
          setUIState(false);
          document.getElementById('status-text').textContent = 'Idle';
          document.getElementById('status-text').style.color = '#4CAF50';
          if (thinkingStart > 0) { var sec = (Date.now() - thinkingStart) / 1000; if (sec >= 0.5) appendLine('  🧠 思考 ' + sec.toFixed(1) + 's', 'dim'); thinkingStart = 0; }
        }
      } catch (x) {}
    });
    sseSource.onerror = function () {};
  }

  // ── Send ──
  function sendMessage() {
    if (busy) return;
    var input = document.getElementById('input-box');
    var text = input.value.trim();
    if (!text) return;
    lastInput = text;
    input.value = '';
    appendLine('>>> ' + text, 'user');
    thinkingStart = Date.now();
    busy = true;
    setUIState(true);
    document.getElementById('status-text').textContent = 'Thinking';
    document.getElementById('status-text').style.color = '#FF9800';
    fetch('/api/send', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ text: text }) }).catch(function (e) { appendLine('发送失败: ' + e, 'error'); busy = false; setUIState(false); });
  }

  function stopAgent() {
    if (!busy) return;
    fetch('/api/stop', { method: 'POST' });
    busy = false; setUIState(false);
    appendLine('  ⏹ 已终止', 'system');
    document.getElementById('status-text').textContent = 'Idle';
    document.getElementById('status-text').style.color = '#4CAF50';
  }

  function retryLast() {
    if (!lastInput) return;
    document.getElementById('input-box').value = lastInput;
    sendMessage();
  }

  function clearChat() {
    if (chatModel) chatModel.setValue('');
    document.getElementById('activity-log').innerHTML = '';
    fetch('/api/clear', { method: 'POST' });
  }

  function setUIState(b) {
    var btn = document.getElementById('send-btn');
    btn.disabled = b;
    btn.textContent = b ? '工作中...' : '发送';
    document.getElementById('input-box').disabled = b;
  }

  function scrollToBottom() {
    if (!chatEditor) return;
    chatEditor.setScrollTop(chatEditor.getContentHeight());
    isAtBottom = true;
    hideScrollIndicator();
  }

  function showScrollIndicator() {
    var el = document.getElementById('scroll-indicator');
    if (el) el.style.display = 'block';
  }
  function hideScrollIndicator() {
    var el = document.getElementById('scroll-indicator');
    if (el) el.style.display = 'none';
  }

  // ── Context / Settings ──
  function fetchContext() {
    fetch('/api/context').then(function (r) { return r.json(); }).then(function (d) {
      if (d.provider) document.getElementById('provider-label').textContent = d.provider;
    }).catch(function () {});
  }

  function openSettings() { document.getElementById('settings-modal').classList.remove('hidden'); }
  function closeSettings() { document.getElementById('settings-modal').classList.add('hidden'); }
  function saveSettings() {
    closeSettings();
    document.getElementById('provider-label').textContent = document.getElementById('settings-provider').value;
  }

  // ── Expose to HTML ──
  window.sendMessage = sendMessage;
  window.stopAgent = stopAgent;
  window.retryLast = retryLast;
  window.clearChat = clearChat;
  window.scrollToBottom = scrollToBottom;
  window.openDiffFromUnified = openDiffFromUnified;
  window.closeDiff = closeDiff;
  window.openSettings = openSettings;
  window.closeSettings = closeSettings;
  window.saveSettings = saveSettings;

  // ── Start ──
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', initMonaco);
  else initMonaco();

})();
