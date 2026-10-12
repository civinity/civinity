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
dispatchLink.insertAdjacentElement('afterend',strip);
// The statistics above the task list use the same existing server-fed task table.
const taskView=document.querySelector('#dispatch .d-view[data-view="tasks"]');
const taskStats=document.createElement('div');taskStats.id='civi-task-summary';
taskStats.innerHTML='<div class="civi-summary-item"><strong id="civi-top-new">—</strong><span>Jauni uzdevumi</span></div><div class="civi-summary-item"><strong id="civi-top-done">—</strong><span>Pabeigti</span></div><div class="civi-summary-item"><strong id="civi-top-open">—</strong><span>Neizpildīti</span></div><div class="civi-summary-item"><strong id="civi-top-progress">—</strong><span>Procesā</span></div>';
if(taskView){const heading=taskView.querySelector('.d-heading');if(heading)heading.remove();taskView.prepend(taskStats);
const add=document.createElement('button');add.className='btn civi-task-create';add.textContent='＋ Jauns uzdevums';add.type='button';add.onclick=()=>document.querySelector('#civi-dispatch-nav [data-view="new"]')?.click();taskStats.insertAdjacentElement('afterend',add);}
// Remove duplicate title/exit row left behind by the old dispatcher markup.
const who=$('d_who');if(who?.parentElement)who.parentElement.remove();
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
