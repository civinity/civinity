/* CIVINITY V6.6: consolidated reports, clean navigation and object actions. */
(()=>{'use strict';
const $=id=>document.getElementById(id),nav=$('nav');if(!nav)return;
// Reports are the sole location of all document generators. The existing generators remain mounted.
const docNav=nav.querySelector('[data-page="documents"]');docNav?.remove();
const reportNav=nav.querySelector('[data-page="reports"]');
const reportSub=document.createElement('div');reportSub.id='v66-report-menu';reportSub.className='v66-submenu';reportNav?.after(reportSub);
const categories=[
 ['inspection','Apsekošanas akti'],['defect','Defektu akti'],['pn','PN akti'],['monthly','Mēneša atskaites'],
 ['quote','Cenu piedāvājumi'],['invoice','Rēķini'],['technical','Tehniskie atzinumi'],['archive','Dokumentu arhīvs']
];
const reportSection=$('reports'),oldDocs=$('documents'),generator=$('civi-reports-v60');
if(reportSection){
 const head=reportSection.querySelector('.section-hero h2');if(head)head.textContent='Atskaites · Dokumentu centrs';
 const intro=reportSection.querySelector('.section-hero p');if(intro)intro.textContent='Visi akti, atskaites, piedāvājumi un rēķini vienuviet.';
 const dashboard=document.createElement('section');dashboard.id='v66-doc-dashboard';dashboard.className='v66-doc-dashboard';
 dashboard.innerHTML='<div class="v66-report-heading"><div><span>CIVINITY · DOKUMENTI</span><h2 id="v66-category-title">PN akti</h2><p id="v66-category-info">Izvēlieties dokumenta veidu kreisajā izvēlnē.</p></div></div><div id="v66-category-content" class="v66-category-content"></div>';
 reportSection.querySelector('.section-hero')?.after(dashboard);
 const content=$('v66-category-content');
 if(generator){generator.classList.remove('hidden');generator.classList.add('v66-existing-generator');content.append(generator)}
 if(oldDocs){const panel=oldDocs.querySelector('.panel');if(panel){panel.id='v66-archive-panel';panel.classList.add('hidden');dashboard.after(panel)}}
 const oldReportPanel=reportSection.querySelector(':scope > .panel');if(oldReportPanel)oldReportPanel.classList.add('v66-legacy-panel');
 const preview=document.createElement('div');preview.id='v66-category-placeholder';preview.className='v66-category-placeholder hidden';content.append(preview);
 function selectCategory(key){
  window.page?.('reports');
  reportSub.querySelectorAll('button').forEach(b=>b.classList.toggle('v66-current',b.dataset.category===key));
  const title=categories.find(x=>x[0]===key)?.[1]||'Atskaites';$('v66-category-title').textContent=title;
  const isGenerator=['pn','monthly','invoice'].includes(key);
  generator?.classList.toggle('hidden',!isGenerator);
  $('v66-archive-panel')?.classList.toggle('hidden',key!=='archive');
  preview.classList.toggle('hidden',isGenerator||key==='archive');
  if(key==='pn'||key==='monthly')generator?.querySelector('[data-tab="pn"]')?.click();
  if(key==='invoice')generator?.querySelector('[data-tab="invoice"]')?.click();
  if(!isGenerator&&key!=='archive'){
   preview.replaceChildren();
   const p=document.createElement('p');p.textContent='Šī dokumenta veida sagatavošanai izmantojiet esošos objekta un apsekošanas datus. Atsevišķs automātiskais ģenerators vēl nav pieslēgts.';preview.append(p);
   const btn=document.createElement('button');btn.type='button';btn.className='btn alt';btn.textContent='Atvērt esošos dokumentus';btn.onclick=()=>selectCategory('archive');preview.append(btn);
  }
  $('v66-category-info').textContent=key==='archive'?'Saglabātie dokumenti un esošais arhīvs.':isGenerator?'Priekšskatījums un pieejamie eksporta formāti.':'Dokumentu veids ir pievienots vienotajai izvēlnei.';
 }
 categories.forEach(([key,label])=>{const b=document.createElement('button');b.type='button';b.dataset.category=key;b.textContent=label;b.addEventListener('click',()=>selectCategory(key));reportSub.append(b)});
 let expanded=false;reportNav?.setAttribute('aria-expanded','false');reportNav?.insertAdjacentHTML('beforeend','<span class="v66-chevron" aria-hidden="true">⌄</span>');
 reportNav?.addEventListener('click',()=>{expanded=!expanded;reportSub.classList.toggle('v66-open',expanded);reportNav.setAttribute('aria-expanded',String(expanded));},false);
 selectCategory('pn');window.page?.('overview');
}
// No duplicate document tab in technical management.
for(const b of document.querySelectorAll('#v65-technical-menu button'))if(/Dokumenti/i.test(b.textContent))b.remove();
// One pair of actions inside the blue object banner; remove duplicates below.
const objects=$('objects');if(objects){
 objects.querySelectorAll('.v65-object-actions').forEach(x=>x.remove());
 const hero=objects.querySelector('.section-hero-copy');
 if(hero){let add=hero.querySelector('button[onclick*="newObject"]');if(add){add.textContent='＋ Jauns objekts';add.classList.add('v66-object-new')}
 const contract=document.createElement('button');contract.type='button';contract.className='btn v66-contract-new';contract.textContent='＋ Jauns līgums';
 contract.onclick=()=>{window.page?.('objects');const panel=$('v65-contract-panel');panel?.classList.remove('hidden');panel?.scrollIntoView({behavior:'smooth',block:'start'})};hero.append(contract)}
 objects.querySelectorAll('.panel > button[onclick*="newObject"]').forEach(b=>b.remove());
}
// Keep header consistently first in main on all page changes.
const topbar=document.querySelector('main > .topbar');if(topbar){topbar.parentElement.prepend(topbar)}
})();