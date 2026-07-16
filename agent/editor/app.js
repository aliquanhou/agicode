/* AgiCode Web — Pure DOM chat + Monaco diff (optional) */

(function () {
  'use strict';

  var chatDiv = null, diffEditor = null, chatEditor = null, chatModel = null;
  var busy = false, lastInput = '', thinkingStart = 0, isAtBottom = true;
  var sseSource = null;

  var icons = {read:'📖',write:'✏️',edit:'🔧',glob:'🔍',grep:'🔎',bash:'💻',background:'⏳',process:'⚙️',web:'🌐',browser:'🌍',plan:'📋',task:'✅',ast:'🌳',dep_graph:'🕸',call_chain:'🔗',subagent:'🧠',mcp:'🔌'};

  // ── Chat Div Rendering (immediate, no dependencies) ──

  function ensureChatDiv() {
    if (!chatDiv) chatDiv = document.getElementById('chat-div');
    return chatDiv;
  }

  function appendMsg(text, className) {
    var div = ensureChatDiv();
    if (!div) return;
    var el = document.createElement('span');
    el.className = 'msg-' + (className || 'assistant');
    el.textContent = text;
    div.appendChild(el);
    if (isAtBottom) div.scrollTop = div.scrollHeight;
  }

  function appendLine(text, className) {
    appendMsg(text + '\n', className || 'assistant');
  }

  function appendToolStart(name, input) {
    var icon = icons[name] || '⚡';
    var path = '';
    if (input) path = input.file_path || input.command || input.url || input.pattern || input.query || '';
    appendLine('  ' + icon + ' ' + name + (path ? '  ' + path : ''), 'tool');
    if (input) {
      var extras = [];
      for (var k in input) {
        if (!['file_path','command','url','pattern','query','path','content'].includes(k) && input[k]) {
          extras.push(k + '=' + input[k]);
        }
      }
      if (extras.length) appendLine('    ' + extras.join(' ').substring(0, 150), 'dim');
    }
  }

  function appendToolResult(result, toolName, elapsed) {
    var isErr = /错误|error|失败|❌/i.test(result.substring(0,100));
    var icon = icons[toolName] || '⚡';
    if (isErr) {
      appendLine('    ' + icon + ' ' + toolName + ' ❌ 失败' + (elapsed||''), 'error');
      appendLine('    ' + result.substring(0,200).replace(/\n/g,' '), 'error');
    } else {
      appendLine('    ' + icon + ' ' + toolName + ' ✅ 完成' + (elapsed||''), 'result');
    }
  }

  function clearChat() {
    var div = ensureChatDiv();
    if (div) div.innerHTML = '';
    if (chatModel) chatModel.setValue('');
    document.getElementById('activity-log').innerHTML = '';
    fetch('/api/clear', {method:'POST'});
  }

  // ── SSE ──

  function connectSSE() {
    if (sseSource) sseSource.close();
    sseSource = new EventSource('/api/stream');
    sseSource.addEventListener('text', function (e) {
      try { var d = JSON.parse(e.data); if (d.delta) appendMsg(d.delta, 'assistant'); }
      catch (x) { if (e.data) appendMsg(e.data, 'assistant'); }
    });
    sseSource.addEventListener('thought', function (e) {
      try { var d = JSON.parse(e.data); if (d.delta && d.delta.length>20) appendLine('  🧠 '+d.delta.substring(0,120)+'...', 'thinking'); }
      catch (x) {}
    });
    sseSource.addEventListener('tool', function (e) {
      try {
        var d = JSON.parse(e.data);
        if (d.subtype === 'start') { setToolStatus(d.tool_name, 'running'); logActivity(d.tool_name, 'running'); }
        if (d.subtype === 'result') { setToolStatus(d.tool_name, d.status || 'done'); logActivity(d.tool_name, d.status || 'done'); }
      } catch (x) {}
    });
    sseSource.addEventListener('error', function (e) {
      try { var d = JSON.parse(e.data); if (d.message) appendLine('❌ '+d.message, 'error'); }
      catch (x) { if (e.data) appendLine('❌ '+e.data, 'error'); }
    });
    sseSource.addEventListener('session', function (e) {
      try {
        var d = JSON.parse(e.data);
        if (d.subtype === 'end') {
          busy = false; setUIState(false);
          document.getElementById('status-text').textContent = 'Idle';
          document.getElementById('status-text').style.color = '#4CAF50';
          if (thinkingStart > 0) { var sec = (Date.now()-thinkingStart)/1000; if (sec>=0.5) appendLine('  🧠 思考 '+sec.toFixed(1)+'s', 'dim'); thinkingStart=0; }
        }
        if (d.subtype === 'start') {
          document.getElementById('status-text').textContent = 'Thinking';
          document.getElementById('status-text').style.color = '#FF9800';
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
    lastInput = text; input.value = '';
    appendLine('>>> ' + text, 'user');
    thinkingStart = Date.now(); busy = true; setUIState(true);
    document.getElementById('status-text').textContent = 'Sending...';
    document.getElementById('status-text').style.color = '#FF9800';
    fetch('/api/send', {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({text:text})})
      .then(function(r){return r.json()}).then(function(d){
        if (d.status!=='ok') { appendLine('❌ '+(d.message||'发送失败'), 'error'); busy=false; setUIState(false); }
      }).catch(function(e){ appendLine('❌ 网络错误: '+e, 'error'); busy=false; setUIState(false); });
  }

  function stopAgent() {
    if (!busy) return;
    fetch('/api/stop', {method:'POST'}); busy=false; setUIState(false);
    appendLine('  ⏹ 已终止', 'system');
    document.getElementById('status-text').textContent = 'Idle';
    document.getElementById('status-text').style.color = '#4CAF50';
  }

  function retryLast() {
    if (busy || !lastInput) return;
    document.getElementById('input-box').value = lastInput; sendMessage();
  }

  function setUIState(b) {
    var btn = document.getElementById('send-btn');
    btn.disabled = b; btn.textContent = b ? '...' : '发送';
    document.getElementById('input-box').disabled = b;
  }

  function scrollToBottom() {
    var div = ensureChatDiv();
    if (div) { div.scrollTop = div.scrollHeight; isAtBottom = true; }
  }

  // ── Monaco Diff Editor (optional, loads from CDN) ──

  function tryMonaco() {
    if (typeof require === 'undefined') return;
    require.config({paths:{vs:'https://cdn.jsdelivr.net/npm/monaco-editor@0.52.2/min/vs'}});
    require(['vs/editor/editor.main'], function () {
      monaco.editor.defineTheme('agicode', {
        base:'vs-dark',inherit:true,colors:{
          'editor.background':'#1e1e1e','editor.foreground':'#e0e0e0',
        },
      });
      diffEditor = monaco.editor.createDiffEditor(document.getElementById('diff-editor'), {
        theme:'agicode',fontSize:13,fontFamily:'Consolas, "Microsoft YaHei", monospace',
        readOnly:true,renderSideBySide:false,minimap:{enabled:false},
        lineNumbers:'on',wordWrap:'on',automaticLayout:true,
      });
      window.__diffEditor = diffEditor;
      window.__monacoReady = true;
    });
  }

  window.openDiffFromUnified = function(diffText, filePath) {
    if (!window.__diffEditor) { appendLine('  ── 变更对比 ──', 'dim'); return; }
    var de = window.__diffEditor;
    // Parse unified diff
    var t = diffText;
    var si = t.indexOf('--- DIFF START ---'), ei = t.indexOf('--- DIFF END ---');
    if (si>=0) t = t.substring(si+18, ei>=0?ei:undefined);
    if (ei>=0) t = t.substring(0,ei);
    var orig=[], mod=[]; t.split('\n').forEach(function(l){
      if (l.startsWith('--- ')||l.startsWith('+++ ')||l.startsWith('@@ ')) return;
      if (l.startsWith('\\ ')) return;
      if (l.startsWith('-')) orig.push(l.substring(1));
      else if (l.startsWith('+')) mod.push(l.substring(1));
      else { var c=l.startsWith(' ')?l.substring(1):l; orig.push(c); mod.push(c); }
    });
    var lang = 'plaintext';
    if (filePath) { var m={py:'python',js:'javascript',ts:'typescript',html:'html',css:'css',json:'json'}; lang = m[filePath.split('.').pop().toLowerCase()] || 'plaintext'; }
    var om = monaco.editor.createModel(orig.join('\n'), lang);
    var mm = monaco.editor.createModel(mod.join('\n'), lang);
    de.setModel({original:om,modified:mm});
    document.getElementById('chat-container').className='hidden';
    document.getElementById('diff-container').className='active';
  };

  window.closeDiff = function() {
    if (!window.__diffEditor) return;
    var m = window.__diffEditor.getModel();
    if (m) { if (m.original) m.original.dispose(); if (m.modified) m.modified.dispose(); window.__diffEditor.setModel({original:null,modified:null}); }
    document.getElementById('diff-container').className='hidden';
    document.getElementById('chat-container').className='active';
  };

  // ── Tool Panel ──

  var CATEGORIES = [
    {name:'📂 文件系统',color:'#42A5F5',tools:['read','write','edit','glob','grep']},
    {name:'⚡ 命令执行',color:'#EF5350',tools:['bash','background']},
    {name:'🖥️ 系统控制',color:'#AB47BC',tools:['process','service','registry','gui','monitor']},
    {name:'🧠 网络/浏览器',color:'#FFA726',tools:['web','web_search','browser']},
    {name:'🔬 代码分析',color:'#FF7043',tools:['ast','dep_graph','call_chain']},
    {name:'📋 工具链',color:'#66BB6A',tools:['plan','task','subagent','mcp']},
  ];

  function buildToolPanel() {
    var c = document.getElementById('tab-tools');
    CATEGORIES.forEach(function(cat){
      var h=document.createElement('div'); h.className='tool-cat'; h.style.color=cat.color; h.textContent=cat.name; c.appendChild(h);
      for (var i=0;i<cat.tools.length;i+=2){ var r=document.createElement('div'); r.className='tool-row';
        for (var j=i;j<Math.min(i+2,cat.tools.length);j++){ var n=cat.tools[j],card=document.createElement('div'); card.className='tool-card'; card.id='tool-'+n;
          card.innerHTML='<span class="tool-dot" id="dot-'+n+'">○</span><span class="tool-name">'+(icons[n]||'⚡')+' '+n+'</span>'; r.appendChild(card); }
        c.appendChild(r); }
    });
  }

  function setToolStatus(name, status) {
    var dot = document.getElementById('dot-'+name); if (!dot) return;
    dot.textContent = {idle:'○',running:'●',done:'✓',error:'✗'}[status]||'○';
    dot.className = 'tool-dot '+(status||'idle');
  }

  function logActivity(tool, status) {
    var log = document.getElementById('activity-log');
    var ts = new Date().toLocaleTimeString();
    var icons = {running:'▶',done:'✓',error:'✗'};
    var l = document.createElement('div'); l.className='log-line '+status;
    l.textContent = ts+' '+(icons[status]||'·')+' '+tool;
    log.appendChild(l); log.scrollTop = log.scrollHeight;
  }

  // ── Config ──

  function loadConfig() {
    fetch('/api/config').then(function(r){return r.json()}).then(function(d){
      document.getElementById('settings-provider').value = d.provider||'DeepSeek';
      document.getElementById('settings-key').placeholder = d.api_key ? '当前已配置，输入新 Key 覆盖' : '输入 API Key';
      document.getElementById('settings-model').value = d.model||'';
      document.getElementById('provider-label').textContent = d.provider||'—';
      if (!d.api_key) appendLine('⚠️ 请点击右上角 ⚙ Settings 配置 API Key', 'system');
    }).catch(function(){});
  }

  window.openSettings = function() {
    fetch('/api/config').then(function(r){return r.json()}).then(function(d){
      document.getElementById('settings-provider').value = d.provider||'DeepSeek';
      document.getElementById('settings-key').value = '';
      document.getElementById('settings-key').placeholder = d.api_key ? '当前已配置，输入新 Key 覆盖' : '输入 API Key';
      document.getElementById('settings-model').value = d.model||'';
    }).catch(function(){});
    document.getElementById('settings-modal').classList.remove('hidden');
  };

  window.closeSettings = function() { document.getElementById('settings-modal').classList.add('hidden'); };

  window.saveSettings = function() {
    var provider = document.getElementById('settings-provider').value;
    var key = document.getElementById('settings-key').value.trim();
    var model = document.getElementById('settings-model').value.trim();
    if (!key) { appendLine('⚠️ 请输入 API Key', 'system'); return; }
    fetch('/api/config', {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({provider:provider,api_key:key,model:model})})
      .then(function(r){return r.json()}).then(function(d){
        if (d.status==='ok') { document.getElementById('provider-label').textContent=provider; appendLine('✅ 配置已保存: '+provider+' / '+model, 'system'); }
        else { appendLine('❌ 保存失败: '+(d.message||''), 'error'); }
      }).catch(function(e){ appendLine('❌ 保存失败: '+e, 'error'); });
    window.closeSettings();
  };

  // ── Init ──

  window.sendMessage=sendMessage; window.stopAgent=stopAgent; window.retryLast=retryLast;
  window.clearChat=clearChat; window.scrollToBottom=scrollToBottom;

  function init() {
    // DOM references
    chatDiv = document.getElementById('chat-div');

    // Input handler
    document.getElementById('input-box').addEventListener('keydown', function(e) {
      if (e.key==='Enter' && !e.ctrlKey && !e.shiftKey) { e.preventDefault(); sendMessage(); }
    });

    // Tab switching
    document.querySelectorAll('.tab').forEach(function(t){
      t.addEventListener('click',function(){
        document.querySelectorAll('.tab,.tab-content').forEach(function(x){x.classList.remove('active');});
        t.classList.add('active');
        document.getElementById('tab-'+t.dataset.tab).classList.add('active');
      });
    });

    // Scroll detection
    chatDiv.addEventListener('scroll', function() {
      isAtBottom = (chatDiv.scrollHeight - chatDiv.scrollTop - chatDiv.clientHeight) < 40;
    });

    buildToolPanel();
    loadConfig();
    connectSSE();
    tryMonaco();
  }

  if (document.readyState==='loading') document.addEventListener('DOMContentLoaded', init);
  else init();
})();
