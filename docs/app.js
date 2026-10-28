'use strict';

const DATA_PATH = './data/meals.json';
let rows = new Map();
let lastSync = null;
let partial = false;

const $ = id => document.getElementById(id);
function koreaDate() {
  const parts = new Intl.DateTimeFormat('en-US', {timeZone: 'Asia/Seoul', year: 'numeric', month: '2-digit', day: '2-digit'}).formatToParts(new Date());
  const val = name => parts.find(p => p.type === name).value;
  return `${val('year')}-${val('month')}-${val('day')}`;
}
function shiftDate(iso, n) {
  const d = new Date(`${iso}T12:00:00Z`);
  d.setUTCDate(d.getUTCDate() + n);
  return d.toISOString().slice(0,10);
}
function weekday(iso) { const d = new Date(`${iso}T12:00:00Z`); return '일월화수목금토'[d.getUTCDay()]; }
function displayDate(iso) {
  const [year, month, day] = iso.split('-').map(Number);
  return `${year}년 ${month}월 ${day}일 (${weekday(iso)})`;
}
function formatMeal(iso, kind='dinner') {
  const row = rows.get(iso);
  const label = kind === 'dinner' ? '석식' : '중식';
  if (!row) return `📅 ${displayDate(iso)} ${label}\n\n해당 날짜의 급식 데이터가 아직 확인되지 않았습니다.`;
  const menu = row[kind];
  if (!Array.isArray(menu) || menu.length === 0) {
    return `📅 ${displayDate(iso)} ${label}\n\n${label} 데이터가 등록되지 않았습니다.\n(급식 미운영으로 확정된 것은 아닙니다.)`;
  }
  return `🍽️ ${displayDate(iso)} ${label}\n\n` + menu.map(x=>`• ${x}`).join('\n');
}
function render(iso) {
  $('day-title').textContent = displayDate(iso);
  $('meal-date').value = iso;
  const panel = $('meal-panel');
  panel.replaceChildren();
  const label = document.createElement('h3');
  label.textContent = '오늘의 석식 메뉴';
  const row = rows.get(iso);
  const items = row?.dinner;
  if (Array.isArray(items) && items.length) {
    const list = document.createElement('ul');
    items.forEach(item => { const li=document.createElement('li'); li.textContent = item; list.append(li); });
    panel.append(label,list);
  } else {
    const message = document.createElement('p');
    message.className = 'muted';
    message.textContent = row ? '이 날짜의 석식 정보가 아직 등록되지 않았어요. 급식이 없는 날이라고 단정할 수는 없어요.' : '이 날짜는 아직 데이터가 수집되지 않았어요.';
    panel.append(label,message);
  }
  for(const button of document.querySelectorAll('[data-offset]')) {
    button.classList.toggle('active', shiftDate(koreaDate(), Number(button.dataset.offset)) === iso);
  }
}
function resolveCommand(input) {
  const t = input.replace(/\s+/g, '').trim();
  const now = koreaDate();
  if (t === '!석식' || t === '!오늘석식') return formatMeal(now);
  if (t === '!중식' || t === '!오늘중식') return formatMeal(now,'lunch');
  if (t === '!내일석식') return formatMeal(shiftDate(now,1));
  if (t === '!모레석식') return formatMeal(shiftDate(now,2));
  if (t === '!이번주석식') {
    const offset = (new Date(`${now}T12:00:00Z`).getUTCDay()+6)%7;
    const monday = shiftDate(now,-offset);
    return Array.from({length:5}, (_,i)=>formatMeal(shiftDate(monday,i))).join('\n\n──────────\n\n');
  }
  let match=t.match(/^!(\d{4})-(\d{1,2})-(\d{1,2})석식$/);
  if (match) {
    const iso = makeIso(Number(match[1]), Number(match[2]), Number(match[3]));
    return iso ? formatMeal(iso) : '올바른 날짜가 아닙니다.';
  }
  match=t.match(/^!(\d{1,2})월(\d{1,2})일석식$/);
  if (match) {
    const year = Number(now.slice(0,4));
    const iso = makeIso(year,Number(match[1]),Number(match[2]));
    return iso ? formatMeal(iso) : '올바른 날짜가 아닙니다. 연도가 다르면 !2027-01-02석식 형식으로 입력하세요.';
  }
  return '사용 가능한 명령어:\n!석식 / !내일석식 / !모레석식\n!중식 / !이번주석식\n!11월2일석식 / !2026-11-02석식';
}
function makeIso(year, month, day) {
  if(year<2000 || year>2100 || month<1 || month>12 || day<1 || day>31) return null;
  const d = new Date(Date.UTC(year,month-1,day));
  if(d.getUTCFullYear()!==year || d.getUTCMonth()!==month-1 || d.getUTCDate()!==day) return null;
  return d.toISOString().slice(0,10);
}
function connectControls() {
  const now=koreaDate();
  $('meal-date').value = now;
  $('meal-date').addEventListener('change', e => { if (e.target.value) render(e.target.value); });
  document.querySelectorAll('[data-offset]').forEach(button => button.addEventListener('click', () => render(shiftDate(koreaDate(),Number(button.dataset.offset)))));
  const submit=() => { $('chat-result').textContent=resolveCommand($('command').value); };
  $('send').addEventListener('click',submit);
  $('command').addEventListener('keydown',e => { if(e.key==='Enter') submit(); });
  document.querySelectorAll('[data-command]').forEach(button=>button.addEventListener('click',()=>{ $('command').value=button.dataset.command; submit(); }));
  render(now);
}
async function init() {
  connectControls();
  try {
    const res=await fetch(DATA_PATH + '?v=' + Date.now(), {cache:'no-store'});
    if (!res.ok) throw Error('Data HTTP ' + res.status);
    const obj=await res.json();
    if(!Array.isArray(obj.days)) throw Error('Unknown data format');
    rows=new Map(obj.days.filter(x=>/^\d{4}-\d{2}-\d{2}$/.test(x.date)).map(x=>[x.date,x]));
    lastSync=obj.updatedAt;
    partial=!!obj.partial;
    const sync=$('sync');
    if(!lastSync) {
      sync.textContent='아직 자동 수집 전 · GitHub Actions 실행 필요';
      sync.classList.add('warn');
    } else {
      const hours=(Date.now()-Date.parse(lastSync))/3600000;
      const formatted=new Intl.DateTimeFormat('ko-KR',{timeZone:'Asia/Seoul',month:'numeric',day:'numeric',hour:'numeric',minute:'2-digit'}).format(new Date(lastSync));
      sync.textContent=`마지막 데이터 확인: ${formatted} · ${rows.size}일분` + (partial?' · 일부 날짜 누락':'') + (hours>48?' · 오래된 데이터 주의':'');
      if(partial || hours>48) sync.classList.add('warn');
    }
    render($('meal-date').value || koreaDate());
  } catch (err) {
    $('sync').textContent='급식 데이터를 불러오지 못했어요. 배포/네트워크 상태를 확인해 주세요.';
    $('sync').classList.add('warn');
    render(koreaDate());
  }
}
init();
