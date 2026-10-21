/* V6.9: stable dispatcher navigation after inline-script repair. */
(()=>{'use strict';
const $=id=>document.getElementById(id),nav=$('nav'),parent=nav?.querySelector('[data-page="dispatch"]'),sub=$('civi-dispatch-nav');
if(!nav||!parent||!sub)return;
// Old versions registered overlapping listeners. Capture navigation and keep one authoritative path.
sub.replaceChildren();
const entries=[['list','Saraksts'],['new','Jauns uzdevums'],['stats','Statistika']];
let current='list',expanded=false;
function show(kind){current=kind;window.page('dispatch');
const register=$('v68-ticket-register'),stats=$('v67-ticket-statistics'),workspace=$('d_workspace'),auth=$('d_auth');
if(register)register.classList.toggle('hidden',kind!=='list');
if(stats)stats.classList.toggle('hidden',kind!=='stats');
if(workspace)workspace.classList.toggle('v69-list-mode',kind==='list');
if(workspace)workspace.classList.toggle('v69-new-mode',kind==='new');
if(workspace)workspace.classList.toggle('v69-stats-mode',kind==='stats');
if(kind==='new' && typeof window.civiDispatchShow==='function')window.civiDispatchShow('new');
if(kind==='list')$('v68-ticket-reload')?.click();
if(kind==='stats')$('v67-refresh')?.click();
sub.querySelectorAll('button').forEach(b=>b.classList.toggle('v69-selected',b.dataset.kind===kind));
if(auth&&!auth.classList.contains('hidden'))$('d_message').textContent='Pieslēdzieties, lai skatītu uzdevumus.';
}
entries.forEach(([kind,label])=>{const b=document.createElement('button');b.type='button';b.className='civi-subnav-button';b.dataset.kind=kind;b.textContent=label;b.addEventListener('click',e=>{e.preventDefault();e.stopPropagation();show(kind)});sub.append(b)});
parent.addEventListener('click',e=>{e.preventDefault();e.stopImmediatePropagation();expanded=!expanded;sub.classList.toggle('v65-expanded',expanded);parent.setAttribute('aria-expanded',String(expanded));if(expanded)show(current)},true);
// Restore company management navigation, regardless of previous script failure.
let company=nav.querySelector('[data-page="companies"]');if(!company){company=document.createElement('button');company.type='button';company.className='nav';company.dataset.page='companies';company.innerHTML='<span class="nav-icon">▣</span><span>Uzņēmumi</span>';nav.querySelector('[data-page="objects"]')?.before(company)}
company.addEventListener('click',e=>{e.preventDefault();e.stopImmediatePropagation();window.page('companies')},true);
// Company selector belongs beneath CIVINITY brand, not in the top toolbar.
const selector=$('company'),label=document.querySelector('label[for="company"]'),brand=document.querySelector('aside .brand');if(selector&&brand){let box=$('v67-company');if(!box){box=document.createElement('div');box.id='v67-company';brand.after(box)}if(label)box.append(label);box.append(selector)}
// Make Enter submit login only, not registration.
$('d_password')?.addEventListener('keydown',e=>{if(e.key==='Enter'){e.preventDefault();window.dispatchLogin?.()}});
// Remove redundant top-level documents entry; document center remains in Atskaites.
nav.querySelector('[data-page="documents"]')?.remove();
})();
