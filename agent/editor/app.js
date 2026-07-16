/* ══════════════════════════════════════════════════
   AgiCode Web v2 — Full Claude Code-style UI
   ══════════════════════════════════════════════════
   - Particle canvas background
   - Claude Code-style conversation output
   - Tool calls with paths, diffs, timing
   - Streaming text accumulation
   - Side panels: tools, workflow, events, config, agents
   ══════════════════════════════════════════════════ */
(function(){'use strict';

// ─── STATE ───
var S={
  busy:0, last:'', ab:1, sse:null,
  wfSteps:[], wfDone:0, wfTotal:0,
  toolCount:0, events:[], evFilter:'all',
  _thinkStart:0,
};

// ─── localStorage 持久化 ───
var STORAGE_KEY = 'agicode_session';
function saveState(){
  try{
    // 只存核心数据，不存 DOM
    var data = {
      msgs: [],  // {type, text, html, acc}
      wf: {steps:S.wfSteps, done:S.wfDone, total:S.wfTotal},
      tc: S.toolCount,
      ev: S.events.slice(-200),  // 只存最近 200 条
      ts: window._toolStats || {},
      last: S.last || '',
    };
    // 从 DOM 提取消息
    var children = msgs.querySelectorAll(':scope > *');
    children.forEach(function(el){
      var m = {type:'asst'};
      if(el.classList.contains('msg-user')) m.type='user';
      else if(el.classList.contains('msg-asst')) m.type='asst';
      else if(el.classList.contains('tool-line')) {m.type='tool'; m.tname=el.dataset.tname||''; m.tseq=el.dataset.tseq||'';}
      else if(el.classList.contains('diff-block')) return; // diff 不存，让工具重新渲染
      else if(el.classList.contains('step-sep')) {m.type='sep'; m.text=el.textContent; data.msgs.push(m); return;}
      else if(el.classList.contains('think-block')) {m.type='think'; m.text=el.querySelector('.tb-b')?.textContent||''; data.msgs.push(m); return;}
      else if(el.classList.contains('msg-sys')) {m.type='sys'; m.text=el.textContent; data.msgs.push(m); return;}
      else if(el.classList.contains('msg-err')) {m.type='err'; m.text=el.textContent; data.msgs.push(m); return;}
      else return; // skip others

      var mc = el.querySelector('.mc');
      if(mc) m.html = mc.innerHTML;
      if(el._acc) m.acc = el._acc;
      data.msgs.push(m);
    });
    localStorage.setItem(STORAGE_KEY, JSON.stringify(data));
  }catch(e){/* quota exceeded etc */}
}

function loadState(){
  try{
    var raw = localStorage.getItem(STORAGE_KEY);
    if(!raw) return false;
    var data = JSON.parse(raw);
    if(!data || !data.msgs) return false;

    // Restore messages
    msgs.innerHTML = '';
    data.msgs.forEach(function(m){
      if(m.type==='user'){
        var el=div('msg msg-user');
        el.innerHTML='<div class="mc">'+(m.html||esc(m.text||''))+'</div><div class="mt">-</div>';
        msgs.appendChild(el);
      } else if(m.type==='asst'){
        var el=div('msg msg-asst');
        el.innerHTML='<div class="mc">'+(m.html||'')+'</div><div class="mt">-</div>';
        if(m.acc) el._acc=m.acc;
        msgs.appendChild(el);
      } else if(m.type==='tool'){
        var el=div('tool-line');
        if(m.tname) el.dataset.tname=m.tname;
        if(m.tseq) el.dataset.tseq=m.tseq;
        el.innerHTML=m.html||'<span class="tl-icon">⚡</span><span class="tl-name">tool</span><span class="tl-status tl-done">✅</span>';
        msgs.appendChild(el);
      } else if(m.type==='sep'){
        var el=div('step-sep step-done');
        el.textContent=m.text||'';
        msgs.appendChild(el);
      } else if(m.type==='think'){
        var el=div('think-block');
        el.innerHTML='<div class="think-h">🧠 思考</div><div class="think-b">'+esc(m.text||'')+'</div>';
        el.querySelector('.think-h').onclick=function(){el.classList.toggle('collapsed')};
        msgs.appendChild(el);
      } else if(m.type==='sys'){
        var el=div('msg msg-sys');
        el.innerHTML='<div class="mc">'+esc(m.text||'')+'</div>';
        msgs.appendChild(el);
      } else if(m.type==='err'){
        var el=div('msg msg-err');
        el.innerHTML='<div class="mc">'+esc(m.text||'')+'</div>';
        msgs.appendChild(el);
      }
    });

    // Restore workflow
    if(data.wf){
      S.wfSteps=data.wf.steps||[];
      S.wfDone=data.wf.done||0;
      S.wfTotal=data.wf.total||0;
      renderWfPanel();
      updateWfBar();
    }

    // Restore events
    if(data.ev) S.events=data.ev;
    renderEvLog();

    // Restore tool stats
    if(data.ts){ window._toolStats=data.ts;
      Object.keys(data.ts).forEach(function(n){
        var cnt=$('tcnt-'+n); if(cnt) cnt.textContent=data.ts[n];
      });
    }

    // Restore counts
    if(data.tc){S.toolCount=data.tc;$('st-c').textContent=data.tc;}
    if(data.last) S.last=data.last;

    // Scroll to bottom
    setTimeout(function(){msgs.scrollTop=msgs.scrollHeight;},100);
    return true;
  }catch(e){return false;}
}

// 在每次状态改变后自动保存
function autoSave(){
  if(typeof msgs!=='undefined' && msgs){
    // 防抖：延迟保存，避免频繁写入
    if(window._saveTimer) clearTimeout(window._saveTimer);
    window._saveTimer = setTimeout(saveState, 500);
  }
}

// ─── DOM ───
var $=function(id){return document.getElementById(id)};
var msgs=$('msgs'), ib=$('inp'), sb=$('send-btn'), st=$('st-t'), hds=$('hd-s');
var wff=$('wf-f'), wfc=$('wf-cnt'), wfcur=$('wf-cur'), wfnx=$('wf-nx');
var toasts=$('toasts'), scrollH=$('scroll-hint');

// ─── TOOL ICONS ───
var I={
  read:'📖',write:'✏️',edit:'🔧',replace:'🔍',
  glob:'🔎',grep:'🔎',bash:'💻',background:'⏳',
  web:'🌐',web_search:'🔍',browser:'🌍',ask_user:'💬',
  process:'⚙️',service:'⚙️',registry:'📋',gui:'🖱️',monitor:'📊',
  ast:'🌳',dep_graph:'🕸️',call_chain:'🔗',trace_error:'🐛',
  plan:'📋',task:'✅',project_memory:'🗂️',
  subagent:'🧠',mcp:'🔌',remember:'🧠',
  schedule:'⏰',watch:'👁️',websocket:'🔌',
  test:'🧪',dep:'📦',hash_file:'#️⃣',
  move:'📂',copy:'📄',delete:'🗑️',mkdir:'📁',download:'📥',revert:'⏪',
};

// ══════════════════════════════════════════════════
// PARTICLE BACKGROUND
// ══════════════════════════════════════════════════
(function(){
  var cv=$('bg-canvas'), ctx=cv.getContext('2d'), W,H, parts=[], mx=0,my=0, ma=0;
  var COLORS=['0,212,255','124,58,237','244,114,182','52,211,153'];
  function resize(){W=cv.width=window.innerWidth;H=cv.height=window.innerHeight}
  resize(); window.addEventListener('resize',resize);

  for(var i=0;i<120;i++){
    parts.push({
      x:Math.random()*W,y:Math.random()*H,
      vx:(Math.random()-0.5)*0.5,vy:(Math.random()-0.5)*0.5,
      r:Math.random()*2+0.5,o:Math.random()*0.4+0.1,
      c:COLORS[Math.floor(Math.random()*4)],
      ps:Math.random()*0.02+0.005,po:Math.random()*Math.PI*2,
    });
  }

  document.addEventListener('mousemove',function(e){mx=e.clientX;my=e.clientY;ma=1});
  document.addEventListener('mouseleave',function(){ma=0});

  function anim(t){
    ctx.clearRect(0,0,W,H);
    for(var i=0;i<parts.length;i++){
      var p=parts[i];p.x+=p.vx;p.y+=p.vy;
      if(p.x<0||p.x>W)p.vx*=-1;if(p.y<0||p.y>H)p.vy*=-1;
      var d=ma?Math.hypot(p.x-mx,p.y-my):999;
      var sc=d<150?1+(1-d/150)*1.5:1;
      var ro=p.o*(0.7+0.3*Math.sin(t*p.ps+p.po));
      if(d<80)ro=Math.min(1,ro+0.4);
      ctx.beginPath();ctx.arc(p.x,p.y,p.r*sc,0,Math.PI*2);
      ctx.fillStyle='rgba('+p.c+','+ro+')';ctx.fill();
    }
    // connections
    for(var i=0;i<parts.length;i++){
      for(var j=i+1;j<parts.length;j++){
        var dx=parts[i].x-parts[j].x,dy=parts[i].y-parts[j].y,dist=Math.hypot(dx,dy);
        if(dist<120){
          ctx.beginPath();ctx.moveTo(parts[i].x,parts[i].y);ctx.lineTo(parts[j].x,parts[j].y);
          ctx.strokeStyle='rgba(124,58,227,'+(1-dist/120)*0.12+')';ctx.lineWidth=0.5;ctx.stroke();
        }
      }
    }
    // mouse connections
    if(ma){
      for(var i=0;i<parts.length;i++){
        var dx=parts[i].x-mx,dy=parts[i].y-my,dist=Math.hypot(dx,dy);
        if(dist<180){
          ctx.beginPath();ctx.moveTo(parts[i].x,parts[i].y);ctx.lineTo(mx,my);
          ctx.strokeStyle='rgba(0,212,255,'+(1-dist/180)*0.2+')';ctx.lineWidth=0.6;ctx.stroke();
        }
      }
    }
    requestAnimationFrame(anim);
  }
  anim(0);
})();

// ══════════════════════════════════════════════════
// UTILITY
// ══════════════════════════════════════════════════
function esc(s){var d=document.createElement('div');d.textContent=s;return d.innerHTML}
function ts(){return new Date().toLocaleTimeString()}
function div(c){var d=document.createElement('div');d.className=c;return d}
function scrollB(){if(S.ab)msgs.scrollTop=msgs.scrollHeight}

// Language map
var LM={py:'python',js:'javascript',ts:'typescript',jsx:'javascript',tsx:'typescript',
  html:'html',css:'css',json:'json',md:'markdown',yaml:'yaml',yml:'yaml',
  rs:'rust',go:'go',java:'java',cpp:'cpp',c:'c',sh:'bash',bash:'bash',
  sql:'sql',xml:'xml',php:'php',rb:'ruby',swift:'swift',kt:'kotlin'};

// Simple syntax highlight - safe, no HTML corruption
function hl(line,lang){
  var h=esc(line);
  // Only do safe replacements: keywords get bold+color span
  var kws=['function ','def ','class ','return ','if ','else ','elif ','for ','while ','import ','from ','export ','const ','let ','var ','async ','await ','try ','catch ','throw ','new ','this ','null ','undefined ','true ','false ','None ','True ','False ','self ','public ','private ','static ','interface ','enum ','type ','package ','struct ','impl ','trait ','fn ','mut ','pub ','in ','not ','and ','or ','is ','lambda ','yield ','with ','as ','except ','finally ','raise ','pass ','break ','continue ','switch ','case ','default '];
  kws.forEach(function(kw){
    var re=new RegExp('(^|\\W)('+kw.replace(/[.*+?^${}()|[\]\\]/g,'\\$&')+')(?=\\W|$)','g');
    h=h.replace(re,'$1<span style="color:#7c3aed;font-weight:600">$2</span>');
  });
  // Comments
  h=h.replace(/(&lt;!--[\s\S]*?--&gt;|#.+$|\/\/.+$)/gm,'<span style="color:#555580;font-style:italic">$1</span>');
  // Strings (only safe quotes)
  h=h.replace(/("(?:[^"\\]|\\.)*")/g,'<span style="color:#ce9178">$1</span>');
  h=h.replace(/('(?:[^'\\]|\\.)*')/g,'<span style="color:#ce9178">$1</span>');
  return h;
}

// Markdown render — handles agent text with embedded HTML
function md(text){
  if(!text) return '';
  var h = text, cbs = [], ics = [];  // protected blocks

  // 1. Protect code blocks ```...``` from any processing
  h = h.replace(/```(\w*)\n?([\s\S]*?)```/g, function(m, l, c) {
    var i = cbs.length;
    cbs.push('<pre><code>' + esc(c) + '</code></pre>');
    return '%%CB' + i + '%%';
  });

  // 2. Protect inline code `...`
  h = h.replace(/`([^`]+)`/g, function(m, c) {
    var i = ics.length;
    ics.push('<code>' + esc(c) + '</code>');
    return '%%IC' + i + '%%';
  });

  // 3. Process markdown syntax (safe because code is already protected)
  h = h.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>');
  h = h.replace(/^# (.+)$/gm, '<b style="font-size:16px;color:var(--accent)">$1</b>');
  h = h.replace(/^## (.+)$/gm, '<b style="font-size:14px">$1</b>');

  // 4. Restore protected blocks (BEFORE line breaks, so <pre> keeps its internal \n)
  h = h.replace(/%%CB(\d+)%%/g, function(m, i) { return cbs[parseInt(i)] || ''; });
  h = h.replace(/%%IC(\d+)%%/g, function(m, i) { return ics[parseInt(i)] || ''; });

  // 5. Line breaks (skip inside <pre>)
  h = h.replace(/\n/g, '<br>');

  return h;
}

// ─── Diff detection ───
function hasDiff(t){return t.indexOf('@@ -')>=0||(t.indexOf('\n+')>=0&&t.indexOf('\n-')>=0)||t.indexOf('+++')>=0}

// ══════════════════════════════════════════════════
// CHAT MESSAGES — Claude Code style
// ══════════════════════════════════════════════════

// Assistant text (streaming accumulator)
function addText(delta){try{autoSave()}catch(e){}
  var last=msgs.lastElementChild;
  if(last&&last.classList.contains('msg-asst')){
    last._acc=(last._acc||'')+delta;
    var mc=last.querySelector('.mc');
    if(mc) mc.innerHTML=md(last._acc);
  }else{
    var el=div('msg msg-asst');
    el.innerHTML='<div class="mc">'+md(delta)+'</div><div class="mt">'+ts()+'</div>';
    el._acc=delta;
    msgs.appendChild(el);
  }
  scrollB();
}

// User message
function addUser(text){try{autoSave()}catch(e){}
  var el=div('msg msg-user');
  el.innerHTML='<div class="mc">'+esc(text)+'</div><div class="mt">'+ts()+'</div>';
  msgs.appendChild(el);scrollB();
}

// Tool call line — compact, Claude Code style
var _toolSeq=0;
function addToolCall(name, path, extra){try{autoSave()}catch(e){}
  var icon=I[name]||'⚡';
  var extraHtml=extra?' <span class="tl-extra">'+esc(extra)+'</span>':'';
  var pathHtml=path?'<span class="tl-target">'+esc(path)+'</span>':'';
  var seq=++_toolSeq;
  var el=div('tool-line');
  el.dataset.tseq=seq;
  el.dataset.tname=name;
  el.innerHTML='<span class="tl-icon">'+icon+'</span>'
    +'<span class="tl-name">'+name+'</span>'
    +pathHtml+extraHtml
    +'<span class="tl-status">⏳</span>';
  msgs.appendChild(el);scrollB();

  // Add step separator after every 3 calls
  var tl=msgs.querySelectorAll('.tool-line');
  if(tl.length>=3&&tl.length%3===0){
    var sep=div('step-sep step-done');
    sep.textContent='✔ '+(tl.length)+' 工具调用';
    msgs.appendChild(sep);scrollB();
  }
  return el;
}

// Tool result — update status + render diff
// Uses sequential matching: finds the first tool-line with same name AND ⏳ status
function addToolResult(name, isErr, durMs, resultText, toolPath){
  var tools=msgs.querySelectorAll('.tool-line');
  var tc=null;
  // Find the FIRST tool-line with matching name AND ⏳ status (oldest pending)
  for(var i=0;i<tools.length;i++){
    if(tools[i].dataset.tname===name){
      var st=tools[i].querySelector('.tl-status');
      if(st&&st.textContent==='⏳'){tc=tools[i];break;}
    }
  }
  // Fallback: any pending tool-line
  if(!tc){
    for(var i=0;i<tools.length;i++){
      var st=tools[i].querySelector('.tl-status');
      if(st&&st.textContent==='⏳'){tc=tools[i];break;}
    }
  }
  if(!tc) return;

  var st=tc.querySelector('.tl-status');
  var durStr=durMs?' <span class="tl-time">'+(durMs/1000).toFixed(1)+'s</span>':'';
  if(isErr){
    st.innerHTML='❌'+durStr;st.className='tl-status tl-err';
  }else{
    st.innerHTML='✅'+durStr;st.className='tl-status tl-done';
  }

  S.toolCount++;$('st-c').textContent=S.toolCount;

  // Render diff if detected in result
  if(resultText&&hasDiff(resultText)){
    renderDiff(tc, resultText, toolPath||'');
  }
}

// Inline diff rendering (Claude Code style)
function renderDiff(refEl, diffText, filePath){
  var lines=diffText.split('\n');
  var db=div('diff-block');

  // Detect language
  var lang='';
  if(filePath){var ext=filePath.split('.').pop().toLowerCase();lang=LM[ext]||'';}

  // Count changes
  var add=0,del=0;
  lines.forEach(function(l){
    if(l.startsWith('+')&&!l.startsWith('+++'))add++;
    if(l.startsWith('-')&&!l.startsWith('---'))del++;
  });

  var plusMinus=(add?'+'+add:'')+(del?'  -'+del:'');
  var hdr=div('diff-hdr');
  hdr.innerHTML='<span>📝 '+plusMinus+(lang?'  ·  '+lang:'')+'</span><span style="margin-left:auto;font-size:10px">点击收起</span>';
  hdr.onclick=function(){db.classList.toggle('closed');hdr.querySelector('span:first-child').textContent=db.classList.contains('closed')?'▶ '+plusMinus:'📝 '+plusMinus;};

  var body=div('diff-body');
  var lineNum=0, inHunk=false;
  lines.forEach(function(l){
    if(l.startsWith('@@')){
      var h=div('diff-hunk');h.textContent=l;body.appendChild(h);
      var m=l.match(/@@\s+-\d+(?:,\d+)?\s+\+(\d+)/);if(m)lineNum=parseInt(m[1])-1;
      inHunk=true;return;
    }
    if(l.startsWith('---')||l.startsWith('+++')||l.startsWith('\\ ')) return;

    var dl=div('diff-line');
    if(l.startsWith('+')){
      dl.className+=' diff-add';
      dl.innerHTML='<span class="diff-num"></span><span class="diff-sig">+</span><span class="diff-code">'+hl(l.substring(1),lang)+'</span>';
    }else if(l.startsWith('-')){
      dl.className+=' diff-del';
      dl.innerHTML='<span class="diff-num"></span><span class="diff-sig">-</span><span class="diff-code">'+hl(l.substring(1),lang)+'</span>';
    }else{
      var ctx=l.startsWith(' ')?l.substring(1):l;
      dl.className+=' diff-ctx';
      lineNum++;
      dl.innerHTML='<span class="diff-num">'+lineNum+'</span><span class="diff-sig"> </span><span class="diff-code">'+esc(ctx)+'</span>';
    }
    body.appendChild(dl);
  });
  db.appendChild(hdr);db.appendChild(body);

  // Insert after the tool-line
  refEl.parentNode.insertBefore(db,refEl.nextSibling);
  scrollB();

  // Collapse if >30 lines
  var total=body.querySelectorAll('.diff-line').length;
  if(total>30){db.classList.add('closed');hdr.querySelector('span:first-child').textContent='▶ '+plusMinus;}
  if(total>50){body.style.maxHeight='300px';body.style.overflowY='auto';}
}

// Thinking block
function addThink(text){try{autoSave()}catch(e){}
  var last=msgs.lastElementChild;
  if(last&&last.classList.contains('think-block')){
    var b=last.querySelector('.think-b');
    if(b){b.textContent+=text;scrollB();return last;}
  }
  var el=div('think-block');
  el.innerHTML='<div class="think-h">🧠 思考</div><div class="think-b">'+esc(text)+'</div>';
  msgs.appendChild(el);
  el.querySelector('.think-h').onclick=function(){el.classList.toggle('collapsed');};
  scrollB();return el;
}

// System message
function addSys(text){try{autoSave()}catch(e){}
  var el=div('msg msg-sys');
  el.innerHTML='<div class="mc">'+esc(text)+'</div>';
  msgs.appendChild(el);scrollB();
}

// Error message
function addErr(text){try{autoSave()}catch(e){}
  var el=div('msg msg-err');
  el.innerHTML='<div class="mc">'+esc(text)+'</div>';
  msgs.appendChild(el);scrollB();
}

// ══════════════════════════════════════════════════
// SSE
// ══════════════════════════════════════════════════
// ─── SSE 连接（带自动重连 + 状态指示）───
var _sseRetry=0, _sseTimer=null;

function connectSSE(){
  if(S.sse){try{S.sse.close()}catch(e){}}
  S.sse=new EventSource('/api/stream');
  _sseRetry=0;

  // 连接状态
  S.sse.onopen=function(){
    _sseRetry=0;
    var dot=$('hd-s')?.querySelector('.hd-dot');
    if(dot){dot.style.background='var(--accent4)';dot.style.animation='none';}
  };

  S.sse.onerror=function(){
    S.sse.close();
    _sseRetry++;
    // 指数退避重连：1s, 2s, 4s, 8s... 最大 30s
    var delay=Math.min(1000*Math.pow(2,_sseRetry),30000);
    if(_sseTimer) clearTimeout(_sseTimer);
    _sseTimer=setTimeout(function(){connectSSE()},delay);
    // 状态指示
    var dot=$('hd-s')?.querySelector('.hd-dot');
    if(dot&&_sseRetry>2){dot.style.background='var(--accent5)';dot.style.animation='pi 1s infinite';}
  };

  S.sse.addEventListener('text',function(e){
    try{var d=JSON.parse(e.data);if(d.delta)addText(d.delta);}catch(x){}
  });

  S.sse.addEventListener('thought',function(e){
    try{var d=JSON.parse(e.data);if(d.delta)addThink(d.delta);}catch(x){}
  });

  S.sse.addEventListener('tool',function(e){
    try{var d=JSON.parse(e.data);
      if(d.subtype==='start'){addToolCall(d.tool_name,d.file_path||'',d.args_preview||'');addEvent('tool','→ '+d.tool_name+' '+d.file_path);}
      if(d.subtype==='result'){addToolResult(d.tool_name,d.status==='error',d.duration_ms||0,d.result||'',d.file_path||'');addEvent('tool',(d.status==='error'?'✗ ':'✔ ')+d.tool_name+(d.duration_ms?' '+(d.duration_ms/1000).toFixed(1)+'s':''));}
    }catch(x){}
  });

  S.sse.addEventListener('session',function(e){
    try{var d=JSON.parse(e.data);
      if(d.subtype==='start'){setBusy(1);addEvent('session','▶ start');}
      if(d.subtype==='end'){
        setBusy(0);
        addEvent('session','■ end');
      }
    }catch(x){}
  });

  S.sse.addEventListener('error',function(e){
    try{var d=JSON.parse(e.data);if(d.message){addErr(d.message);setBusy(0);addEvent('error',d.message);}}catch(x){}
  });

  S.sse.addEventListener('phase',function(e){
    try{var d=JSON.parse(e.data);if(d.workflow)updateWf(d.workflow);if(d.progress!==undefined)wff.style.width=(d.progress*100)+'%';}catch(x){}
  });

  S.sse.addEventListener('step',function(e){
    try{var d=JSON.parse(e.data);
      if(d.status&&d.step_name){updateWfStep(d.step_id||d.step_name,d.status,d.step_name,d.result||'');addEvent('step',d.status+' '+d.step_name);}
      if(d.status==='done'){var sep=div('step-sep step-done');sep.textContent='✔ 步骤 "'+(d.step_name||'')+'" 完成';msgs.appendChild(sep);scrollB();}
      if(d.status==='failed'){var sep=div('step-sep step-fail');sep.textContent='✗ 步骤 "'+(d.step_name||'')+'" 失败';msgs.appendChild(sep);scrollB();}
    }catch(x){}
  });

  S.sse.addEventListener('plan',function(e){
    try{var d=JSON.parse(e.data);
      if(d.subtype==='created'){
        var steps=(d.steps||[]).map(function(s,i){return{id:s.id||String(i),name:s.name,status:s.status||'pending'};});
        S.wfSteps=steps;S.wfDone=0;S.wfTotal=steps.length;
        updateWfBar();addEvent('plan','创建计划: '+(d.title||'')+' ('+steps.length+' 步)');
        // Show plan in chat
        if(steps.length>0){
          var p=div('msg msg-asst');
          var planHtml='<div class="mc"><b style="color:var(--accent2)">📋 计划: '+(d.title||'')+'</b><br>';
          steps.forEach(function(s,i){planHtml+='  '+(i+1)+'. '+esc(s.name)+'<br>';});
          planHtml+='<span style="color:var(--fg-3)">共 '+steps.length+' 步</span></div>';
          p.innerHTML=planHtml;msgs.appendChild(p);scrollB();
        }
      }
    }catch(x){}
  });
}

// ══════════════════════════════════════════════════
// SEND / STOP / RETRY / CLEAR
// ══════════════════════════════════════════════════

function send(){
  var t=ib.value.trim();if(!t||S.busy)return;
  S.last=t;ib.value='';ib.style.height='auto';
  addUser(t);setBusy(1);
  fetch('/api/send',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({text:t})})
    .then(function(r){return r.json()})
    .then(function(d){if(d.status!=='ok'){addErr(d.message||'发送失败');setBusy(0);}})
    .catch(function(e){addErr('网络错误: '+e.message);setBusy(0);});
}

function stop(){if(!S.busy)return;fetch('/api/stop',{method:'POST'}).catch(function(){});setBusy(0);addSys('⏹ 已终止');}
function retry(){if(S.busy||!S.last)return;ib.value=S.last;send();}

function clear(){try{autoSave()}catch(e){}
  msgs.innerHTML='';
  S.toolCount=0;S.wfSteps=[];S.wfDone=0;S.wfTotal=0;$('st-c').textContent='0';
  S.events=[];
  wff.style.width='0%';wfc.textContent='0/0';
  $('wf-c').innerHTML='<div style="padding:20px;text-align:center;color:var(--fg-3);font-size:12px">📋 发送指令后自动创建</div>';
  renderEvLog();
  localStorage.removeItem(STORAGE_KEY);
  fetch('/api/clear',{method:'POST'}).catch(function(){});
  addSys('🗑 对话已清空');
  toast('对话已清空','info');
}

function setBusy(b){
  S.busy=b;sb.disabled=b;sb.textContent=b?'...':'发送';ib.disabled=b;$('btn-stop').disabled=!b;
  if(b){hds.className='hd-status busy';st.textContent='工作中';}else{hds.className='hd-status';st.textContent='就绪';}
}

// ══════════════════════════════════════════════════
// WORKFLOW
// ══════════════════════════════════════════════════

function updateWf(wf){try{autoSave()}catch(e){}
  if(!wf)return;
  if(wf.steps){S.wfSteps=wf.steps;S.wfTotal=wf.steps.length;S.wfDone=wf.steps.filter(function(s){return s.status==='done'||s.status==='skipped';}).length;}
  if(wf.progress!==undefined)wff.style.width=(wf.progress*100)+'%';
  renderWfPanel();updateWfBar();
}

function updateWfStep(id,status,name,result){try{autoSave()}catch(e){}
  for(var i=0;i<S.wfSteps.length;i++){if(S.wfSteps[i].id===id||S.wfSteps[i].name===name){S.wfSteps[i].status=status;break;}}
  S.wfDone=S.wfSteps.filter(function(s){return s.status==='done'||s.status==='skipped';}).length;
  S.wfTotal=S.wfSteps.length;
  renderWfPanel();updateWfBar();
}

function renderWfPanel(){
  var c=$('wf-c');
  if(!S.wfSteps||S.wfSteps.length===0){c.innerHTML='<div style="padding:20px;text-align:center;color:var(--fg-3);font-size:12px">📋 发送指令后自动创建</div>';return;}
  var done=0,cur='',next='';
  S.wfSteps.forEach(function(s){if(s.status==='done'||s.status==='skipped')done++;if(s.status==='running')cur=s.name;if(s.status==='pending'&&!next)next=s.name;});
  var prog=S.wfSteps.length>0?Math.round((done/S.wfSteps.length)*100):0;
  var h='<div class="wf-sec">';
  h+='<div class="wf-hdr"><div class="wf-title">📋 工作流</div><div class="wf-badge run">'+done+'/'+S.wfSteps.length+'</div></div>';
  h+='<div class="wf-prog"><div class="wf-pl"><span>进度</span><span>'+prog+'%</span></div><div class="wf-pt"><div class="wf-pf" style="width:'+prog+'%"></div></div></div>';
  h+='<div class="wf-st">';
  S.wfSteps.forEach(function(s){
    var icon={'pending':'⏳','running':'▶️','done':'✅','failed':'❌','skipped':'⏭️'}[s.status]||'⏳';
    var cls={'pending':'','running':'cur','done':'don','failed':'fail'}[s.status]||'';
    h+='<div class="wf-step '+cls+'"><span class="wf-si">'+icon+'</span><span class="wf-sn">'+esc(s.name)+'</span><span class="wf-ss '+s.status.substring(0,3)+'">'+s.status+'</span></div>';
  });
  h+='</div></div>';
  c.innerHTML=h;
}

function updateWfBar(){
  var prog=S.wfTotal>0?Math.round((S.wfDone/S.wfTotal)*100):0;
  wff.style.width=prog+'%';
  wfc.textContent=S.wfDone+'/'+S.wfTotal;
  var cur='',next='';
  S.wfSteps.forEach(function(s){if(s.status==='running')cur=s.name;if(s.status==='pending'&&!next)next=s.name;});
  wfcur.textContent=cur||'';wfnx.textContent=next?'→ '+next:'';
}

// ══════════════════════════════════════════════════
// EVENT LOG
// ══════════════════════════════════════════════════

var EV_TYPES=['all','session','phase','step','thought','tool','text','plan','error'];
function renderEvFilters(){
  var c=$('ev-fil');c.innerHTML='';
  EV_TYPES.forEach(function(t){
    var b=document.createElement('button');b.className='ev-f'+(t==='all'?' act':'');b.textContent=t;
    b.onclick=function(){c.querySelectorAll('.ev-f').forEach(function(x){x.classList.remove('act')});b.classList.add('act');S.evFilter=t;renderEvLog();};
    c.appendChild(b);
  });
}

function addEvent(type,data){try{autoSave()}catch(e){}
  S.events.push({type:type,data:data||'',ts:Date.now()});
  if(S.events.length>500)S.events.shift();
  renderEvLog();
}

function renderEvLog(){
  var c=$('ev-c');
  var filtered=S.evFilter==='all'?S.events:S.events.filter(function(e){return e.type===S.evFilter});
  if(filtered.length===0){c.innerHTML='<div style="padding:20px;text-align:center;color:var(--fg-3);font-size:12px">'+(S.evFilter==='all'?'等待事件...':'无 '+S.evFilter+' 事件')+'</div>';return;}
  var show=filtered.slice(-80);
  var h='';
  show.forEach(function(e){
    var t=new Date(e.ts).toLocaleTimeString();
    var d=typeof e.data==='string'?e.data:JSON.stringify(e.data);
    h+='<div class="ev-item"><span class="ev-tm">'+t+'</span><span class="ev-ty '+e.type+'">'+e.type.substring(0,4)+'</span><span class="ev-da">'+esc(d.substring(0,80))+'</span></div>';
  });
  c.innerHTML=h;c.scrollTop=c.scrollHeight;
}

// ══════════════════════════════════════════════════
// TOOLS PANEL
// ══════════════════════════════════════════════════

var TCATS=[
  {n:'📁 文件',c:'#60a5fa',ts:['read','write','edit','replace','glob','grep','move','copy','delete','mkdir','download','revert']},
  {n:'💻 命令',c:'#34d399',ts:['bash','background']},
  {n:'🌐 网络/浏览器',c:'#fb923c',ts:['web','web_search','browser','ask_user']},
  {n:'🖥️ 系统',c:'#f472b6',ts:['process','service','registry','gui','monitor']},
  {n:'🔬 分析',c:'#a78bfa',ts:['ast','dep_graph','call_chain','trace_error']},
  {n:'📋 规划',c:'#38bdf8',ts:['plan','task','project_memory']},
  {n:'🧠 子Agent',c:'#c084fc',ts:['subagent','mcp']},
  {n:'🧠 记忆',c:'#34d399',ts:['remember']},
  {n:'⏰ 自动化',c:'#fbbf24',ts:['schedule','watch','websocket']},
  {n:'🧪 测试',c:'#fb7185',ts:['test','dep']},
  {n:'💬 其他',c:'#94a3b8',ts:['hash_file']},
];

window._toolStats={};

function buildTools(){
  var c=$('tools-c');c.innerHTML='';
  TCATS.forEach(function(cat){
    var hdr=div('tool-cat');hdr.style.color=cat.c;hdr.textContent=cat.n+' ('+cat.ts.length+')';c.appendChild(hdr);
    var g=div('tool-grd');
    cat.ts.forEach(function(name){
      window._toolStats[name]=0;
      var el=div('tool-item');el.innerHTML='<span class="td idle" id="td-'+name+'"></span><span class="ti">'+(I[name]||'⚡')+'</span><span class="tn">'+name+'</span><span class="tc" id="tcnt-'+name+'">0</span>';
      g.appendChild(el);
    });
    c.appendChild(g);
  });
}

function updateTD(name,status){
  var d=$('td-'+name);if(d){d.className='td '+status;}
  if(status==='done'||status==='error'){
    window._toolStats[name]=(window._toolStats[name]||0)+1;
    var cnt=$('tcnt-'+name);if(cnt)cnt.textContent=window._toolStats[name];
  }
}

// Override tool status tracking
var _origAddToolResult=addToolResult;
addToolResult=function(name,isErr,durMs,resultText,path){
  _origAddToolResult(name,isErr,durMs,resultText,path);
  updateTD(name,isErr?'error':'done');
};
var _origAddToolCall=addToolCall;
addToolCall=function(name,path,extra){
  updateTD(name,'running');
  _origAddToolCall(name,path,extra);
};

// ══════════════════════════════════════════════════
// CONFIG
// ══════════════════════════════════════════════════

function buildConfig(){
  var c=$('cfg-c');
  c.innerHTML='<div class="cfg-g"><label class="cfg-l">LLM 提供商</label><select class="cfg-s" id="cfg-p"><option>Anthropic Claude</option><option>OpenAI</option><option>DeepSeek</option><option>Gemini</option><option>Ollama</option></select></div>'
    +'<div class="cfg-g"><label class="cfg-l">API Key</label><input class="cfg-i" type="password" id="cfg-k" placeholder="sk-..."></div>'
    +'<div class="cfg-g"><label class="cfg-l">模型</label><input class="cfg-i" type="text" id="cfg-m" placeholder="claude-sonnet-4-20250514"></div>'
    +'<div class="cfg-g"><label class="cfg-l">Base URL (可选)</label><input class="cfg-i" type="text" id="cfg-u" placeholder="https://api.anthropic.com"></div>'
    +'<button class="cfg-btn" onclick="A.saveConfig()">💾 保存配置</button>'
    +'<button class="cfg-t" onclick="A.testConfig()">🔄 测试连接</button>'
    +'<div id="cfg-st" style="margin-top:6px;font-size:11px;color:var(--fg-3);display:none"></div>';

  // Load current config
  fetch('/api/config').then(function(r){return r.json()}).then(function(d){
    $('cfg-p').value=d.provider||'DeepSeek';$('cfg-m').value=d.model||'';$('cfg-u').value=d.base_url||'';
    $('cfg-k').placeholder=d.api_key?'当前已配置':'输入 API Key';
    // Sync header
    $('st-p').textContent=d.provider||'—';$('st-m').textContent=d.model||'—';
    if(!d.api_key)addSys('⚠️ 请在右侧面板 ⚙ 中配置 API Key');
  }).catch(function(){});
}

// ══════════════════════════════════════════════════
// SUB-AGENTS
// ══════════════════════════════════════════════════

function buildAgents(){
  var c=$('ag-c');
  var agents=[{n:'🧠 code-architect',d:'分析代码架构、设计方案、输出实施蓝图',m:'claude-sonnet-4-20250514',ts:['read','glob','grep','web_search']},{n:'🔍 code-reviewer',d:'审查代码质量、发现潜在问题、给出改进建议',m:'claude-sonnet-4-20250514',ts:['read','glob','grep','ast','dep_graph','call_chain']}];
  var h='';
  agents.forEach(function(a){
    h+='<div class="ag-card" onclick="A.promptAgent(\''+a.n+'\')"><div class="ag-n">'+a.n+'</div><div class="ag-d">'+a.d+'</div><div class="ag-m">Model: '+a.m+'</div><div class="ag-ts">';
    a.ts.forEach(function(t){h+='<span class="ag-tt">'+t+'</span>';});
    h+='</div></div>';
  });
  c.innerHTML=h;
}

// ══════════════════════════════════════════════════
// MCP
// ══════════════════════════════════════════════════

function loadMCPServers(){
  fetch('/api/mcp/servers')
    .then(function(r){return r.json()})
    .then(function(d){
      var c=$('mcp-c');
      if(d.status!=='ok'||!d.servers||d.servers.length===0){
        c.innerHTML='<div class="mcp-empty">🔌 暂无 MCP 服务器连接</div>'
          +'<button class="mcp-add-btn" onclick="A.showMCPForm()">+ 添加 MCP 服务器</button>';
        if(!window._mcpFormAdded) c.innerHTML+=buildMCPForm();
        return;
      }
      var h='';
      d.servers.forEach(function(s){
        var connected=s.connected||false;
        h+='<div class="mcp-card">'
          +'<div class="mcp-hdr"><div class="mcp-n"><span class="mcp-dot '+(connected?'':'off')+'"></span>'+esc(s.name||s)+'</div>'
          +'<button class="mcp-act '+(connected?'disc':'conn')+'" onclick="A.'+(connected?'disconnectMCP':'connectMCP')+'(\''+esc(s.name||s)+'\')">'+(connected?'断开':'连接')+'</button></div>';
        if(s.command) h+='<div class="mcp-cmd">'+esc(s.command)+' '+(s.args||[]).join(' ')+'</div>';
        var toolNames = s.tool_names || [];
        if(toolNames.length > 0){
          h+='<div class="mcp-ts">';
          toolNames.forEach(function(t){h+='<span class="mcp-tt">'+esc(t)+'</span>';});
          h+='</div>';
        }
        h+='</div>';
      });
      h+='<button class="mcp-add-btn" onclick="A.showMCPForm()">+ 连接新 MCP 服务器</button>';
      h+=buildMCPForm();
      c.innerHTML=h;
    })
    .catch(function(){
      var c=$('mcp-c');
      c.innerHTML='<div class="mcp-empty">🔌 无法加载 MCP 服务器</div>'
    });
}

function buildMCPForm(){
  return '<div class="mcp-form" id="mcp-form" style="display:none">'
    +'<input type="text" id="mcp-name" placeholder="服务器名称 (如 playwright)">'
    +'<input type="text" id="mcp-cmd" placeholder="启动命令 (如 npx)">'
    +'<input type="text" id="mcp-args" placeholder="参数 (JSON 数组，如 [\"-y\",\"@anthropic/mcp-playwright\"])">'
    +'<div class="mcp-row"><button style="background:var(--accent2);color:#fff" onclick="A.doConnectMCP()">连接</button>'
    +'<button style="background:rgba(255,255,255,0.05);color:var(--fg-2)" onclick="A.hideMCPForm()">取消</button></div></div>';
}

function showMCPForm(){
  var f=$('mcp-form');if(f)f.style.display='block';
}
function hideMCPForm(){
  var f=$('mcp-form');if(f)f.style.display='none';
}
function doConnectMCP(){
  var name=$('mcp-name'),cmd=$('mcp-cmd'),args=$('mcp-args');
  if(!name.value.trim()||!cmd.value.trim()){toast('请填写服务器名称和命令','error');return;}
  var body={name:name.value.trim(),command:cmd.value.trim()};
  if(args.value.trim()){
    try{body.args=JSON.parse(args.value.trim());}catch(e){toast('参数格式错误，需要 JSON 数组','error');return;}
  }
  fetch('/api/mcp/connect',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)})
    .then(function(r){return r.json()})
    .then(function(d){
      if(d.status==='ok'){toast('✅ 已连接: '+name.value,'success');name.value='';cmd.value='';args.value='';$('mcp-form').style.display='none';loadMCPServers();}
      else{toast('❌ '+(d.message||'连接失败'),'error');}
    }).catch(function(e){toast('❌ '+e.message,'error');});
}
function disconnectMCP(name){
  fetch('/api/mcp/disconnect',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({name:name})})
    .then(function(r){return r.json()})
    .then(function(d){
      if(d.status==='ok'){toast('✅ 已断开: '+name,'success');loadMCPServers();}
      else{toast('❌ '+(d.message||'断开失败'),'error');}
    }).catch(function(e){toast('❌ '+e.message,'error');});
}

// ══════════════════════════════════════════════════
// SETTINGS MODAL
// ══════════════════════════════════════════════════

function openSettings(){
  fetch('/api/config').then(function(r){return r.json()}).then(function(d){
    $('s-prov').value=d.provider||'DeepSeek';$('s-mod').value=d.model||'';$('s-url').value=d.base_url||'';
    $('s-key').value='';$('s-key').placeholder=d.api_key?'当前已配置':'输入 API Key';
  }).catch(function(){});
  $('settings-modal').classList.add('show');
}
function closeSettings(){$('settings-modal').classList.remove('show');}
function saveSettings(){
  var p=$('s-prov').value,k=$('s-key').value.trim(),m=$('s-mod').value.trim(),u=$('s-url').value.trim();
  if(!k){toast('请输入 API Key','error');return;}
  var body={provider:p,model:m,base_url:u};if(k)body.api_key=k;
  fetch('/api/config',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)})
    .then(function(r){return r.json()}).then(function(d){
      if(d.status==='ok'){$('st-p').textContent=p;$('st-m').textContent=m;toast('✅ 已保存: '+p+' / '+m,'success');closeSettings();
        // Sync panel config
        var cp=$('cfg-p');if(cp)cp.value=p;var cm=$('cfg-m');if(cm)cm.value=m;
      }else{toast('❌ '+(d.message||'失败'),'error');}
    }).catch(function(e){toast('❌ '+e.message,'error');});
}

// ══════════════════════════════════════════════════
// TOAST
// ══════════════════════════════════════════════════

function toast(msg,t){
  t=t||'info';
  var el=div('toast'+(t==='success'?' s':t==='error'?' e':''));
  el.innerHTML=(t==='success'?'✅':t==='error'?'❌':'ℹ️')+' '+msg;
  toasts.appendChild(el);
  setTimeout(function(){el.classList.add('out');setTimeout(function(){el.remove();},250);},3000);
}

// ══════════════════════════════════════════════════
// SCROLL
// ══════════════════════════════════════════════════

msgs.addEventListener('scroll',function(){
  var th=60;S.ab=(msgs.scrollHeight-msgs.scrollTop-msgs.clientHeight)<th;
  scrollH.classList.toggle('show',!S.ab);
});
scrollH.onclick=function(){S.ab=1;scrollB();this.classList.remove('show');};

// ══════════════════════════════════════════════════
// EXPORTS
// ══════════════════════════════════════════════════

window.A={
  send:send,stop:stop,retry:retry,clear:clear,
  openSettings:openSettings,closeSettings:closeSettings,saveSettings:saveSettings,
  saveConfig:function(){
    var p=$('cfg-p'),k=$('cfg-k'),m=$('cfg-m'),u=$('cfg-u');
    if(!k||!k.value.trim()){toast('请输入 API Key','error');return;}
    var body={provider:p.value,model:m.value,base_url:u.value};
    if(k.value.trim())body.api_key=k.value.trim();
    fetch('/api/config',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)})
      .then(function(r){return r.json()}).then(function(d){
        if(d.status==='ok'){$('st-p').textContent=p.value;$('st-m').textContent=m.value;var st=$('cfg-st');st.style.display='block';st.style.color='var(--accent4)';st.textContent='✅ 保存成功';toast('✅ 配置已保存','success');k.value='';}else{var st=$('cfg-st');st.style.display='block';st.style.color='var(--accent6)';st.textContent='❌ '+(d.message||'失败');}
      }).catch(function(e){var st=$('cfg-st');st.style.display='block';st.style.color='var(--accent6)';st.textContent='❌ '+e.message;});
  },
  testConfig:function(){
    var st=$('cfg-st');st.style.display='block';st.textContent='🔄 测试中...';
    fetch('/api/context').then(function(r){return r.json()}).then(function(d){
      if(d.has_key){st.style.color='var(--accent4)';st.textContent='✅ 连接正常 · '+(d.provider||'')+' / '+(d.model||'');toast('✅ 连接正常','success');}else{st.style.color='var(--accent5)';st.textContent='⚠️ 请先配置 API Key';}
    }).catch(function(e){st.style.color='var(--accent6)';st.textContent='❌ '+e.message;});
  },
  promptAgent:function(name){ib.value='使用 '+name+' 分析 ';ib.focus();toast('🧠 在输入框中编辑指令','info');},
  loadMCPServers:loadMCPServers,
  showMCPForm:showMCPForm,hideMCPForm:hideMCPForm,
  doConnectMCP:doConnectMCP,disconnectMCP:disconnectMCP,
  toast:toast,
};

// ══════════════════════════════════════════════════
// INIT
// ══════════════════════════════════════════════════

function init(){
  ib.addEventListener('input',function(){this.style.height='auto';this.style.height=Math.min(this.scrollHeight,100)+'px'});
  ib.addEventListener('keydown',function(e){if(e.key==='Enter'&&!e.shiftKey){e.preventDefault();send()}});

  // Tab switching
  document.querySelectorAll('.p-tab').forEach(function(t){
    t.addEventListener('click',function(){
      document.querySelectorAll('.p-tab,.p-content').forEach(function(x){x.classList.remove('active')});
      t.classList.add('active');$('pn-'+t.dataset.t).classList.add('active');
    });
  });

  // Modal backdrop
  $('settings-modal').addEventListener('click',function(e){if(e.target===this)closeSettings()});
  document.addEventListener('keydown',function(e){if(e.key==='Escape')closeSettings()});

  // Build panels
  buildTools();renderEvFilters();buildConfig();buildAgents();
  loadMCPServers();

  // Restore session from localStorage（刷新不丢消息）
  var restored = loadState();
  if(!restored){
    setTimeout(function(){addSys('⚡ AgiCode v2 · 全透明自主 AI 智能体')},100);
  }

  // Connect SSE
  connectSSE();

  // Hide loading
  setTimeout(function(){$('loading').classList.add('hidden')},800);

  // Welcome toast (only on fresh session)
  if(!restored){
    setTimeout(function(){toast('🎉 欢迎使用 AgiCode','success')},1200);
  }

  // Before unload: 保存最后状态，防止刷新丢数据
  window.addEventListener('beforeunload', function(){
    saveState();
  });

  // Periodic context check
  setInterval(function(){
    fetch('/api/context').then(function(r){return r.json()}).then(function(d){
      if(d.busy!==undefined&&d.busy!==S.busy)setBusy(d.busy);
      if(d.provider){$('st-p').textContent=d.provider||$('st-p').textContent;$('st-m').textContent=d.model||$('st-m').textContent}
    }).catch(function(){});
  },10000);
}

if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',init);else init();

})();
