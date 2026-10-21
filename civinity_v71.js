/* V7.1: single final controller; no duplicate menu handlers. */
(()=>{'use strict';
const $=id=>document.getElementById(id);
function init(){
 const nav=$('nav'),brand=document.querySelector('aside .brand'),dispatch=$('dispatch');
 if(!nav||!brand||!dispatch)return;
 // Keep the original select (including its original onchange handler).
 const select=$('company'),label=document.querySelector('label[for="company"]');
 if(select){let host=$('v71-company');if(!host){host=document.createElement('div');host.id='v71-company';brand.after(host)}if(label)host.append(label);host.append(select)}
 // The v68 controller creates the company page. Its original button is replaced to prevent competing handlers.
 let companies=nav.querySelector('[data-page="companies"]');
 if(!companies){companies=document.createElement('button');companies.className='nav';companies.dataset.page='companies';nav.querySelector('[data-page="objects"]')?.before(companies)}
 const makeParent=(old,title,icon)=>{const fresh=document.createElement('button');fresh.type='button';fresh.className='nav v71-parent';fresh.dataset.page=old.dataset.page;fresh.innerHTML=`<span class="nav-icon">${icon}</span><span>${title}</span><span class="v71-chevron">⌄</span>`;old.replaceWith(fresh);return fresh};
 const taskParent=makeParent(nav.querySelector('[data-page="dispatch"]'),'Uzdevumi','☷');
 const companyParent=makeParent(companies,'Uzņēmumi','▣');
 let taskMenu=$('civi-dispatch-nav');if(!taskMenu){taskMenu=document.createElement('div');taskMenu.id='civi-dispatch-nav'}taskParent.after(taskMenu);taskMenu.replaceChildren();taskMenu.className='v71-menu';taskMenu.hidden=true;taskMenu.classList.remove('v65-expanded');
 let companyMenu=$('v69-company-sub');if(!companyMenu){companyMenu=document.createElement('div');companyMenu.id='v69-company-sub'}companyParent.after(companyMenu);companyMenu.replaceChildren();companyMenu.className='v71-menu';companyMenu.hidden=true;
 const stat=$('v67-ticket-statistics'),register=$('v68-ticket-register');
 function conceal(){for(const x of [stat,register])if(x){x.classList.add('hidden');x.style.display='none'}}
 function show(mode){window.page('dispatch');conceal();
  if(mode==='list'){window.civiDispatchShow?.('tasks');if(register){register.classList.remove('hidden');register.style.display='block';$('v68-ticket-reload')?.click()}}
  else if(mode==='new'){window.civiDispatchShow?.('new');const v=dispatch.querySelector('.d-view[data-view="new"]');if(v){v.classList.add('active');v.classList.remove('hidden')}const form=$('civi-create-panel');if(form){form.style.display='block';form.classList.remove('hidden')}}
  else if(mode==='stats'){window.civiDispatchShow?.('tasks');dispatch.querySelectorAll('.d-view').forEach(v=>v.classList.remove('active'));if(stat){stat.classList.remove('hidden');stat.style.display='block';$('v67-refresh')?.click()}}
  taskMenu.querySelectorAll('button').forEach(b=>b.classList.toggle('v71-selected',b.dataset.mode===mode));
 }
 for(const [mode,name] of [['list','Saraksts'],['new','Jauns uzdevums'],['stats','Statistika']]){const b=document.createElement('button');b.type='button';b.dataset.mode=mode;b.textContent=name;b.addEventListener('click',e=>{e.preventDefault();e.stopPropagation();show(mode)});taskMenu.append(b)}
 function toggle(button,menu){const expanded=menu.hidden;menu.hidden=!expanded;button.setAttribute('aria-expanded',String(expanded));}
 taskParent.setAttribute('aria-expanded','false');taskParent.addEventListener('click',e=>{e.preventDefault();toggle(taskParent,taskMenu);if(!taskMenu.hidden)show('list')});
 const companyPage=$('companies');function showCompany(kind){window.page('companies');$(kind==='stats'?'v68-company-stats':'v68-company-list')?.click();companyMenu.querySelectorAll('button').forEach(b=>b.classList.toggle('v71-selected',b.dataset.kind===kind))}
 for(const [kind,name] of [['list','Jaunie uzņēmumi'],['stats','Statistika']]){const b=document.createElement('button');b.type='button';b.dataset.kind=kind;b.textContent=name;b.addEventListener('click',e=>{e.preventDefault();e.stopPropagation();showCompany(kind)});companyMenu.append(b)}
 companyParent.setAttribute('aria-expanded','false');companyParent.addEventListener('click',e=>{e.preventDefault();toggle(companyParent,companyMenu);if(!companyMenu.hidden)showCompany('list')});
 // Existing inline page() sets visibility. Restore it on section change without losing company wrapper.
 const originalPage=window.page;window.page=function(name){if(name!=='dispatch')conceal();return originalPage(name)};
 // Guard against accidental repeated bootstrap and ensure the original selectors remain unique.
 window.CIVINITY_V71_READY=true;
 }
 if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',init,{once:true});else init();
})();
