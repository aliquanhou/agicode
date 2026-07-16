/* AgiCode Web — Monaco Editor + SSE + Config API */

(function () {
  'use strict';

  let chatEditor, chatModel, diffEditor;
  let isAtBottom = true, newMsgCount = 0, busy = false;
  let lastInput = '', thinkingStart = 0;

  const TOOL_ICONS = { read:'📖',write:'✏️',edit:'🔧',glob:'🔍',grep:'🔎',bash:'💻',background:'⏳',process:'⚙️',service:'⚙️',registry:'📋',gui:'🖱️',monitor:'📊',web:'🌐',web_search:'🔍',browser:'🌍',ast:'🌳',dep_graph:'🕸',call_chain:'🔗',plan:'📋',task:'✅',subagent:'🧠',mcp:'🔌' };

  const AGICODE_THEME = {
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
    ],
    colors: {
      'editor.background':'#1e1e1e','editor.foreground':'#e0e0e0',
      'editor.lineHighlightBackground':'#2a2a2a','editor.selectionBackground':'#264f78',
    },
  };

  var STYLE_PREFIXES = {};
  function initStylePrefixes() {
    var map = { user:'[USER]',assistant:'',thinking:'[THINK]',tool:'[TOOL]',result:'[RESULT]',error:'[ERROR]',system:'[SYS]',dim:'[DIM]',sep:'[SEP]' };
    for (var k in map) STYLE_PREFIXES[k] = { prefix: map[k] ? '//'+map[k]+' ' : '', token: k };
  }
  initStylePrefixes();

  class ChatTokenizer {
    getInitialState() { return 0; }
    tokenize(line) {
      for (var k in STYLE_PREFIXES) {
        var p = STYLE_PREFIXES[k].prefix;
        if (p && line.startsWith(p)) return { tokens: [{startIndex:0,scopes:k},{startIndex:line.length,scopes:k}], endState:0 };
      }
      return { tokens: [{startIndex:0,scopes:'assistant'},{startIndex:line.length,scopes:'assistant'}], endState:0 };
    }
  }

  function initMonaco() {
    require.config({ paths: { vs: 'https://cdn.jsdelivr.net/npm/monaco-editor@0.52.2/min/vs' } });
    require(['vs/editor/editor.main'], function () {
      monaco.editor.defineTheme('agicode', AGICODE_THEME);
      monaco.languages.register({ id: 'agicode-chat' });
      monaco.languages.setTokensProvider('agicode-chat', new ChatTokenizer());

      chatModel = monaco.editor.createModel('', 'agicode-chat');
      chatEditor = monaco.editor.create(document.getElementById('chat-editor'), {
        model: chatModel, theme: 'agicode', language: 'agicode-chat',
        readOnly: true, fontSize: 13, fontFamily: 'Consolas, "Microsoft YaHei", monospace',
        lineNumbers: 'off', minimap: { enabled: false }, wordWrap: 'on',
        scrollBeyondLastLine: false, contextmenu: false, folding: false,
        lineDecorationsWidth: 0, glyphMargin: false,
        padding: { top: 4, bottom: 4 }, automaticLayout: true,
        scrollbar: { verticalScrollbarSize: 8, alwaysConsumeMouseWheel: false },
      });

      diffEditor = monaco.editor.createDiffEditor(document.getElementById('diff-editor'), {
        theme: 'agicode', fontSize: 13, fontFamily: 'Consolas, "Microsoft YaHei", monospace',
        readOnly: true, renderSideBySide: false, minimap: { enabled: false },
        lineNumbers: 'on', wordWrap: 'on', automaticLayout: true,
      });

      chatEditor.onDidScrollChange(function (e) {
        var h = chatEditor.getContentHeight(), v = chatEditor.getLayoutInfo().height;
        isAtBottom = (e.scrollTop + v >= h - 30);
        if (!isAtBottom && newMsgCount > 0) showScrollIndicator();
        else hideScrollIndicator();
      });

      document.getElementById('input-box').addEventListener('keydown', function (e) {
        if (e.key === 'Enter' && !e.ctrlKey && !e.shiftKey) { e.preventDefault(); sendMessage(); }
      });
      document.querySelectorAll('.tab').forEach(function (t) {
        t.addEventListener('click', function () {
          document.querySelectorAll('.tab, .tab-content').forEach(function (x) { x.classList.remove('active'); });
          t.classList.add('active');
          document.getElementById('tab-' + t.dataset.tab).classList.add('active');
        });
      });

      // Load tools
      buildToolPanel();

      // Load initial config
      loadConfig();

      // Connect SSE
      connectSSE();
    });
  }

  // ── Config API ──

  function loadConfig() {
    fetch('/api/config').then(function (r) { return r.json(); }).then(function (d) {
      document.getElementById('settings-provider').value = d.provider || 'DeepSeek';
      document.getElementById('settings-key').value = d.api_key || '';
      document.getElementById('settings-model').value = d.model || '';
      document.getElementById('provider-label').textContent = d.provider || '—';
      if (!d.api_key) {
        appendLine('⚠️ 请点击右上角 ⚙ Settings 配置 API Key', 'system');
      }
    }).catch(function () {});
  }

  function openSettings() {
    // Reload current config
    fetch('/api/config').then(function (r) { return r.json(); }).then(function (d) {
      document.getElementById('settings-provider').value = d.provider || 'DeepSeek';
      document.getElementById('settings-key').value = '';
      document.getElementById('settings-model').value = d.model || '';
    }).catch(function () {});
    document.getElementById('settings-modal').classList.remove('hidden');
  }

  function closeSettings() { document.getElementById('settings-modal').classList.add('hidden'); }

  function saveSettings() {
    var provider = document.getElementById('settings-provider').value;
    var key = document.getElementById('settings-key').value.trim();
    var model = document.getElementById('settings-model').value.trim();
    if (!key) { appendLine('⚠️ 请输入 API Key', 'system'); return; }
    fetch('/api/config', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ provider: provider, api_key: key, model: model }),
    }).then(function (r) { return r.json(); }).then(function (d) {
      if (d.status === 'ok') {
        document.getElementById('provider-label').textContent = provider;
        appendLine('✅ 配置已保存: ' + provider + ' / ' + model, 'system');
      } else {
        appendLine('❌ 保存失败: ' + (d.message || ''), 'error');
      }
    }).catch(function (e) { appendLine('❌ 保存失败: ' + e, 'error'); });
    closeSettings();
  }

  // ── SSE ──

  function connectSSE() {
    var sse = new EventSource('/api/stream');
    sse.addEventListener('text', function (e) {
      try { var d = JSON.parse(e.data); if (d.delta) appendText(d.delta, 'assistant'); }
      catch (x) { if (e.data) appendText(e.data, 'assistant'); }
    });
    sse.addEventListener('thought', function (e) {
      try { var d = JSON.parse(e.data); if (d.delta && d.delta.length > 20) appendLine('  🧠 ' + d.delta.substring(0,120) + '...', 'thinking'); }
      catch (x) {}
    });
    sse.addEventListener('tool', function (e) {
      try {
        var d = JSON.parse(e.data);
        if (d.subtype === 'start') { setToolStatus(d.tool_name, 'running'); logActivity(d.tool_name, 'running'); }
        if (d.subtype === 'result') { setToolStatus(d.tool_name, d.error_type ? 'error' : 'done'); logActivity(d.tool_name, d.error_type ? 'error' : 'done'); }
      } catch (x) {}
    });
    sse.addEventListener('error', function (e) {
      try { var d = JSON.parse(e.data);
        if (d.message) appendLine('❌ ' + d.message, 'error');
        if (d.delta) appendText(d.delta, 'error');
      } catch (x) { if (e.data) appendLine('❌ ' + e.data, 'error'); }
    });
    sse.addEventListener('session', function (e) {
      try {
        var d = JSON.parse(e.data);
        if (d.subtype === 'end') {
          busy = false; setUIState(false);
          document.getElementById('status-text').textContent = 'Idle';
          document.getElementById('status-text').style.color = '#4CAF50';
          if (thinkingStart > 0) { var sec = (Date.now()-thinkingStart)/1000; if (sec >= 0.5) appendLine('  🧠 思考 ' + sec.toFixed(1) + 's', 'dim'); thinkingStart = 0; }
        }
        if (d.subtype === 'start') {
          document.getElementById('status-text').textContent = 'Thinking';
          document.getElementById('status-text').style.color = '#FF9800';
        }
      } catch (x) {}
    });
    sse.onerror = function () { /* SSE connection issues - will auto-reconnect */ };
  }

  // ── Send ──

  function sendMessage() {
    if (busy) return;
    var input = document.getElementById('input-box');
    var text = input.value.trim();
    if (!text) return;
    lastInput = text; input.value = '';
    appendLine('>>> ' + text, 'user');
    thinkingStart = Date.now(); busy = true; setUIState(true);
    document.getElementById('status-text').textContent = 'Sending...';
    document.getElementById('status-text').style.color = '#FF9800';
    fetch('/api/send', {
      method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ text: text }),
    }).then(function (r) { return r.json(); }).then(function (d) {
      if (d.status !== 'ok') { appendLine('❌ ' + (d.message || '发送失败'), 'error'); busy = false; setUIState(false); }
    }).catch(function (e) {
      appendLine('❌ 网络错误: ' + e, 'error'); busy = false; setUIState(false);
    });
  }

  function stopAgent() {
    if (!busy) return;
    fetch('/api/stop', { method: 'POST' });
    busy = false; setUIState(false); appendLine('  ⏹ 已终止', 'system');
    document.getElementById('status-text').textContent = 'Idle';
    document.getElementById('status-text').style.color = '#4CAF50';
  }

  function retryLast() {
    if (busy || !lastInput) return;
    document.getElementById('input-box').value = lastInput; sendMessage();
  }

  function clearChat() { if (chatModel) chatModel.setValue('');
    document.getElementById('activity-log').innerHTML = ''; fetch('/api/clear', { method: 'POST' }); }

  function setUIState(b) {
    var btn = document.getElementById('send-btn');
    btn.disabled = b; btn.textContent = b ? '...' : '发送';
    document.getElementById('input-box').disabled = b;
  }

  function scrollToBottom() {
    if (!chatEditor) return;
    chatEditor.setScrollTop(chatEditor.getContentHeight()); isAtBottom = true; hideScrollIndicator();
  }

  function showScrollIndicator() { var el = document.getElementById('scroll-indicator'); if (el) el.style.display = 'block'; }
  function hideScrollIndicator() { var el = document.getElementById('scroll-indicator'); if (el) el.style.display = 'none'; }

  // ── Monaco Append ──

  function appendText(text, style) {
    if (!chatEditor) return;
    var prefix = (STYLE_PREFIXES[style] && STYLE_PREFIXES[style].prefix) || '';
    var lines = text.split('\n');
    var fullText = lines.map(function (l) { return prefix + l; }).join('\n');
    chatEditor.executeEdits('append', [
      { range: getEndRange(), text: fullText, forceMoveMarkers: true },
    ]);
    if (isAtBottom) chatEditor.setScrollTop(chatEditor.getContentHeight());
  }

  function appendLine(text, style) { appendText(text + '\n', style); }

  function getEndRange() {
    var lc = chatModel.getLineCount();
    var ll = chatModel.getLineContent(lc);
    return new monaco.Range(lc, ll.length + 1, lc, ll.length + 1);
  }

  // ── Tool Panel ──

  var CATEGORIES = [
    { name: '📂 文件系统', color: '#42A5F5', tools: ['read','write','edit','glob','grep'] },
    { name: '⚡ 命令执行', color: '#EF5350', tools: ['bash','background'] },
    { name: '🖥️ 系统控制', color: '#AB47BC', tools: ['process','service','registry','gui','monitor'] },
    { name: '🧠 网络/浏览器', color: '#FFA726', tools: ['web','web_search','browser'] },
    { name: '🔬 代码分析', color: '#FF7043', tools: ['ast','dep_graph','call_chain'] },
    { name: '📋 工具链', color: '#66BB6A', tools: ['plan','task','subagent','mcp'] },
  ];

  function buildToolPanel() {
    var container = document.getElementById('tab-tools');
    CATEGORIES.forEach(function (cat) {
      var hdr = document.createElement('div'); hdr.className = 'tool-cat'; hdr.style.color = cat.color; hdr.textContent = cat.name; container.appendChild(hdr);
      for (var i = 0; i < cat.tools.length; i += 2) {
        var row = document.createElement('div'); row.className = 'tool-row';
        for (var j = i; j < Math.min(i+2, cat.tools.length); j++) {
          var name = cat.tools[j];
          var card = document.createElement('div'); card.className = 'tool-card'; card.id = 'tool-'+name;
          card.innerHTML = '<span class="tool-dot" id="dot-'+name+'">○</span><span class="tool-name">'+(TOOL_ICONS[name]||'⚡')+' '+name+'</span>';
          row.appendChild(card);
        }
        container.appendChild(row);
      }
    });
  }

  function setToolStatus(name, status) {
    var dot = document.getElementById('dot-'+name); if (!dot) return;
    dot.textContent = {idle:'○',running:'●',done:'✓',error:'✗'}[status]||'○';
    dot.className = 'tool-dot ' + (status || 'idle');
  }

  function logActivity(tool, status) {
    var log = document.getElementById('activity-log');
    var ts = new Date().toLocaleTimeString();
    var icons = {running:'▶',done:'✓',error:'✗'};
    var line = document.createElement('div'); line.className = 'log-line '+status;
    line.textContent = ts+' '+(icons[status]||'·')+' '+tool;
    log.appendChild(line); log.scrollTop = log.scrollHeight;
  }

  // ── Diff ──

  function parseUnifiedDiff(t) {
    var s = t.indexOf('--- DIFF START ---'); var e = t.indexOf('--- DIFF END ---');
    if (s>=0) t = t.substring(s+18, e>=0?e:undefined);
    if (e>=0) t = t.substring(0,e);
    var orig=[],mod=[]; t.split('\n').forEach(function(l){
      if(l.startsWith('--- ')||l.startsWith('+++ ')||l.startsWith('@@ ')) return;
      if(l.startsWith('\\ ')) return;
      if(l.startsWith('-')) orig.push(l.substring(1));
      else if(l.startsWith('+')) mod.push(l.substring(1));
      else { var c=l.startsWith(' ')?l.substring(1):l; orig.push(c); mod.push(c); }
    });
    return {original:orig.join('\n'),modified:mod.join('\n')};
  }

  function openDiffFromUnified(diffText, filePath) {
    if (!diffEditor) return;
    var r = parseUnifiedDiff(diffText);
    if (!r.original&&!r.modified) { appendText(diffText,'result'); return; }
    var lang = filePath ? (function(fp){var m={py:'python',js:'javascript',ts:'typescript',html:'html',css:'css',json:'json',md:'markdown',yaml:'yaml',yml:'yaml'}; return m[fp.split('.').pop().toLowerCase()]||'plaintext';})(filePath) : 'plaintext';
    var om = monaco.editor.createModel(r.original, lang);
    var mm = monaco.editor.createModel(r.modified, lang);
    diffEditor.setModel({original:om,modified:mm});
    document.getElementById('chat-container').className='hidden';
    document.getElementById('diff-container').className='active';
    var fpEl = document.getElementById('diff-filepath');
    if(fpEl) fpEl.textContent = filePath||'';
    setTimeout(function(){if(chatEditor)chatEditor.layout();},100);
  }

  function closeDiff() {
    if (!diffEditor) return;
    var m = diffEditor.getModel();
    if(m){if(m.original)m.original.dispose();if(m.modified)m.modified.dispose();diffEditor.setModel({original:null,modified:null});}
    document.getElementById('diff-container').className='hidden';
    document.getElementById('chat-container').className='active';
    if(chatEditor){chatEditor.layout();setTimeout(function(){chatEditor.setScrollTop(chatEditor.getContentHeight());},100);}
  }

  // ── Expose ──

  window.sendMessage=sendMessage; window.stopAgent=stopAgent; window.retryLast=retryLast;
  window.clearChat=clearChat; window.scrollToBottom=scrollToBottom;
  window.openDiffFromUnified=openDiffFromUnified; window.closeDiff=closeDiff;
  window.openSettings=openSettings; window.closeSettings=closeSettings; window.saveSettings=saveSettings;

  // ── Start ──
  if(document.readyState==='loading') document.addEventListener('DOMContentLoaded',initMonaco);
  else initMonaco();
})();
