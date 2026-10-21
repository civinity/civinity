/* V7.0: deterministic sidebar/navigation repair; runs after all legacy modules. */
(()=>{'use strict';
function init(){
 const $=id=>document.getElementById(id),nav=$('nav'),brand=document.querySelector('aside .brand'),dispatch=$('dispatch');
 if(!nav||!brand||!dispatch)return;
 // Preserve the ORIGINAL selector and its event listeners; put it directly below the brand.
 const select=$('company'),label=document.querySelector('label[for="company"]');
 if(select){let host=$('v70-company');if(!host){host=document.createElement('div');host.id='v70-company';brand.insertAdjacentElement('afterend',host)}if(label)host.appendChild(label);host.appendChild(select);}
 // Rebuild the two accordion menus as a single source of truth.
 const oldTasks=nav.querySelector('[data-page="dispatch"]');
 if(!oldTasks)return;
 const taskParent=oldTasks.cloneNode(false);taskParent.className='nav v70-parent';taskParent.type='button';taskParent.dataset.page='dispatch';taskParent.innerHTML='<span class="nav-icon">☷</span><span>Uzdevumi</span><span class="v70-arrow">⌄</span>';
 oldTasks.replaceWith(taskParent);
 let taskSub=$('civi-dispatch-nav');if(!taskSub){taskSub=document.createElement('div');taskSub.id='civi-dispatch-nav'}
 taskSub.className='v70-submenu';taskSub.hidden=true;taskParent.after(taskSub);taskSub.replaceChildren();
 const stats=$('v67-ticket-statistics'),register=$('v68-ticket-register');
 function hideExtras(){if(stats){stats.classList.add('hidden');stats.style.display='none'}if(register){register.classList.add('hidden');register.style.display='none'}}
 function navigate(mode){window.page('dispatch');hideExtras();
  if(mode==='list'){dispatch.querySelectorAll('.d-view').forEach(v=>v.classList.remove('hidden'));window.civiDispatchShow?.('tasks');if(register){register.classList.remove('hidden');register.style.display='block'}$('v68-ticket-reload')?.click();}
  if(mode==='new'){dispatch.querySelectorAll('.d-view').forEach(v=>v.classList.remove('hidden'));window.civiDispatchShow?.('new');const view=dispatch.querySelector('.d-view[data-view="new"]');if(view){dispatch.querySelectorAll('.d-view').forEach(v=>v.classList.toggle('active',v===view));view.classList.remove('hidden');}const form=$('civi-create-panel');if(form)form.style.display='block';}
  if(mode==='stats'){window.civiDispatchShow?.('tasks');dispatch.querySelectorAll('.d-view').forEach(v=>{v.classList.remove('active');v.classList.add('hidden')});if(stats){stats.classList.remove('hidden');stats.style.display='block'}$('v67-refresh')?.click();}
  [...taskSub.children].forEach(b=>b.classList.toggle('v70-current',b.dataset.mode===mode));
 }
 for(const [mode,title] of [['list','Saraksts'],['new','Jauns uzdevums'],['stats','Statistika']]){const b=document.createElement('button');b.type='button';b.dataset.mode=mode;b.textContent=title;b.addEventListener('click',e=>{e.stopPropagation();navigate(mode)});taskSub.append(b)}
 taskParent.setAttribute('aria-expanded','false');taskParent.addEventListener('click',e=>{e.preventDefault();const opening=taskSub.hidden;taskSub.hidden=!opening;taskParent.setAttribute('aria-expanded',String(opening));if(opening)navigate('list')});
 // Separate company-management accordion; company selector above is not a substitute for this section.
 let companies=nav.querySelector('[data-page="companies"]');
 if(!companies){companies=document.createElement('button');companies.className='nav';companies.dataset.page='companies';taskSub.after(companies)}
 const companyParent=companies.cloneNode(false);companyParent.className='nav v70-parent';companyParent.type='button';companyParent.dataset.page='companies';companyParent.innerHTML='<span class="nav-icon">▣</span><span>Uzņēmumi</span><span class="v70-arrow">⌄</span>';companies.replaceWith(companyParent);
 let companySub=$('v69-company-sub');if(!companySub){companySub=document.createElement('div');companySub.id='v69-company-sub'}companySub.className='v70-submenu';companySub.hidden=true;companyParent.after(companySub);companySub.replaceChildren();
 for(const [title,buttonId] of [['Jaunie uzņēmumi','v68-company-list'],['Statistika','v68-company-stats']]){const b=document.createElement('button');b.type='button';b.textContent=title;b.onclick=e=>{e.stopPropagation();window.page('companies');$(buttonId)?.click()};companySub.append(b)}
 companyParent.setAttribute('aria-expanded','false');companyParent.addEventListener('click',e=>{e.preventDefault();const opening=companySub.hidden;companySub.hidden=!opening;companyParent.setAttribute('aria-expanded',String(opening));if(opening){window.page('companies');$('v68-company-list')?.click()}});
 // Ensure older scripts cannot reintroduce their old sidebar links.
 const duplicate=$('v69-company-host');if(duplicate&&duplicate!==$('v70-company'))duplicate.remove();
 }
 if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',init,{once:true});else init();
})();
