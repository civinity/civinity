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
 group.innerHTML='<div class="civi-subnav-label">DARBA VIDE</div>';
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
const profile=$('profileShortcut');if(profile){profile.setAttribute('title','Mans profils');document.body.append(profile);}
// Keep old page hidden if browser enters via direct navigation.
if(!dispatch.classList.contains('hidden'))document.body.classList.add('civi-tasks-mode');
})();

(()=>{const email=document.getElementById('d_email'),pass=document.getElementById('d_password'),name=document.getElementById('d_name');if(email)email.placeholder='E-pasts / lietotājvārds';if(pass)pass.placeholder='Parole';if(name)name.placeholder='Vārds un uzvārds';})();
