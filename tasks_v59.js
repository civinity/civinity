/* CIVINITY V5.9: unified task navigation and enhanced creation form. */
(()=>{'use strict';
const $=id=>document.getElementById(id), API='https://civinity-ai-api.onrender.com/api/dispatch';
const nav=$('civi-dispatch-nav');if(!nav)return;
const request=async(path,method='GET',body,form=false)=>{const token=sessionStorage.getItem('dispatch_token');const h={Authorization:'Bearer '+token};if(body&&!form)h['Content-Type']='application/json';const r=await fetch(API+path,{method,headers:h,body:body?(form?body:JSON.stringify(body)):undefined});const j=await r.json().catch(()=>({}));if(!r.ok)throw Error(j.error||'HTTP '+r.status);return j};
const oldButtons=[...nav.querySelectorAll('button')];
const find=view=>oldButtons.find(b=>b.dataset.view===view);
const newBtn=find('new'),reports=find('reports'),tasks=find('tasks'),staff=find('staff');
if(tasks)tasks.remove();
const existing=[...nav.querySelectorAll('button')];existing.forEach(b=>b.remove());
const mk=(label,click)=>{const b=document.createElement('button');b.type='button';b.className='civi-subnav-button';b.textContent=label;b.addEventListener('click',click);nav.append(b);return b};
const go=view=>{window.page('dispatch');if(typeof window.civiDispatchShow==='function')window.civiDispatchShow(view);};
if(newBtn){newBtn.textContent='＋ Jauns uzdevums';newBtn.addEventListener('click',()=>setTimeout(enhance,0));nav.append(newBtn)}
if(reports){reports.textContent='▤ PN akti un atskaites';nav.append(reports)}
mk('▦ Objekti un līgumi',()=>window.page('objects'));
mk('▥ Statistika',()=>go('home'));
mk('€ Rēķinu dokumenti',()=>window.page('documents'));
const invoice=$('civi-invoice-link');if(invoice){invoice.remove();invoice.className='civi-subnav-button';nav.append(invoice)}
const admin=$('civi-admin-users');if(admin){admin.remove();admin.className='civi-subnav-button';nav.append(admin)}
if(staff)staff.remove();
// Remove legacy menu and duplicate central create button.
document.querySelectorAll('.civi-task-create').forEach(b=>b.remove());
const legacy=$('d_who');if(legacy?.parentElement)legacy.parentElement.style.setProperty('display','none','important');
const internal=document.querySelector('#dispatch .d-menu');if(internal)internal.style.setProperty('display','none','important');
const form=$('d_manage');const newView=document.querySelector('#dispatch .d-view[data-view="new"]');
if(!newView)return;
const oldCard=newView.querySelector('.d-card');if(!oldCard)return;
const section=oldCard.querySelector('.d-section')||oldCard;
const desc=$('d_description'),object=$('d_obj'),worker=$('d_worker');
const createBtn=[...section.querySelectorAll('button')].find(b=>b.getAttribute('onclick')?.includes('dispatchCreate'));
const modal=document.createElement('div');modal.id='civi-create-panel';modal.className='civi-create-panel';
modal.innerHTML=`<div class="civi-create-header"><div><span class="civi-kicker">CIVINITY · DARBA UZDEVUMI</span><h2>Jauns uzdevums</h2><p>Izvēlieties objektu, meistarus un aprakstiet nepieciešamos darbus.</p></div><span class="civi-create-icon">＋</span></div><div class="civi-create-grid"><div class="civi-create-field" id="civi-object-slot"><label>Objekts</label><input id="civi-object-search" placeholder="Meklēt pēc nosaukuma vai adreses…"><div class="civi-help" id="civi-object-info">Izvēlieties objektu no saraksta.</div></div><div class="civi-create-field" id="civi-master-slot"><label>Meistars</label><input id="civi-master-search" placeholder="Meklēt meistaru…"><div id="civi-master-choices" class="civi-master-choices"></div><div id="civi-selected-masters" class="civi-selected-masters"></div></div></div><div class="civi-create-field civi-description"><div class="civi-description-top"><label>Darba apraksts</label><div><button id="civi-task-mic" type="button" title="Balss ievade">🎙️ Ierunāt</button><button id="civi-task-ai" type="button">✨ AI · Sakārtot tekstu</button></div></div><div id="civi-description-slot"></div></div><div class="civi-create-field"><label>Fotogrāfijas</label><div id="civi-drop-zone" class="civi-drop-zone" tabindex="0">📷 Velciet foto šeit vai <button type="button" id="civi-browse">Pārlūkot</button><input id="civi-task-files" type="file" accept="image/*" multiple hidden></div><div id="civi-photo-previews" class="civi-photo-previews"></div></div><div id="civi-extra-fields"></div><div class="civi-create-footer"><span id="civi-create-status" role="status"></span><button type="button" id="civi-task-cancel">Atcelt</button><button type="button" id="civi-task-submit">Izveidot uzdevumu</button></div>`;
oldCard.replaceWith(modal);
const objectSlot=$('civi-object-slot'),masterSlot=$('civi-master-slot');objectSlot.insertBefore(object, $('civi-object-info'));masterSlot.insertBefore(worker,$('civi-master-choices'));
worker.multiple=true;worker.size=5;worker.style.display='none';
$('civi-description-slot').append(desc);desc.rows=9;desc.placeholder='Aprakstiet darbus, vietu, apjomus un svarīgās prasības…';
const extra=$('civi-extra-fields');for(const id of ['d_department','d_payment','d_priority']){const el=$(id);if(el)extra.append(el.closest('label')||el)}
if(createBtn)createBtn.remove();
const objectInfo=()=>{const opt=object.selectedOptions[0];$('civi-object-info').textContent=opt?.textContent||'Objekts nav izvēlēts';};object.addEventListener('change',objectInfo);objectInfo();
$('civi-object-search').addEventListener('input',e=>{const q=e.target.value.toLowerCase();for(const o of object.options)o.hidden=!o.textContent.toLowerCase().includes(q)});
const chosen=new Set();let masters=[];
async function loadMasters(){try{const users=await request('/users');masters=users.filter(u=>u.approved&&u.role==='meistars');drawMasters()}catch(e){$('civi-master-choices').textContent='Meistaru saraksts nav pieejams: '+e.message}}
function drawMasters(){const q=$('civi-master-search').value.toLowerCase(),list=$('civi-master-choices');list.replaceChildren();for(const m of masters.filter(u=>u.name.toLowerCase().includes(q))){const row=document.createElement('label');row.className='civi-master-row';const box=document.createElement('input');box.type='checkbox';box.checked=chosen.has(m.id);box.onchange=()=>{box.checked?chosen.add(m.id):chosen.delete(m.id);drawChosen()};row.append(box,document.createTextNode(' '+m.name));list.append(row)}drawChosen()}
function drawChosen(){const box=$('civi-selected-masters');box.replaceChildren();for(const id of chosen){const m=masters.find(x=>x.id===id);if(!m)continue;const tag=document.createElement('span');tag.textContent=m.name+' ×';tag.onclick=()=>{chosen.delete(id);drawMasters()};box.append(tag)}}
$('civi-master-search').addEventListener('input',drawMasters);
const files=[];const input=$('civi-task-files'),drop=$('civi-drop-zone');$('civi-browse').onclick=()=>input.click();
function addFiles(incoming){for(const f of incoming){if(!f.type.startsWith('image/'))continue;if(f.size>4*1024*1024){status('Maksimālais foto izmērs ir 4 MB');continue}files.push(f)}renderFiles()}
function renderFiles(){const box=$('civi-photo-previews');box.replaceChildren();files.forEach((f,i)=>{const tile=document.createElement('div');const img=document.createElement('img');const url=URL.createObjectURL(f);img.src=url;img.onload=()=>URL.revokeObjectURL(url);const b=document.createElement('button');b.type='button';b.textContent='×';b.onclick=()=>{files.splice(i,1);renderFiles()};tile.append(img,b);box.append(tile)})}
input.onchange=()=>{addFiles(input.files);input.value=''};drop.ondragover=e=>{e.preventDefault();drop.classList.add('drag')};drop.ondragleave=()=>drop.classList.remove('drag');drop.ondrop=e=>{e.preventDefault();drop.classList.remove('drag');addFiles(e.dataTransfer.files)};
function status(t){$('civi-create-status').textContent=t}
$('civi-task-ai').onclick=async()=>{try{status('AI apstrādā tekstu…');const r=await request('/ai-task','POST',{text:desc.value});desc.value=r.text;status('Teksts sakārtots. Pārbaudiet faktus.')}catch(e){status(e.message)}};
let recorder=null,chunks=[],speech=null;
$('civi-task-mic').onclick=async()=>{const b=$('civi-task-mic');if(speech){speech.stop();speech=null;b.textContent='🎙️ Ierunāt';return}if(recorder?.state==='recording'){recorder.stop();b.textContent='🎙️ Ierunāt';return}
 const SR=window.SpeechRecognition||window.webkitSpeechRecognition;
 if(SR){speech=new SR();speech.lang='lv-LV';speech.continuous=true;speech.onresult=e=>{for(let i=e.resultIndex;i<e.results.length;i++)if(e.results[i].isFinal)desc.value+=(desc.value?' ':'')+e.results[i][0].transcript};speech.onerror=e=>status('Mikrofons: '+e.error);speech.onend=()=>{speech=null;b.textContent='🎙️ Ierunāt';if(desc.value.trim())$('civi-task-ai').click()};speech.start();b.textContent='■ Apturēt';status('Notiek balss atpazīšana…');return}
 try{if(!window.MediaRecorder)throw Error('Pārlūks neatbalsta audio ierakstu');const stream=await navigator.mediaDevices.getUserMedia({audio:true});chunks=[];recorder=new MediaRecorder(stream);recorder.ondataavailable=e=>chunks.push(e.data);recorder.onstop=async()=>{stream.getTracks().forEach(t=>t.stop());try{status('Atpazīst audio…');const blob=new Blob(chunks,{type:recorder.mimeType});const f=new FormData();f.append('audio',blob,'uzdevums.webm');const r=await request('/transcribe-task','POST',f,true);desc.value+=(desc.value?' ':'')+r.text;await $('civi-task-ai').click()}catch(e){status(e.message)}};recorder.start();b.textContent='■ Apturēt';status('Notiek audio ieraksts…')}catch(e){status(e.message)}};
async function submit(){const ids=[...chosen];if(!object.value)return status('Izvēlieties objektu');if(!ids.length)return status('Izvēlieties vismaz vienu meistaru');if(!desc.value.trim())return status('Ievadiet darba aprakstu');const b=$('civi-task-submit');b.disabled=true;try{status('Saglabā uzdevumu…');const t=await request('/tasks','POST',{object_id:Number(object.value),worker_ids:ids,department:$('d_department').value,description:desc.value,payment:$('d_payment').value,priority:$('d_priority').value});let errors=0;for(const f of files){const fd=new FormData();fd.append('photo',f);try{await request('/tasks/'+t.id+'/photo','POST',fd,true)}catch(e){errors++;console.error(e)}}status('Izveidots '+t.number+(errors?' · '+errors+' foto neizdevās augšupielādēt':''));files.length=0;renderFiles();chosen.clear();drawMasters();desc.value='';await window.dispatchInit();go('tasks')}catch(e){status(e.message)}finally{b.disabled=false}}
$('civi-task-submit').onclick=submit;$('civi-task-cancel').onclick=()=>go('tasks');
function enhance(){if(!masters.length)loadMasters();}
newBtn?.addEventListener('click',enhance);
// Automatically refresh employee notifications when the user opens task workspace.
const bell=document.createElement('div');bell.id='civi-task-notices';bell.className='civi-task-notices';const summary=$('civi-task-summary');summary?.insertAdjacentElement('afterend',bell);
async function notices(){try{const items=await request('/notifications');const unread=items.filter(n=>!n.seen);bell.textContent=unread.length?'🔔 '+unread.length+' jauni uzdevumu paziņojumi':''}catch{}}
const original=window.dispatchInit;window.dispatchInit=async function(...args){const r=await original?.(...args);notices();return r};
})();
