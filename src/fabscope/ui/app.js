'use strict';
const $ = id => document.getElementById(id);
const descriptions = {
  EMPTY:'Buồng trống', LOADED:'Wafer sẵn sàng', PREPARING:'Đang chuẩn bị', PROCESSING:'Đang xử lý',
  COMPLETED:'Đã hoàn tất', FAULT:'Lỗi máy giả lập · cần xóa lỗi'
};
const eventNames = {WaferLoaded:'Wafer đã được nạp',RunStarted:'Lượt chạy mới được tạo',PreparationStarted:'Bắt đầu chuẩn bị',ProcessingStarted:'Bắt đầu xử lý mô phỏng',TelemetrySampled:'Ghi tín hiệu minh họa',RunCompleted:'Lượt chạy hoàn tất',RunAborted:'Lượt chạy được dừng',MachineFaultRaised:'Lỗi máy giả lập',FaultCleared:'Đã xóa lỗi máy',WaferUnloaded:'Wafer đã được lấy ra'};
// These are API snapshots and delivery bookkeeping, never a second machine model.
let observer = null, clientState = null, pendingCommand = null, cursor = 0;
let appliedIds = new Set(), waitingEvents = new Map(), clientStale = true;
let refreshing = false, actionBusy = false, scenarioBusy = false, initializedRecipes = false;
let serverSession = null, renderedSequence = -1, evidence = null;

async function api(path, body) {
  let response;
  try { response = await fetch(path, {method:body === undefined ? 'GET':'POST', headers:{'Content-Type':'application/json'}, ...(body === undefined ? {}:{body:JSON.stringify(body)}), signal:AbortSignal.timeout(path.includes('/scenarios/') ? 180000 : 10000)}); }
  catch (error) { throw Object.assign(new Error('Không liên lạc được dịch vụ localhost. '+error.message), {code:'SERVICE_UNAVAILABLE'}); }
  const data = await response.json();
  if (!response.ok) throw Object.assign(new Error(data.message || data.detail?.message || 'Yêu cầu bị từ chối'), {code:data.code || data.detail?.code || 'HTTP_'+response.status, status:response.status});
  return data;
}

function renderObserver(s) {
  $('machine-name').textContent = s.machine_id;
  $('machine-state').textContent = s.state;
  $('machine-state').classList.toggle('stale', s.state === 'FAULT');
  $('machine-explanation').textContent = descriptions[s.state];
  $('wafer-id').textContent = s.wafer_id || 'Chưa nạp';
  $('sim-time').textContent = s.sim_time_s.toFixed(2);
  $('progress').textContent = s.signals.step_progress_pct.toFixed(0)+'%';
  $('progress-bar').style.width = s.signals.step_progress_pct+'%';
  window.fabSnapshot = s;
  window.fabScene?.update(s);
  $('signal-value').textContent = s.signals.demo_process_level.toFixed(2)+' đơn vị quy ước';
  $('play').textContent = s.gateway.playing ? 'Ⅱ Pause':'▶ Chạy';
  $('clock-label').textContent = s.gateway.playing ? 'Đang chạy':'Pause';
  $('advance').disabled = $('finish').disabled = s.gateway.playing || actionBusy;
  $('disconnect').textContent = s.gateway.disconnected ? 'Nối lại gateway':'Ngắt kết nối';
  $('lost-ack').textContent = s.gateway.lost_ack_once ? 'Mất phản hồi: BẬT':'Mất phản hồi';
  $('duplicates').checked = s.gateway.duplicate_delivery;
  if (!initializedRecipes) {
    $('recipe').replaceChildren(...s.config.recipes.map((r, i) => {const option = document.createElement('option');option.value=i;option.textContent=`${r.recipe_id} · v${r.recipe_version}`;return option;}));
    initializedRecipes = true;
    recipeInfo();
  }
  updateControls();
}

function updateControls() {
  // Command affordances use the last equipment response, including when stale.
  const state = clientState?.state;
  const enabled = {load:state==='EMPTY', start:state==='LOADED', abort:['PREPARING','PROCESSING'].includes(state),unload:['LOADED','COMPLETED'].includes(state),'clear-fault':state==='FAULT'};
  for (const [id, allowed] of Object.entries(enabled)) $(id).disabled = !allowed || actionBusy || Boolean(pendingCommand);
  $('machine-fault').disabled = !['PREPARING','PROCESSING'].includes(observer?.state) || actionBusy;
  $('retry').disabled = actionBusy;
  $('play').disabled = actionBusy || !observer;
  $('wafer-input').disabled = state!=='EMPTY';
  $('recipe').disabled = state!=='LOADED';
}

function recipeInfo() {
  const r = observer?.config.recipes[Number($('recipe').value)];
  if(r) $('recipe-info').textContent=`Chuẩn bị ${r.prepare_s}s · xử lý ${r.process_s}s`;
}

function applyEvents(events) {
  for(const event of events) if(!appliedIds.has(event.event_id) && event.sequence>cursor) waitingEvents.set(event.sequence,event);
  while(waitingEvents.has(cursor+1)) {
    const event = waitingEvents.get(cursor+1);
    waitingEvents.delete(cursor+1);
    appliedIds.add(event.event_id);
    cursor++;
  }
}

async function refreshClient() {
  try {
    // Only /equipment can change what the client knows.
    clientState = await api('/equipment/state');
    let more = true, pages = 0;
    while(more && pages++<100) {
      const page = await api(`/equipment/events?after_sequence=${cursor}&limit=30`);
      const before = cursor;
      applyEvents(page.events);
      more = page.has_more;
      if(more && before===cursor) throw new Error('Thiếu sự kiện liên tục. Cursor được giữ để lấy bù.');
    }
    if(more) throw new Error('Đang lấy bù nhật ký; góc nhìn chưa đồng bộ đủ.');
    clientStale=false;
    $('client-note').textContent='';
    $('connection-badge').textContent='Đã kết nối';
  } catch(error) {
    clientStale=true;
    $('client-note').textContent='DỮ LIỆU CŨ · chưa nhận cập nhật';
    $('connection-badge').textContent=error.code==='DISCONNECTED' ? 'Gateway đã ngắt':'Chưa đồng bộ';
  }
  $('connection-badge').classList.toggle('stale',clientStale);
  $('client-state').textContent=clientState?.state || 'Chưa nhận';
  $('client-time').textContent=clientState ? `t=${clientState.sim_time_s.toFixed(2)}s`:'—';
  $('cursor').textContent=cursor;
  $('event-count').textContent=appliedIds.size;
  updateControls();
}

function renderJournal(trace) {
  evidence=trace;
  if(renderedSequence===trace.state.sequence) return;
  renderedSequence=trace.state.sequence;
  const events=trace.events.slice(-100).reverse();
  if(events.length) $('timeline').replaceChildren(...events.map(event=>{
    const row=document.createElement('button');row.className='timeline-event';
    const time=document.createElement('time');time.textContent=event.sim_time_s.toFixed(2)+'s';
    const dot=document.createElement('span');dot.className='dot';
    const desc=document.createElement('span');desc.className='event-desc';desc.textContent=eventNames[event.type]||event.type;
    const detail=document.createElement('small');detail.textContent=event.type==='TelemetrySampled' ? `mức ${event.payload.demo_process_level} · ${event.payload.step_progress_pct}%`:(event.run_id?.split(':').at(-1)||event.wafer_id||'');desc.append(detail);
    const seq=document.createElement('span');seq.className='sequence';seq.textContent='#'+event.sequence;
    row.append(time,dot,desc,seq);row.onclick=()=>{$('event-detail').textContent=JSON.stringify(event,null,2);$('event-dialog').showModal();};return row;
  }));
  else {const empty=document.createElement('p');empty.className='empty';empty.textContent='Chưa có sự kiện. Hãy nạp wafer đầu tiên.';$('timeline').replaceChildren(empty);}
  const samples=trace.events.filter(e=>e.type==='TelemetrySampled' && e.run_id===trace.state.run_id).slice(-60);
  $('signal-caption').textContent=samples.length ? `${trace.state.run_id.split(':').at(-1)} · ${samples.length} mẫu gần nhất · t=${samples[0].sim_time_s}–${samples.at(-1).sim_time_s}s`:'Chưa có mẫu của lượt chạy hiện tại.';
  $('signal-line').setAttribute('points',samples.map((e,i)=>`${samples.length<2?0:i*300/(samples.length-1)},${65-Math.min(100,Math.max(0,e.payload.demo_process_level))*.6}`).join(' '));
  $('run-count').textContent=trace.runs.length;
  $('runs').replaceChildren(...trace.runs.slice().reverse().map(run=>{
    const row=document.createElement('tr');
    [run.run_id.split(':').at(-1),run.wafer_id,`${run.recipe_id} v${run.recipe_version}`,run.status,`${run.started_at}s → ${run.ended_at===null?'đang chạy':run.ended_at+'s'}`].forEach(value=>{const td=document.createElement('td');td.textContent=value;row.append(td);});
    row.title=run.run_id;return row;
  }));
}

async function refresh() {
  if(refreshing) return;
  refreshing=true;
  try {
    const s=await api('/sim/state');
    if(serverSession && serverSession!==s.session_id) {clientState=null;cursor=0;appliedIds.clear();waitingEvents.clear();renderedSequence=-1;pendingCommand=null;$('retry').classList.add('hidden');}
    serverSession=s.session_id;observer=s;
    $('service-banner').classList.add('hidden');
    renderObserver(s);
    await refreshClient();
    if(s.sequence!==renderedSequence) renderJournal(await api('/sim/evidence'));
  } catch(error) {
    $('service-banner').textContent='DỊCH VỤ CHƯA SẴN SÀNG · '+error.message;
    $('service-banner').classList.remove('hidden');
    clientStale=true;
    window.fabScene?.setStale(true);
    $('connection-badge').textContent='Dữ liệu cũ';$('connection-badge').classList.add('stale');
    $('client-note').textContent='Không nhận được dữ liệu mới. Trạng thái hiển thị là lần cuối đã nhận.';
  } finally {refreshing=false;}
}

async function action(fn) {
  if(actionBusy) return;
  actionBusy=true;updateControls();
  try {await fn();} catch(error) {feedback(error.code+' · '+error.message,true);}
  finally {actionBusy=false;updateControls();await refresh();}
}
function feedback(message,error=false) {$('command-result').textContent=message;$('command-result').classList.toggle('error',error);}
async function sendCommand(command) {
  pendingCommand=command;
  try {
    const result=await api('/equipment/commands',command);
    feedback(`${result.code}${result.run_id?' · '+result.run_id.split(':').at(-1):''}${result.accepted?'':' · '+result.message}`,!result.accepted);
    $('command-result').title=`Command ID: ${command.command_id}`;
    pendingCommand=null;$('retry').classList.add('hidden');
  } catch(error) {
    if(error.status===422) {pendingCommand=null;$('retry').classList.add('hidden');}
    else $('retry').classList.remove('hidden');
    feedback(`${error.code} · Gửi lại cùng ID để nhận kết quả.`,true);
    $('command-result').title=`${error.message} · Command ID: ${command.command_id}`;
  }
}
function command(type,parameters={}) {
  if(pendingCommand) return;
  return action(()=>sendCommand({schema_version:'1.0',command_id:'ui-'+crypto.randomUUID(),machine_id:observer.machine_id,type,parameters}));
}
function setFault(type,enabled=true) {return action(async()=>{const result=await api('/sim/faults',{type,enabled});if(result.accepted===false) feedback(result.code,true);});}
$('load').onclick=()=>command('LOAD',{wafer_id:$('wafer-input').value.trim()});
$('start').onclick=()=>{const r=observer.config.recipes[Number($('recipe').value)];command('START',{recipe_id:r.recipe_id,recipe_version:r.recipe_version});};
$('abort').onclick=()=>command('ABORT');$('unload').onclick=()=>command('UNLOAD');$('clear-fault').onclick=()=>command('CLEAR_FAULT');
$('retry').onclick=()=>action(()=>sendCommand(pendingCommand));
$('machine-fault').onclick=()=>setFault('machine');
$('disconnect').onclick=()=>setFault('disconnected',!observer.gateway.disconnected);
$('lost-ack').onclick=()=>setFault('lost_ack_once',!observer.gateway.lost_ack_once);
$('duplicates').onchange=()=>setFault('duplicate_delivery',$('duplicates').checked);
$('play').onclick=()=>action(()=>api('/sim/clock/mode',{playing:!observer.gateway.playing}));
$('advance').onclick=()=>action(()=>api('/sim/clock/advance',{seconds:1}));
$('finish').onclick=()=>action(()=>api('/sim/clock/advance',{seconds:15}));
$('recipe').onchange=recipeInfo;
$('close-dialog').onclick=()=>$('event-dialog').close();
document.querySelector('nav a[href="#scenarios"]').addEventListener('click',()=>{$('scenarios').open=true;});

async function runScenario(id) {
  if(scenarioBusy) return;
  scenarioBusy=true;document.body.classList.add('busy-scenario');
  const result=$('scenario-result');result.classList.remove('hidden');result.textContent=`Đang chạy ${id==='all'?'17 kịch bản':id} trên server riêng… Các kịch bản restart sẽ thay tiến trình thật.`;
  try {
    const data=await api(`/sim/scenarios/${id}/run`,{});result.replaceChildren();
    for(const report of data.reports) {
      const row=document.createElement('div');row.className='report-row'+(report.status==='PASS'?'':' fail');
      const status=document.createElement('strong');status.textContent=report.status;
      const name=document.createElement('span');name.textContent=`${report.scenario_id} · ${report.name}`;
      const detail=document.createElement('small');detail.textContent=`${report.checks.filter(c=>c.status==='PASS').length}/${report.checks.length} điều kiện đạt`;
      const link=document.createElement('a');link.textContent='Mở báo cáo & bằng chứng ↗';link.href=report.html_url;link.target='_blank';link.rel='noopener';row.append(status,name,detail,link);result.append(row);
      if(id!=='all') for(const check of report.checks) {
        const element=document.createElement('details');element.className='report-check';
        const summary=document.createElement('summary');summary.textContent=`${check.status} · ${check.name}`;
        const pre=document.createElement('pre');pre.textContent=`Mong đợi: ${JSON.stringify(check.expected,null,2)}\nThực tế: ${JSON.stringify(check.actual,null,2)}`;element.append(summary,pre);result.append(element);
      }
    }
  } catch(error) {result.textContent='Chưa nhận được kết quả kiểm thử: '+error.message;}
  finally {scenarioBusy=false;document.body.classList.remove('busy-scenario');}
}
$('featured-run').onclick=()=>runScenario('B01');$('run-all').onclick=()=>runScenario('all');
async function init() {
  await refresh();
  try {
    const catalog=await api('/sim/scenarios');
    $('scenario-list').replaceChildren(...catalog.scenarios.map(s=>{const row=document.createElement('div');row.className='scenario-item';const id=document.createElement('span');id.className='scenario-id';id.textContent=s.id;const name=document.createElement('span');name.textContent=s.name;const button=document.createElement('button');button.textContent='Chạy';button.setAttribute('aria-label',`Chạy ${s.id} ${s.name}`);button.onclick=()=>runScenario(s.id);row.append(id,name,button);return row;}));
  } catch(error) { $('scenario-list').textContent='Không tải được danh sách kịch bản: '+error.message; }
  setInterval(refresh,750);
}
init();
