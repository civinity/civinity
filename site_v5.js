/* CIVINITY AI V5 — full-width task workspace and clean navigation. */
(()=>{'use strict';
const $=id=>document.getElementById(id),dispatch=$('dispatch'),workspace=$('d_workspace');if(!dispatch||!workspace)return;
// The original page() remains responsible for visibility and all old features.
const oldPage=window.page;
window.page=function(name){
 if(name==='prices')name='overview';
 const result=oldPage(name);
 document.body.classList.toggle('civi-tasks-mode',name==='dispatch');
 if(name==='dispatch'){
   window.civiUpdateTaskMetrics?.();
   const btn=document.querySelector('#civi-dispatch-nav [data-view="tasks"]');if(btn)btn.click();
 }
 return result;
};
// Keep the CIVINITY left sidebar and move the existing dispatcher controls into it.
// Moving the original buttons preserves their handlers and role restrictions.
const menu=dispatch.querySelector('.d-menu');
const mainNav=$('nav');
if(menu&&mainNav){
 const group=document.createElement('div');group.id='civi-dispatch-nav';
 group.innerHTML='';
 const buttons=[...menu.querySelectorAll('button[data-view]')];
 for(const b of buttons){
   if(b.dataset.view==='home'){b.remove();continue;}
   b.classList.add('civi-subnav-button');group.append(b);
 }
 const dispatchLink=mainNav.querySelector('[data-page="dispatch"]');
 dispatchLink?.insertAdjacentElement('afterend',group);
 menu.hidden=true;
 const objLink=menu.querySelector('button:not([data-view])');
 if(objLink){objLink.classList.add('civi-subnav-button');group.append(objLink);}
}
// Keep dispatcher navigation in the main blue sidebar and expose reporting tools.
const subnav=document.getElementById('civi-dispatch-nav');
if(subnav){
 const makeLink=(label,action)=>{const b=document.createElement('button');b.type='button';b.className='civi-subnav-button';b.textContent=label;b.addEventListener('click',action);subnav.append(b);return b;};
 const taskButton=subnav.querySelector('[data-view="tasks"]');
 const homeButton=makeLink('▥ Statistika',()=>{document.querySelector('#dispatch .d-menu [data-view="home"]')?.click();});
 // Original overview button is removed by V5, so select its view through a preserved UI action.
 homeButton.onclick=()=>{const view=document.querySelector('#dispatch .d-view[data-view="home"]');if(!view)return;document.querySelectorAll('#dispatch .d-view').forEach(v=>v.classList.toggle('active',v===view));subnav.querySelectorAll('[data-view]').forEach(b=>b.classList.remove('active'));};
 const reports=subnav.querySelector('[data-view="reports"]');if(reports)reports.innerHTML='<span class="d-icon">▤</span><span>PN akti un atskaites</span>';
 makeLink('€ Rēķinu dokumenti',()=>window.page('documents'));
}
// Employee approvals belong to the main administrator area, not the task submenu.
// Reuse the existing staff view and its server-side administrator permissions.
(()=>{
 const nav=document.getElementById('nav');
 const subnav=document.getElementById('civi-dispatch-nav');
 const staff=subnav?.querySelector('[data-view="staff"]');
 if(!nav||!staff)return;
 staff.remove();
 const admin=document.createElement('button');
 admin.type='button';admin.id='civi-admin-users';admin.className='nav-item';
 admin.textContent='⚙ Administrēšana';
 admin.title='Lietotāju apstiprināšana un tiesību piešķiršana';
 admin.addEventListener('click',()=>{
   window.page('dispatch');
   staff.click();
 });
 nav.append(admin);
 // The existing dispatcher refreshVisibility() sets the staff button display
 // according to the authenticated role. Mirror that state for the main menu.
 const update=()=>{
   const who=document.getElementById('d_who');
   const isAdmin=!!who?.textContent.includes('administrators');
   admin.style.display=isAdmin?'':'none';
 };
 new MutationObserver(update).observe(document.getElementById('d_who'),{childList:true,subtree:true,characterData:true});
 update();
})();
// Remove the duplicate dispatcher profile/logout row; global profile remains top right.
const who=$('d_who');
if(who){const row=who.parentElement;if(row)row.style.display='none';}
// No separate task header or horizontal tabs; global sidebar is always visible.
// Move profile icon only visually using CSS; it keeps its original click handler.
// Show task list first, not the dashboard, even on subsequent visits.
const originalInit=window.dispatchInit;
if(typeof originalInit==='function')window.dispatchInit=async function(...args){const r=await originalInit(...args);if(document.body.classList.contains('civi-tasks-mode'))document.querySelector('#civi-dispatch-nav [data-view="tasks"]')?.click();return r};
// Profile button must stay in top right on every page.
const profile=$('profileShortcut');if(profile){profile.setAttribute('title','Mans profils');const toolbar=document.querySelector('.topbar .toolbar');if(toolbar)toolbar.prepend(profile);}
// Keep old page hidden if browser enters via direct navigation.
if(!dispatch.classList.contains('hidden'))document.body.classList.add('civi-tasks-mode');
})();

(()=>{const email=document.getElementById('d_email'),pass=document.getElementById('d_password'),name=document.getElementById('d_name');if(email)email.placeholder='E-pasts / lietotājvārds';if(pass)pass.placeholder='Parole';if(name)name.placeholder='Vārds un uzvārds';})();

/* V5.2: task status summary, permanent navigation and no duplicate headers. */
(()=>{'use strict';
const $=id=>document.getElementById(id);
const nav=$('nav'),dispatchLink=nav?.querySelector('[data-page="dispatch"]');
if(!nav||!dispatchLink)return;
// Summary is shown beside the main Uzdevumi entry, including on the home page.
const strip=document.createElement('div');strip.id='civi-task-counts';strip.setAttribute('aria-label','Uzdevumu statusi');
strip.innerHTML='<span title="Jauni uzdevumi"><b id="civi-count-new">—</b> Jauni</span><span title="Pabeigti uzdevumi"><b id="civi-count-done">—</b> Pabeigti</span><span title="Neizpildīti uzdevumi"><b id="civi-count-open">—</b> Neizpildīti</span><span title="Darbi procesā"><b id="civi-count-progress">—</b> Procesā</span>';
// Sidebar status badges removed at user's request; summary stays above task list.

// The statistics above the task list use the same existing server-fed task table.
const taskView=document.querySelector('#dispatch .d-view[data-view="tasks"]');
const taskStats=document.createElement('div');taskStats.id='civi-task-summary';
taskStats.innerHTML='<div class="civi-summary-item"><strong id="civi-top-new">—</strong><span>Jauni uzdevumi</span></div><div class="civi-summary-item"><strong id="civi-top-done">—</strong><span>Pabeigti</span></div><div class="civi-summary-item"><strong id="civi-top-open">—</strong><span>Neizpildīti</span></div><div class="civi-summary-item"><strong id="civi-top-progress">—</strong><span>Procesā</span></div>';
if(taskView){const heading=taskView.querySelector('.d-heading');if(heading)heading.remove();taskView.prepend(taskStats);
const add=document.createElement('button');add.className='btn civi-task-create';add.textContent='＋ Jauns uzdevums';add.type='button';add.onclick=()=>{const button=document.querySelector('#civi-dispatch-nav [data-view="new"]');if(button && getComputedStyle(button).display!=='none'){button.click();}else{const msg=document.getElementById('d_message');if(msg)msg.textContent='Jauna uzdevuma izveidei nepieciešamas vadītāja vai pārvaldnieka tiesības.';}};taskStats.insertAdjacentElement('afterend',add);}
// Remove duplicate title/exit row left behind by the old dispatcher markup.
const who=$('d_who');if(who?.parentElement)who.parentElement.style.display='none'; // retain d_who for permission checks
const names=['new','done','open','progress'];
function update(){const rows=[...document.querySelectorAll('#d_taskrows tr')].filter(r=>r.querySelector('button'));if(!rows.length){return;}
 const counts={new:0,done:0,open:0,progress:0};
 for(const r of rows){const cells=r.querySelectorAll('td');const status=(cells[3]?.textContent||'').trim().toLowerCase();
 if(/apstiprin|pabeigt|izpildīt/.test(status))counts.done++;
 else if(/proces|darbā|pauz/.test(status))counts.progress++;
 else if(/nodot|jaun|piešķirt/.test(status))counts.new++;
 else counts.open++;
 }
 for(const k of names){const v=String(counts[k]);const a=$('civi-count-'+k),b=$('civi-top-'+k);if(a)a.textContent=v;if(b)b.textContent=v;}
}
window.civiUpdateTaskMetrics=update;
const rows=$('d_taskrows');if(rows)new MutationObserver(update).observe(rows,{childList:true,subtree:true});update();
})();


/* V5.5 — Invoice generator, restricted to administrators/vaditajs. */
(()=>{'use strict';
const API='https://civinity-ai-api.onrender.com/api/dispatch';
const nav=document.getElementById('nav');if(!nav)return;
const button=document.createElement('button');button.type='button';button.className='nav-item';button.id='civi-invoice-link';button.textContent='€ Rēķinu ģenerators';button.style.display='none';
const panel=document.createElement('section');panel.id='civi-invoice-panel';panel.className='hidden';panel.innerHTML='<div class="civi-invoice-card"><h2>Rēķinu ģenerators</h2><p>Izvēlieties pieņemšanas–nodošanas aktu, lai sagatavotu rēķina projektu PDF formātā.</p><label for="civi-invoice-pn">PN akts</label><select id="civi-invoice-pn"><option>Notiek ielāde…</option></select><div class="civi-invoice-actions"><button type="button" id="civi-invoice-create">Sagatavot rēķinu (PDF)</button><button type="button" id="civi-invoice-back">Atpakaļ</button></div><p id="civi-invoice-message" role="status"></p></div>';
const main=document.querySelector('main');main?.append(panel);nav.append(button);
const status=panel.querySelector('#civi-invoice-message'),select=panel.querySelector('#civi-invoice-pn');
async function req(path){const token=sessionStorage.getItem('dispatch_token');if(!token)throw Error('Nepieciešama autorizācija');const r=await fetch(API+path,{headers:{Authorization:'Bearer '+token}});if(!r.ok){const j=await r.json().catch(()=>({}));throw Error(j.error||'HTTP '+r.status)}return r;}
async function show(){
 try{const me=await (await req('/me')).json();if(!['administrators','vaditajs'].includes(me.role))throw Error('Nepietiek tiesību');
 document.querySelectorAll('main > section').forEach(el=>{if(el!==panel)el.classList.add('hidden')});panel.classList.remove('hidden');status.textContent='';
 const acts=await (await req('/pn')).json();select.replaceChildren();for(const a of acts){const o=document.createElement('option');o.value=a.id;o.textContent=a.number+' — '+a.object+' ('+a.status+')';select.append(o)}if(!acts.length)status.textContent='Nav PN aktu. Vispirms sagatavojiet PN aktu sadaļā Uzdevumi.';
 }catch(e){status.textContent=e.message;}
}
button.onclick=show;
panel.querySelector('#civi-invoice-back').onclick=()=>{panel.classList.add('hidden');window.page('overview')};
panel.querySelector('#civi-invoice-create').onclick=async()=>{try{if(!select.value)throw Error('Izvēlieties PN aktu');status.textContent='Tiek gatavots PDF…';const blob=await (await req('/invoices/'+encodeURIComponent(select.value)+'/pdf')).blob();const u=URL.createObjectURL(blob);const a=document.createElement('a');a.href=u;a.download='REKINS_PROJEKTS_PN_'+select.value+'.pdf';document.body.append(a);a.click();a.remove();setTimeout(()=>URL.revokeObjectURL(u),15000);status.textContent='Rēķina projekts sagatavots.';}catch(e){status.textContent=e.message}};
const oldPage=window.page;window.page=function(name){panel.classList.add('hidden');return oldPage(name)};
async function update(){try{const token=sessionStorage.getItem('dispatch_token');if(!token){button.style.display='none';return}const r=await req('/me');const me=await r.json();button.style.display=['administrators','vaditajs'].includes(me.role)?'':'none';}catch{button.style.display='none'}}
window.addEventListener('storage',update);setInterval(update,12000);setTimeout(update,1200);
})();
