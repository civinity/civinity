/* UI-only enhancement: reuse existing forms, actions, backend and permissions. */
(()=>{'use strict';
const $=id=>document.getElementById(id);
const dispatch=$('dispatch'),workspace=$('d_workspace');if(!dispatch||!workspace)return;
const auth=$('d_auth');auth.classList.add('d-authbox');
const message=$('d_message');
// Preserve the existing form controls, handlers and IDs by moving DOM nodes (not cloning).
const manage=$('d_manage'),detail=$('d_detail'),month=$('d_month'),users=$('d_useradmin');
const taskTitle=Array.from(workspace.children).find(n=>n.tagName==='H2'&&n.textContent.trim()==='Uzdevumi');
const taskTable=taskTitle?.nextElementSibling;
const profile=workspace.firstElementChild;
const shell=document.createElement('div');shell.className='d-shell';
const menu=document.createElement('aside');menu.className='d-menu';menu.innerHTML='<div class="d-menu-title">DARBA VIDE</div>';
const content=document.createElement('div');content.className='d-content';
shell.append(menu,content);workspace.append(shell);
const views={};
const definitions=[['home','⌂','Pārskats'],['tasks','☷','Uzdevumi'],['new','＋','Jauns uzdevums'],['reports','▤','Mēneša atskaites'],['staff','♙','Darbinieki']];
for(const [key,icon,label] of definitions){const b=document.createElement('button');b.type='button';b.className='d-navbtn';b.dataset.view=key;b.innerHTML=`<span class="d-icon">${icon}</span><span>${label}</span>`;b.onclick=()=>show(key);menu.append(b);const view=document.createElement('section');view.className='d-view';view.dataset.view=key;view.innerHTML=`<div class="d-heading"><div><h2>${label}</h2><p>${({home:'Darba pārskats un ātrās darbības',tasks:'Visi pieejamie darba uzdevumi',new:'Izveidojiet un deleģējiet darbu',objects:'Objektu kartītes un līguma stundas likmes',reports:'Darbu apkopojumi un pieņemšanas–nodošanas akti',staff:'Lietotāju apstiprināšana un lomas'})[key]}</p></div></div>`;content.append(view);views[key]=view;}
const card=(node)=>{const c=document.createElement('div');c.className='d-card';c.append(node);return c;};
const make=(html)=>{const n=document.createElement('div');n.innerHTML=html;return n.firstElementChild};
const welcome=make('<div class="d-welcome"><h2>Darba vadības pārskats</h2><p>Uzdevumi, objekti, darbinieki un PN akti vienuviet.</p></div>');
views.home.append(welcome);
const stats=make('<div class="d-stats"><div class="d-stat"><strong id="d_stat_tasks">—</strong><span>Uzdevumi</span></div><div class="d-stat"><strong id="d_stat_objects">—</strong><span>Objekti</span></div><div class="d-stat"><strong id="d_stat_pending">—</strong><span>Gaida apstiprinājumu</span></div><div class="d-stat"><strong id="d_stat_staff">—</strong><span>Jauni darbinieki</span></div></div>');views.home.append(stats);
const shortcuts=make('<div class="d-card"><h3>Ātrās darbības</h3><div class="d-actions"><button class="btn" type="button" data-jump="new">＋ Izveidot uzdevumu</button><button class="btn alt" type="button" data-jump="tasks">☷ Uzdevumu saraksts</button><button class="btn alt" type="button" data-jump="reports">▤ Mēneša PN akts</button></div></div>');views.home.append(shortcuts);
shortcuts.querySelectorAll('[data-jump]').forEach(b=>b.onclick=()=>show(b.dataset.jump));
if(taskTitle)taskTitle.remove();if(taskTable){taskTable.classList.add('d-table');views.tasks.append(card(taskTable));}
if(detail){detail.classList.add('d-card');views.tasks.append(detail);}
if(manage){
 const headings=Array.from(manage.children).filter(n=>n.tagName==='H2');
 const split=headings[1];
 if(split){const newBlock=document.createElement('div'),objBlock=document.createElement('div');newBlock.className='d-section';objBlock.className='d-section';let toObj=false;for(const node of Array.from(manage.childNodes)){if(node===split)toObj=true;(toObj?objBlock:newBlock).append(node)}views.new.append(card(newBlock));objBlock.style.display='none';workspace.append(objBlock);}
 // Retain the permission-controlled ID as a harmless placeholder; actual forms are in the views.
 manage.style.display='none';workspace.append(manage);

}
if(month){month.classList.add('d-section');views.reports.append(card(month));}
if(users){users.classList.add('d-section');views.staff.append(card(users));}
if(profile){profile.classList.add('d-profile');menu.prepend(profile);}
let current='home';
function show(key){if(!views[key])return;current=key;Object.entries(views).forEach(([k,v])=>v.classList.toggle('active',k===key));document.querySelectorAll('#civi-dispatch-nav .d-navbtn, .d-menu .d-navbtn').forEach(b=>b.classList.toggle('active',b.dataset.view===key));refreshVisibility();}
function refreshVisibility(){const isAdmin=$('d_who')?.textContent.includes('administrators');const isManager=['administrators','vaditajs','parvaldnieks'].some(x=>$('d_who')?.textContent.includes(x));for(const key of ['new','reports']){const b=document.querySelector(`#civi-dispatch-nav [data-view="${key}"], .d-menu [data-view="${key}"]`);if(b)b.style.display=isManager?'':'none';}const staff=document.querySelector('#civi-dispatch-nav [data-view="staff"], .d-menu [data-view="staff"]');if(staff)staff.style.display=isAdmin?'':'none';if(!isManager&&['new','reports'].includes(current))show('tasks');if(!isAdmin&&current==='staff')show('tasks');}
function updateStats(){const rows=$('d_taskrows')?.querySelectorAll('tr')||[];const taskCount=Array.from(rows).filter(r=>r.querySelector('button')).length;const objCount=$('d_obj')?.options.length||0;const pending=$('d_pending')?.querySelectorAll('button').length||0;const pendingTask=Array.from(rows).filter(r=>r.textContent.includes('gaida_apstiprinajumu')).length;$('d_stat_tasks').textContent=taskCount;$('d_stat_objects').textContent=objCount;$('d_stat_pending').textContent=pendingTask;$('d_stat_staff').textContent=pending;refreshVisibility();}
const observer=new MutationObserver(()=>{if(!workspace.classList.contains('hidden'))updateStats()});observer.observe($('d_taskrows'),{childList:true});observer.observe($('d_pending'),{childList:true});observer.observe(workspace,{attributes:true,attributeFilter:['class']});
const originalOpen=window.dispatchOpen;if(typeof originalOpen==='function')window.dispatchOpen=async function(id){show('tasks');await originalOpen(id);$('d_detail')?.scrollIntoView({behavior:'smooth',block:'start'});};
window.civiDispatchShow=show;
// Avoid ID collision: container d_month vs month input d_month_number.
show('home');
})();
