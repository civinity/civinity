/* CIVINITY V6.0: one task list entry and unified reports. */
(()=>{'use strict';
const $=id=>document.getElementById(id),nav=$('civi-dispatch-nav');if(!nav)return;
const API='https://civinity-ai-api.onrender.com/api/dispatch';
const token=()=>sessionStorage.getItem('dispatch_token');
async function api(path){const r=await fetch(API+path,{headers:{Authorization:'Bearer '+token()}});if(!r.ok){const j=await r.json().catch(()=>({}));throw Error(j.error||'HTTP '+r.status)}return r}
const make=(label)=>{const b=document.createElement('button');b.type='button';b.className='civi-subnav-button';b.textContent=label;return b};
// The parent Uzdevumi opens the table. The first child is a clearly labeled Saraksts.
const list=make('☷ Saraksts');nav.prepend(list);
function openList(){window.page('dispatch');const view=document.querySelector('#dispatch .d-view[data-view="tasks"]');if(typeof window.civiDispatchShow==='function')window.civiDispatchShow('tasks');else if(view){document.querySelectorAll('#dispatch .d-view').forEach(v=>v.classList.toggle('active',v===view))}nav.querySelectorAll('.civi-subnav-button').forEach(b=>b.classList.remove('active'));list.classList.add('active')}
list.addEventListener('click',openList);
// Remove duplicated reporting links; keep existing task, object, statistics and admin handlers.
const report=nav.querySelector('[data-view="reports"]');
const invoice=$('civi-invoice-link');
for(const b of [...nav.querySelectorAll('button')]){if(b===report||b===invoice||/Rēķinu dokumenti/i.test(b.textContent))b.remove()}
const atskaites=make('▤ Atskaites');const newButton=nav.querySelector('[data-view="new"]');if(newButton)newButton.insertAdjacentElement('afterend',atskaites);else list.insertAdjacentElement('afterend',atskaites);
// Remove any central create shortcut; sidebar is the only create action.
function cleanup(){document.querySelectorAll('.civi-task-create').forEach(x=>x.remove())}
cleanup();new MutationObserver(cleanup).observe($('dispatch'),{childList:true,subtree:true});
// Keep the original PN report controls and callbacks; move them to a polished unified workspace.
const panel=document.createElement('div');panel.id='civi-reports-v60';panel.className='civi-reports-v60 hidden';
panel.innerHTML=`<div class="civi-report-head"><span class="civi-report-eyebrow">CIVINITY · DOKUMENTU CENTRS</span><h2>Atskaites</h2><p>PN akti, mēneša atskaites un rēķinu projekti vienuviet.</p></div><div class="civi-report-tabs"><button type="button" data-tab="pn" class="active">▤ PN akti</button><button type="button" data-tab="invoice">€ Rēķini</button></div><div class="civi-report-box" id="civi-v60-controls"><div id="civi-v60-legacy"></div><div class="civi-report-select"><label for="civi-v60-pn">Sagatavotie PN akti</label><select id="civi-v60-pn"><option value="">Izvēlieties aktu…</option></select><button type="button" id="civi-v60-refresh">↻ Atjaunot</button></div><div class="civi-report-actions"><button type="button" id="civi-v60-preview">◉ Priekšskatījums</button><button type="button" id="civi-v60-pdf">↓ PDF</button><button type="button" id="civi-v60-xlsx">↓ Excel (.xlsx)</button></div><p id="civi-v60-msg" role="status"></p></div><div class="civi-report-preview hidden" id="civi-v60-preview-box"><div class="civi-report-preview-title">Dokumenta priekšskatījums <button type="button" id="civi-v60-close">×</button></div><div id="civi-v60-preview-content"></div></div>`;
const dispatch=$('dispatch'),workspace=$('d_workspace');$('reports').append(panel);
const legacy=$('d_month');if(legacy){$('civi-v60-legacy').append(legacy);legacy.classList.remove('hidden')}
const msg=$('civi-v60-msg'),select=$('civi-v60-pn'),box=$('civi-v60-preview-box'),content=$('civi-v60-preview-content');
let tab='pn',role='';
function showReport(){window.page('reports');document.querySelectorAll('#dispatch .d-view').forEach(v=>v.classList.remove('active'));panel.classList.remove('hidden');nav.querySelectorAll('.civi-subnav-button').forEach(b=>b.classList.remove('active'));atskaites.classList.add('active');refresh()}
function hideReport(){panel.classList.add('hidden');box.classList.add('hidden')}
atskaites.addEventListener('click',showReport);
for(const b of nav.querySelectorAll('button:not(.civi-report-internal)'))if(b!==atskaites)b.addEventListener('click',hideReport);
async function refresh(){msg.textContent='Ielādē aktus…';try{const me=await (await api('/me')).json();role=me.role;const acts=await (await api('/pn')).json();select.replaceChildren(new Option('Izvēlieties aktu…',''));for(const a of acts)select.add(new Option(a.number+' — '+a.object,a.id));msg.textContent=acts.length?'Pieejami '+acts.length+' PN akti.':'Vēl nav sagatavotu PN aktu.';updateRole()}catch(e){msg.textContent=e.message}}
function updateRole(){const canInvoice=['administrators','vaditajs'].includes(role);panel.querySelector('[data-tab="invoice"]').hidden=!canInvoice;if(!canInvoice&&tab==='invoice')switchTab('pn')}
function switchTab(name){tab=name;panel.querySelectorAll('[data-tab]').forEach(b=>b.classList.toggle('active',b.dataset.tab===name));$('civi-v60-legacy').style.display=name==='pn'?'':'none';$('civi-v60-pdf').textContent=name==='invoice'?'↓ Rēķins PDF':'↓ PN akts PDF';$('civi-v60-xlsx').hidden=name==='invoice';box.classList.add('hidden');msg.textContent=name==='invoice'?'Rēķinu projekti pieejami administratoram un vadītājam.':'PN akti un mēneša atskaites.'}
panel.querySelectorAll('[data-tab]').forEach(b=>b.onclick=()=>switchTab(b.dataset.tab));$('civi-v60-refresh').onclick=refresh;
function endpoint(ext){if(!select.value)throw Error('Vispirms izvēlieties PN aktu');if(tab==='invoice'){if(ext!=='pdf')throw Error('Rēķinu Excel vēl nav pieejams');return '/invoices/'+encodeURIComponent(select.value)+'/pdf'}return '/pn/'+encodeURIComponent(select.value)+'/'+ext}
async function download(ext){try{msg.textContent='Sagatavo dokumentu…';const r=await api(endpoint(ext));const blob=await r.blob();const url=URL.createObjectURL(blob),a=document.createElement('a');a.href=url;a.download=(tab==='invoice'?'Rekins_PROJEKTS_':'PN_')+select.value+'.'+ext;document.body.append(a);a.click();a.remove();setTimeout(()=>URL.revokeObjectURL(url),60000);msg.textContent='Dokuments sagatavots.'}catch(e){msg.textContent=e.message}}
$('civi-v60-pdf').onclick=()=>download('pdf');$('civi-v60-xlsx').onclick=()=>download('xlsx');
$('civi-v60-preview').onclick=async()=>{try{msg.textContent='Ielādē priekšskatījumu…';const r=await api(endpoint('pdf'));const blob=await r.blob(),url=URL.createObjectURL(blob);content.replaceChildren();const frame=document.createElement('iframe');frame.title='PDF priekšskatījums';frame.src=url;frame.onload=()=>setTimeout(()=>URL.revokeObjectURL(url),120000);content.append(frame);box.classList.remove('hidden');msg.textContent='PDF priekšskatījums.'}catch(e){msg.textContent=e.message}};
$('civi-v60-close').onclick=()=>{box.classList.add('hidden');content.replaceChildren()};
const originalPage=window.page;window.page=function(name){if(name!=='reports')hideReport();return originalPage(name)};
// Ensure clicking the parent Uzdevumi always goes to the main list, never the report form.
const parent=$('nav')?.querySelector('[data-page="dispatch"]');parent?.addEventListener('click',()=>{hideReport();setTimeout(openList,0)});
})();
