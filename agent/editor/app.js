/* AgiCode Monaco Editor Integration
   Handles: Chat rendering, Diff display, SSE streaming, Bridge API */

(function () {
  'use strict';

  // ── State ──

  let chatEditor = null;
  let chatModel = null;
  let diffEditor = null;
  let diffContainer = null;
  let chatContainer = null;
  let scrollIndicator = null;
  let isAtBottom = true;
  let newMsgCount = 0;
  let themeApplied = false;

  // ── Color Theme ──

  const AGICODE_THEME = {
    base: 'vs-dark',
    inherit: true,
    rules: [
      { token: 'user-msg', foreground: '4CAF50' },
      { token: 'assistant-msg', foreground: 'E0E0E0' },
      { token: 'thinking-msg', foreground: '888888', fontStyle: 'italic' },
      { token: 'tool-name', foreground: 'FF9800', fontStyle: 'bold' },
      { token: 'tool-result', foreground: 'FFB74D' },
      { token: 'tool-error', foreground: 'F44336', fontStyle: 'bold' },
      { token: 'system-msg', foreground: '64B5F6' },
      { token: 'dim-text', foreground: '666666' },
      { token: 'separator', foreground: '333333', fontStyle: 'italic' },
      { token: 'diff-header', foreground: '569CD6', fontStyle: 'bold' },
      { token: 'diff-add', foreground: '4CAF50' },
      { token: 'diff-del', foreground: 'F44336' },
      { token: 'diff-hunk', foreground: 'C792EA', fontStyle: 'bold' },
      { token: 'code-text', foreground: '82AAFF' },
    ],
    colors: {
      'editor.background': '#1e1e1e',
      'editor.foreground': '#e0e0e0',
      'editor.lineHighlightBackground': '#2a2a2a',
      'editor.selectionBackground': '#264f78',
      'editor.inactiveSelectionBackground': '#3a3d41',
      'editorIndentGuide.background': '#333',
      'editorWidget.background': '#252526',
      'editorWidget.border': '#454545',
      'input.background': '#3c3c3c',
      'input.foreground': '#e0e0e0',
      'list.activeSelectionBackground': '#094771',
      'list.hoverBackground': '#2a2d2e',
      'diffEditor.insertedTextBackground': '#4CAF5020',
      'diffEditor.removedTextBackground': '#F4433620',
    },
  };

  // ── Style Tokens for Chat Text ──

  // We encode styles as Monaco theme tokens by line prefix
  const STYLE_MAP = {
    user:        { prefix: '// [USER] ',    token: 'user-msg' },
    assistant:   { prefix: '',               token: 'assistant-msg' },
    thinking:    { prefix: '// [THINK] ',   token: 'thinking-msg' },
    tool:        { prefix: '// [TOOL] ',    token: 'tool-name' },
    tool_result: { prefix: '// [RESULT] ',  token: 'tool-result' },
    err:         { prefix: '// [ERROR] ',   token: 'tool-error' },
    sys:         { prefix: '// [SYS] ',     token: 'system-msg' },
    dim:         { prefix: '// [DIM] ',     token: 'dim-text' },
    sep:         { prefix: '// [SEP] ',     token: 'separator' },
    code:        { prefix: '// [CODE] ',    token: 'code-text' },
  };

  // ── Token Provider (maps line prefixes to color tokens) ──

  class AgiCodeTokenProvider {
    constructor() {
      this._tokens = {};
      for (const key in STYLE_MAP) {
        const info = STYLE_MAP[key];
        if (info.prefix) {
          this._tokens[info.prefix] = info.token;
        }
      }
    }

    getInitialState() { return 0; }

    tokenize(line, state) {
      const tokens = [];
      // Check line prefix for color token
      for (const prefix in this._tokens) {
        if (line.startsWith(prefix)) {
          tokens.push({ startIndex: 0, scopes: this._tokens[prefix] });
          tokens.push({ startIndex: line.length, scopes: this._tokens[prefix] });
          return { tokens, endState: 0 };
        }
      }
      // Default
      tokens.push({ startIndex: 0, scopes: 'assistant-msg' });
      tokens.push({ startIndex: line.length, scopes: 'assistant-msg' });
      return { tokens, endState: 0 };
    }
  }

  // ── Init Monaco ──

  function initMonaco() {
    require.config({
      paths: {
        vs: 'https://cdn.jsdelivr.net/npm/monaco-editor@0.52.2/min/vs',
      },
    });

    require(['vs/editor/editor.main'], function () {
      // Register custom theme
      monaco.editor.defineTheme('agicode-dark', AGICODE_THEME);

      // Register custom token provider
      monaco.languages.register({ id: 'agicode-chat' });
      monaco.languages.setTokensProvider('agicode-chat', new AgiCodeTokenProvider());

      // Language detection for code blocks
      monaco.languages.register({ id: 'agicode-code' });

      // ── Chat Editor ──

      chatContainer = document.getElementById('chat-container');
      diffContainer = document.getElementById('diff-container');

      chatModel = monaco.editor.createModel('', 'agicode-chat');
      chatEditor = monaco.editor.create(document.getElementById('chat-editor'), {
        model: chatModel,
        theme: 'agicode-dark',
        language: 'agicode-chat',
        readOnly: true,
        fontSize: 13,
        fontFamily: 'Consolas, "Microsoft YaHei", monospace',
        lineNumbers: 'off',
        minimap: { enabled: false },
        wordWrap: 'on',
        scrollBeyondLastLine: false,
        renderWhitespace: 'none',
        contextmenu: false,
        folding: false,
        lineDecorationsWidth: 0,
        lineNumbersMinChars: 0,
        glyphMargin: false,
        padding: { top: 8, bottom: 8 },
        automaticLayout: true,
        scrollbar: {
          verticalScrollbarSize: 8,
          horizontalScrollbarSize: 0,
          alwaysConsumeMouseWheel: false,
        },
        suggest: { showWords: false },
        quickSuggestions: false,
      });

      // ── Diff Editor ──

      diffEditor = monaco.editor.createDiffEditor(document.getElementById('diff-editor'), {
        theme: 'agicode-dark',
        fontSize: 13,
        fontFamily: 'Consolas, "Microsoft YaHei", monospace',
        readOnly: true,
        renderSideBySide: false,
        minimap: { enabled: false },
        lineNumbers: 'on',
        wordWrap: 'on',
        scrollBeyondLastLine: false,
        automaticLayout: true,
      });

      // ── Scroll Indicator ──

      scrollIndicator = document.getElementById('scroll-indicator');
      if (!scrollIndicator) {
        scrollIndicator = document.createElement('div');
        scrollIndicator.id = 'scroll-indicator';
        document.getElementById('app').appendChild(scrollIndicator);
      }

      // ── Scroll Events ──

      chatEditor.onDidScrollChange(function (e) {
        const height = chatEditor.getContentHeight();
        const visible = chatEditor.getLayoutInfo().height;
        const wasAtBottom = isAtBottom;
        isAtBottom = (e.scrollTop + visible >= height - 30);
        if (isAtBottom) {
          newMsgCount = 0;
          scrollIndicator.classList.remove('visible');
        } else if (newMsgCount > 0) {
          updateScrollIndicator();
        }
      });

      scrollIndicator.addEventListener('click', function () {
        scrollToBottom();
      });

      // ── Mark ready ──
      window.__monacoReady = true;
      if (window.__monacoPending) {
        window.__monacoPending.forEach(function (fn) { fn(); });
        window.__monacoPending = [];
      }
    });
  }

  // ── Public Bridge API ──

  window.AgiCodeBridge = {

    // Append styled text to chat
    appendText: function (text, style) {
      if (!chatEditor) return;
      const info = STYLE_MAP[style] || STYLE_MAP.assistant;
      const prefix = info.prefix;
      const lines = text.split('\n');
      const fullText = lines.map(function (l) { return prefix + l; }).join('\n');
      chatEditor.executeEdits('append', [
        { range: getEndRange(), text: fullText, forceMoveMarkers: true },
      ]);
      if (isAtBottom) scrollToBottom();
    },

    // Append a single line with style
    appendLine: function (text, style) {
      this.appendText(text + '\n', style);
    },

    // Append tool start line
    appendToolStart: function (name, input, stepPrefix) {
      if (!chatEditor) return;
      const iconMap = {
        read: '📖', write: '✏️', edit: '🔧', glob: '🔍', grep: '🔎',
        bash: '💻', web: '🌐', web_search: '🔍', browser: '🌍',
        process: '⚙️', service: '⚙️', plan: '📋', task: '✅',
        background: '⏳', remember: '🧠', test: '🧪', dep: '📦',
        ask_user: '💬',
      };
      const icon = iconMap[name] || '⚡';
      let line = '  ' + icon + ' ' + name;
      if (input) {
        const path = input.file_path || input.command || input.url || input.pattern || input.query || '';
        if (path) line += '  ' + path;
      }
      if (stepPrefix) line += '  ' + stepPrefix;
      chatEditor.executeEdits('append', [
        { range: getEndRange(), text: STYLE_MAP.tool.prefix + line + '\n', forceMoveMarkers: true },
      ]);
      if (isAtBottom) scrollToBottom();
    },

    // Append tool result
    appendToolResult: function (result, toolName, elapsed, activeInput) {
      if (!chatEditor) return;
      const isErr = /错误|error|失败|❌/i.test(result.substring(0, 100));
      const iconMap = {
        read: '📖', write: '✏️', edit: '🔧',
      };
      const icon = iconMap[toolName] || '⚡';
      let line;

      if (isErr) {
        line = '    ' + icon + ' ' + toolName + ' ❌ 失败' + (elapsed || '');
        chatEditor.executeEdits('append', [
          { range: getEndRange(), text: STYLE_MAP.err.prefix + line + '\n', forceMoveMarkers: true },
        ]);
        const summary = result.substring(0, 200).replace(/\n/g, ' ');
        chatEditor.executeEdits('append', [
          { range: getEndRange(), text: STYLE_MAP.err.prefix + '    ' + summary + '\n', forceMoveMarkers: true },
        ]);
      } else {
        line = '    ' + icon + ' ' + toolName + ' ✅ 完成' + (elapsed || '');
        chatEditor.executeEdits('append', [
          { range: getEndRange(), text: STYLE_MAP.tool_result.prefix + line + '\n', forceMoveMarkers: true },
        ]);
      }
      if (isAtBottom) scrollToBottom();
    },

    // Open unified diff in diff editor
    openDiffFromUnified: function (diffText, filePath) {
      if (!diffEditor) return;
      const result = parseUnifiedDiff(diffText);
      if (!result.original && !result.modified) {
        // Fallback: show raw text
        this.appendText(diffText, 'tool_result');
        return;
      }

      // Create models
      const lang = detectLanguage(filePath);
      const originalModel = monaco.editor.createModel(result.original, lang);
      const modifiedModel = monaco.editor.createModel(result.modified, lang);
      diffEditor.setModel({ original: originalModel, modified: modifiedModel });

      // Switch to diff view
      chatContainer.classList.remove('active');
      chatContainer.classList.add('hidden');
      diffContainer.classList.remove('hidden');
      diffContainer.classList.add('active');

      // Show file path
      var fpEl = document.getElementById('diff-filepath');
      if (fpEl) fpEl.textContent = filePath || '';
    },

    // Close diff view, return to chat
    closeDiff: function () {
      if (!diffEditor) return;
      // Dispose diff models
      const m = diffEditor.getModel();
      if (m) {
        if (m.original) m.original.dispose();
        if (m.modified) m.modified.dispose();
        diffEditor.setModel({ original: null, modified: null });
      }
      diffContainer.classList.remove('active');
      diffContainer.classList.add('hidden');
      chatContainer.classList.remove('hidden');
      chatContainer.classList.add('active');
      if (chatEditor) {
        chatEditor.layout();
        scrollToBottom();
      }
    },

    // Clear chat
    clearChat: function () {
      if (!chatModel) return;
      chatModel.setValue('');
    },

    // Scroll to bottom
    scrollToBottom: function () {
      scrollToBottom();
    },

    // Set status text (no-op in Monaco, kept for API compat)
    setStatus: function (text) {},

    // Get scroll state
    getScrollState: function () {
      if (!chatEditor) return JSON.stringify({ atBottom: true, scrollTop: 0 });
      const pos = chatEditor.getScrollTop();
      const height = chatEditor.getContentHeight();
      const visible = chatEditor.getLayoutInfo().height;
      return JSON.stringify({
        atBottom: pos + visible >= height - 30,
        scrollTop: pos,
      });
    },

    // Get all chat content
    getContent: function () {
      if (!chatModel) return '';
      return chatModel.getValue();
    },
  };

  // ── Helper Functions ──

  function getEndRange() {
    const lineCount = chatModel.getLineCount();
    const lastLine = chatModel.getLineContent(lineCount);
    return new monaco.Range(lineCount, lastLine.length + 1, lineCount, lastLine.length + 1);
  }

  function scrollToBottom() {
    if (!chatEditor) return;
    const height = chatEditor.getContentHeight();
    chatEditor.setScrollTop(height);
    isAtBottom = true;
    newMsgCount = 0;
    if (scrollIndicator) scrollIndicator.classList.remove('visible');
  }

  function updateScrollIndicator() {
    if (!scrollIndicator) return;
    scrollIndicator.textContent = '  ↓ ' + newMsgCount + ' 条新消息  ';
    scrollIndicator.classList.add('visible');
  }

  function parseUnifiedDiff(diffText) {
    // Strip markers
    var cleaned = diffText;
    var startM = '--- DIFF START ---';
    var endM = '--- DIFF END ---';
    var si = cleaned.indexOf(startM);
    var ei = cleaned.indexOf(endM);
    if (si >= 0) cleaned = cleaned.substring(si + startM.length, ei >= 0 ? ei : undefined);
    if (ei >= 0) cleaned = cleaned.substring(0, ei >= 0 ? ei : cleaned.length);

    var originalLines = [];
    var modifiedLines = [];
    var lines = cleaned.split('\n');

    for (var i = 0; i < lines.length; i++) {
      var line = lines[i];
      if (line.startsWith('--- ') || line.startsWith('+++ ') || line.startsWith('@@ ')) continue;
      if (line.startsWith('\\ ')) continue;
      if (line.startsWith('-')) {
        originalLines.push(line.substring(1));
      } else if (line.startsWith('+')) {
        modifiedLines.push(line.substring(1));
      } else {
        var ctx = line.startsWith(' ') ? line.substring(1) : line;
        originalLines.push(ctx);
        modifiedLines.push(ctx);
      }
    }
    return {
      original: originalLines.join('\n'),
      modified: modifiedLines.join('\n'),
    };
  }

  function detectLanguage(filePath) {
    if (!filePath) return 'plaintext';
    var ext = filePath.split('.').pop().toLowerCase();
    var map = {
      py: 'python', js: 'javascript', ts: 'typescript', jsx: 'javascript',
      tsx: 'typescript', html: 'html', css: 'css', json: 'json',
      md: 'markdown', yaml: 'yaml', yml: 'yaml', toml: 'ini',
      c: 'c', cpp: 'cpp', java: 'java', rs: 'rust', go: 'go',
      rs: 'rust', sh: 'shell', ps1: 'powershell', bat: 'bat',
    };
    return map[ext] || 'plaintext';
  }

  // ── Start ──

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initMonaco);
  } else {
    initMonaco();
  }

})();