/* V6.9: stable sidebar accordions and functional task routes. */
(()=>{'use strict';
const $=id=>document.getElementById(id), nav=$('nav'), sub=$('civi-dispatch-nav');
if(!nav||!sub)return;
const dispatch=nav.querySelector('[data-page="dispatch"]');
const companySelect=$('company'),companyLabel=document.querySelector('label[for="company"]');
// One company selector, below the logo. Never duplicate or discard the real select element.
if(companySelect){let host=$('v69-company-host');if(!host){host=document.createElement('div');host.id='v69-company-host';(document.querySelector('aside .brand')||nav).after(host)}if(companyLabel)host.append(companyLabel);host.append(companySelect)}
// The company management module is a collapsible group, not a standalone top-level route.
const companies=nav.querySelector('[data-page="companies"]');
if(companies){const group=$('v69-company-sub')||document.createElement('div');group.id='v69-company-sub';group.className='v69-sidebar-sub';group.hidden=true;companies.after(group);group.replaceChildren();
 const openCompany=(kind)=>{window.page('companies');if(kind==='stats')$('v68-company-stats')?.click();else $('v68-company-list')?.click()};
 for(const [title,kind] of [['Jaunie uzņēmumi','new'],['Statistika','stats']]){const b=document.createElement('button');b.type='button';b.textContent=title;b.addEventListener('click',e=>{e.stopPropagation();openCompany(kind)});group.append(b)}
 companies.replaceWith(companies.cloneNode(true));const newParent=nav.querySelector('[data-page="companies"]');newParent.append(document.createElement('span'));newParent.lastElementChild.className='v69-chevron';newParent.lastElementChild.textContent='⌄';newParent.setAttribute('aria-expanded','false');newParent.addEventListener('click',e=>{e.preventDefault();const expanded=group.hidden;group.hidden=!expanded;newParent.setAttribute('aria-expanded',String(expanded));if(expanded)openCompany('new')});}
// Replace prior conflicting click handlers on the task parent, but keep its location and appearance.
if(dispatch){const fresh=dispatch.cloneNode(true);dispatch.replaceWith(fresh);fresh.setAttribute('aria-expanded','false');sub.classList.remove('v65-expanded');sub.style.display='none';fresh.addEventListener('click',e=>{e.preventDefault();const expanded=fresh.getAttribute('aria-expanded')!=='true';fresh.setAttribute('aria-expanded',String(expanded));sub.classList.toggle('v65-expanded',expanded);sub.style.display=expanded?'flex':'none';if(expanded)activate('list')})}
sub.replaceChildren();
function base(){window.page('dispatch');$('v67-ticket-statistics')?.classList.add('hidden');$('v68-ticket-register')?.classList.add('hidden')}
function activate(mode){base();if(mode==='list'){window.civiDispatchShow?.('tasks');$('v68-ticket-register')?.classList.remove('hidden');$('v68-ticket-reload')?.click()}else if(mode==='new'){window.civiDispatchShow?.('new');const form=$('civi-create-modal');if(form)form.classList.remove('hidden');}else if(mode==='stats'){window.civiDispatchShow?.('tasks');document.querySelectorAll('#dispatch .d-view').forEach(e=>e.classList.remove('active'));$('v67-ticket-statistics')?.classList.remove('hidden');$('v67-refresh')?.click()}
 sub.querySelectorAll('button').forEach(b=>b.classList.toggle('v69-selected',b.dataset.action===mode));}
for(const [title,action] of [['Saraksts','list'],['Jauns uzdevums','new'],['Statistika','stats']]){const b=document.createElement('button');b.type='button';b.className='civi-subnav-button v69-task-link';b.dataset.action=action;b.textContent=title;b.addEventListener('click',e=>{e.preventDefault();e.stopPropagation();activate(action)});sub.append(b)}
// The older internal dispatcher menu must not present duplicated controls.
const internal=document.querySelector('#d_workspace .d-menu');if(internal)internal.style.display='none';
})();
