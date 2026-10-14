/* CIVINITY V6.5 — navigation, object contracts, contextual myCi chat. */
(()=>{'use strict';
const $=id=>document.getElementById(id), nav=$('nav'), task=$('civi-dispatch-nav');if(!nav||!task)return;
const parent=nav.querySelector('[data-page="dispatch"]'), tech=nav.querySelector('[data-page="technical"]');
// Existing dispatcher actions retain their original event listeners; only duplicate navigation is removed.
for(const b of [...task.querySelectorAll('button')]){
 if(b.dataset.view==='tasks'||b.dataset.view==='objects'||b.dataset.view==='reports'||b.dataset.view==='staff'||/Rēķinu|Objekti un līgumi|Administrēšana/i.test(b.textContent))b.remove();
}
const list=task.querySelector('button:not([data-view])');
if(list&&/Saraksts/i.test(list.textContent)){list.onclick=()=>{window.page('dispatch');window.civiDispatchShow?.('tasks')}}
// Reorder the visible entries: Saraksts, Jauns uzdevums, Statistika.
const newTask=task.querySelector('[data-view="new"]'),stats=[...task.querySelectorAll('button')].find(b=>/Statistika/i.test(b.textContent));
for(const b of [list,newTask,stats])if(b)task.append(b);
parent.setAttribute('aria-expanded','false');parent.insertAdjacentHTML('beforeend','<span class="v65-chevron" aria-hidden="true">⌄</span>');
let taskExpanded=false;const expandTask=v=>{taskExpanded=v;task.classList.toggle('v65-expanded',v);parent.setAttribute('aria-expanded',String(v))};
parent.addEventListener('click',()=>expandTask(!taskExpanded));
for(const b of task.querySelectorAll('button'))b.addEventListener('click',()=>expandTask(true));
// Unified reports use the existing PN/invoice generators, now only under top-level Atskaites.
const reportsLink=nav.querySelector('[data-page="reports"]');
reportsLink?.addEventListener('click',()=>{const r=[...document.querySelectorAll('#civi-dispatch-nav button')].find(b=>/Atskaites/.test(b.textContent));r?.click()});
const reportSection=$('reports'),reportPanel=$('civi-reports-v60');
if(reportSection&&reportPanel){reportSection.querySelectorAll(':scope > .section-hero,:scope > .panel').forEach(e=>e.classList.add('v65-old-report'));}
// Technical management is a collapsible sidebar group, not an always-open tab strip.
if(tech){
 tech.insertAdjacentHTML('beforeend','<span class="v65-chevron" aria-hidden="true">⌄</span>');
 const group=document.createElement('div');group.id='v65-technical-menu';group.className='v65-submenu';tech.after(group);
 const entries=[['budget','Remontdarbu plāns'],['quality','Darbu kontrole'],['docs','Dokumenti'],['client','Klientu portāls']];
 for(const [key,label] of entries){const b=document.createElement('button');b.type='button';b.className='civi-subnav-button';b.textContent=label;b.addEventListener('click',async()=>{try{await tech.onclick?.();const tab=$('technical')?.querySelector('[data-op="'+key+'"]');tab?.click();group.querySelectorAll('button').forEach(x=>x.classList.toggle('active',x===b))}catch(e){console.warn(e)}});group.append(b)}
 tech.setAttribute('aria-expanded','false');let expanded=false;
 tech.addEventListener('click',e=>{e.stopImmediatePropagation();expanded=!expanded;group.classList.toggle('v65-expanded',expanded);tech.setAttribute('aria-expanded',String(expanded));},true);
 $('technical')?.querySelector('.op-tabs')?.classList.add('v65-hidden-tabs');
}
// Object contracts/GPS move out of the estimate form; preserve original input IDs and persistence handlers.
const contract=$('estimate')?.querySelector('.unified-contract'),objects=$('objects');
if(contract&&objects){
 const panel=document.createElement('div');panel.id='v65-contract-panel';panel.className='panel hidden';
 panel.innerHTML='<div class="v65-panel-heading"><h2>Jauns līgums · Objekta dati</h2><button type="button" id="v65-contract-close" class="btn alt">Aizvērt</button></div><p class="hint">Līguma, izcenojumu un GPS dati ir piesaistīti izvēlētajam objektam.</p>';
 panel.append(contract);const save=document.createElement('button');save.type='button';save.className='btn';save.textContent='Saglabāt objekta datus';save.onclick=()=>$('saveObject')?.click();panel.append(save);objects.append(panel);
 const actions=document.createElement('div');actions.className='v65-object-actions';actions.innerHTML='<button type="button" class="btn" id="v65-new-object">＋ Jauns objekts</button><button type="button" class="btn alt" id="v65-new-contract">＋ Jauns līgums</button>';
 objects.querySelector('.section-hero')?.insertAdjacentElement('afterend',actions);
 $('v65-new-object').onclick=()=>window.newObject?.();
 $('v65-new-contract').onclick=()=>{window.page('objects');panel.classList.remove('hidden');panel.scrollIntoView({behavior:'smooth',block:'start'})};
 $('v65-contract-close').onclick=()=>panel.classList.add('hidden');
}
// Keep the global toolbar at the top even if legacy pages set large top margins.
const topbar=document.querySelector('main > .topbar');if(topbar){const main=topbar.parentElement;main.prepend(topbar)}
// Replace old navigation-to-assistant action with a compact in-page dialog.
const old=$('my-c-launcher');if(old){const button=old.cloneNode(false);button.innerHTML='<span class="v65-my">my</span><span class="v65-ci">C<span class="v65-i">ı</span></span>';button.setAttribute('aria-expanded','false');old.replaceWith(button);
 const chat=document.createElement('section');chat.id='v65-myci-chat';chat.className='hidden';chat.setAttribute('role','dialog');chat.setAttribute('aria-label','myCi asistents');chat.innerHTML=`<div class="v65-chat-header"><div><b>myCi</b><small>CIVINITY AI asistents</small></div><button id="v65-chat-close" type="button" aria-label="Aizvērt">×</button></div><div id="v65-chat-log" class="v65-chat-log" aria-live="polite"><div class="v65-bubble bot">Labdien! Kā varu palīdzēt? Varat rakstīt vai diktēt jautājumu.</div></div><form id="v65-chat-form"><textarea id="v65-chat-input" rows="2" placeholder="Rakstiet savu jautājumu…" aria-label="Jautājums"></textarea><div class="v65-chat-actions"><button type="button" id="v65-chat-mic" title="Balss ievade">🎙</button><button type="submit">Nosūtīt →</button></div><small id="v65-chat-status" role="status"></small></form>`;
 document.body.append(chat);const log=$('v65-chat-log'),input=$('v65-chat-input'),status=$('v65-chat-status');
 const toggle=show=>{chat.classList.toggle('hidden',!show);button.setAttribute('aria-expanded',String(show));if(show)input.focus()};button.onclick=()=>toggle(chat.classList.contains('hidden'));$('v65-chat-close').onclick=()=>toggle(false);
 const bubble=(content,cls)=>{const d=document.createElement('div');d.className='v65-bubble '+cls;d.textContent=content;log.append(d);log.scrollTop=log.scrollHeight};
 $('v65-chat-form').onsubmit=async e=>{e.preventDefault();const question=input.value.trim();if(!question)return;input.value='';bubble(question,'user');status.textContent='Apstrādā jautājumu…';try{const r=await fetch('https://civinity-ai-api.onrender.com/api/dispatch/v61/assistant',{method:'POST',headers:{'Content-Type':'application/json','Authorization':'Bearer '+(sessionStorage.getItem('dispatch_token')||'')},body:JSON.stringify({question,ai_summary:true})});const d=await r.json();if(!r.ok)throw Error(d.error||'HTTP '+r.status);bubble([d.answer,...(d.sources||[]).slice(0,5).map(s=>`${s.number||''}: ${s.description||''}`)].filter(Boolean).join('\n'),'bot');status.textContent=''}catch(err){bubble('Neizdevās saņemt atbildi: '+err.message,'bot');status.textContent=''}};
 let recognition=null;const mic=$('v65-chat-mic');mic.onclick=()=>{if(recognition){recognition.stop();return}const Speech=window.SpeechRecognition||window.webkitSpeechRecognition;if(!Speech){status.textContent='Šajā pārlūkā balss atpazīšana nav pieejama. Ierakstiet tekstu.';return}recognition=new Speech();recognition.lang=({lv:'lv-LV',ru:'ru-RU',en:'en-US',lt:'lt-LT'})[$('language')?.value]||'lv-LV';recognition.onresult=e=>{input.value+=(input.value?' ':'')+Array.from(e.results).map(x=>x[0].transcript).join(' ')};recognition.onerror=e=>status.textContent='Mikrofona kļūda: '+e.error;recognition.onend=()=>{recognition=null;mic.classList.remove('recording')};recognition.start();mic.classList.add('recording');status.textContent='Klausos…'};
}
})();