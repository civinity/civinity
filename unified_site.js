/* CIVINITY AI unified access + object/contract bridge. */
(()=>{'use strict';
const $=id=>document.getElementById(id), token=()=>sessionStorage.getItem('dispatch_token')||'', BASE='https://civinity-ai-api.onrender.com/api/dispatch';
const safe=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const fields={code:'u_code',ownership:'u_owner',customer:'u_customer',contract:'u_contract',rate:'u_rate',vat:'u_vat',latitude:'u_lat',longitude:'u_lon',radius:'u_radius',cadastral_number:'u_cadastre'};
let remote=[], remoteReady=false, activeServerId=null, currentUser=null, gateBusy=false;
const gate=document.createElement('div');gate.id='u_gate';gate.innerHTML='<div class="u-login-card"><div class="u-login-brand"><div class="u-logo">C<span>i</span>ViNiTY</div><p>Būvniecība · Apsaimniekošana · AI</p></div><div id="u_auth_host"></div><div class="u-auth-actions"><button type="button" id="u_register_switch">Reģistrēties</button><button type="button" id="u_forgot_switch">Aizmirsi paroli?</button></div><div id="u_forgot_note" hidden>Paroles atjaunošana pašlaik nav pieslēgta. Sazinieties ar sistēmas administratoru, lai droši atjaunotu piekļuvi.</div></div>';
document.body.append(gate);
const auth=$('d_auth'),msg=$('d_message');$('u_auth_host').append(auth,msg);
const regSwitch=$('u_register_switch'),forgotSwitch=$('u_forgot_switch'),forgotNote=$('u_forgot_note');let registering=false;const nameField=$('d_name').closest('label');const registerAction=auth.querySelector('button[onclick="dispatchRegister()"]');const loginAction=auth.querySelector('button[onclick="dispatchLogin()"]');function loginMode(on){registering=on;nameField.style.display=on?'block':'none';registerAction.style.display=on?'block':'none';loginAction.style.display=on?'none':'block';regSwitch.textContent=on?'Atpakaļ uz pieslēgšanos':'Reģistrēties';forgotNote.hidden=true;msg.textContent='';}loginMode(false);regSwitch.onclick=()=>loginMode(!registering);forgotSwitch.onclick=()=>{forgotNote.hidden=!forgotNote.hidden};

async function request(path,method='GET',data){const r=await fetch(BASE+path,{method,headers:{Authorization:'Bearer '+token(),...(data?{'Content-Type':'application/json'}:{})},body:data?JSON.stringify(data):undefined});let j;try{j=await r.json()}catch{j={}}if(!r.ok)throw Error(j.error||`HTTP ${r.status}`);return j;}
function setGate(allowed){
 document.body.classList.toggle('site-authenticated',Boolean(allowed));
 gate.style.display=allowed?'none':'grid';
 if(!allowed){remoteReady=false;currentUser=null;}
}
// Authentication is the ONLY condition controlling access to the main interface.
// Object sync or dispatcher data errors must never force a second login.
async function loadObjectsSafely(){
 try{await loadObjects();}
 catch(e){console.warn('Object sync unavailable:',e);const status=$('u_sync_status');if(status)status.textContent='Objektu sinhronizācija īslaicīgi nav pieejama.';}
}
async function verify(){
 if(gateBusy)return;
 gateBusy=true;
 try{
  if(!token()){setGate(false);return;}
  let user;
  try{user=await request('/me');}
  catch(e){setGate(false);msg.textContent='Sesija beigusies. Lūdzu, pieslēdzieties vēlreiz.';return;}
  if(!user || user.approved!==true){setGate(false);msg.textContent='Konts gaida administratora apstiprinājumu.';return;}
  currentUser=user;
  setGate(true);
  // Do not await unrelated data loads while deciding if the user is authenticated.
  void loadObjectsSafely();
 }finally{gateBusy=false;}
}
const oldLogout=window.dispatchLogout;
window.dispatchLogout=async function(){
 try{if(typeof oldLogout==='function')await oldLogout();}
 finally{sessionStorage.removeItem('dispatch_token');setGate(false);}
};
const oldLogin=window.dispatchLogin;
window.dispatchLogin=async function(){
 if(typeof oldLogin==='function')await oldLogin();
 if(token())await verify();
};
const oldRegister=window.dispatchRegister;
window.dispatchRegister=async function(){if(typeof oldRegister==='function')await oldRegister();};
function objCode(o){return String(o.code||'').trim().toLowerCase()}
async function loadObjects(){remote=await request('/objects');remoteReady=true;renderUnifiedObjects();}
function objectData(){const raw={name:$('name').value.trim(),address:$('address').value.trim(),code:$('u_code').value.trim(),ownership:$('u_owner').value.trim(),customer:$('u_customer').value.trim(),contract:$('u_contract').value.trim(),company:$('company').value,rate:Number($('u_rate').value||0),vat:Number($('u_vat').value||21),radius:Number($('u_radius').value||150)};raw.cadastral_number=$('u_cadastre').value.trim();raw.latitude=$('u_lat').value?Number($('u_lat').value):null;raw.longitude=$('u_lon').value?Number($('u_lon').value):null;return raw;}
function fillContract(o){activeServerId=o?.id||null;for(const [key,id] of Object.entries(fields))$(id).value=o?.[key]??(key==='vat'?21:key==='radius'?150:'');}
// Existing local object selection stays functional; map it to server object by code.
const originalFill=window.fill;window.fill=function(o){originalFill(o);const r=remote.find(x=>objCode(x)===objCode(o)&&objCode(o))||remote.find(x=>x.address===o.address&&x.name===o.name);fillContract(r||o);};
const originalNew=window.newObject;window.newObject=function(){originalNew();fillContract(null);$('u_sync_status').textContent='';};
const originalSave=window.saveObject;window.saveObject=function(){const ok=originalSave();if(ok)saveServer().catch(e=>{$('u_sync_status').textContent='Servera saglabāšanas kļūda: '+e.message;console.error(e)});return ok;};
async function saveServer(){const p=objectData();if(!p.code){p.code='OBJ-'+(crypto.randomUUID?crypto.randomUUID().slice(0,12):String(Date.now()));$('u_code').value=p.code;} // Technical identifier for dispatcher; no mandatory input.
 if(!p.address)p.address='';
 if(!currentUser||!['administrators','vaditajs'].includes(currentUser.role)){$('u_sync_status').textContent='Nav tiesību saglabāt serverī. Lokālais ieraksts paliek pārlūkā.';return;}
 const existing=remote.find(x=>objCode(x)===objCode(p));let result;
 if(activeServerId||existing){const id=activeServerId||existing.id;if(existing&&activeServerId&&existing.id!==activeServerId)throw Error('Objekta kods jau izmantots citam objektam');result=await request('/objects/'+id,'PATCH',p);}
 else result=await request('/objects','POST',p);
 activeServerId=result.id;window.dispatchEvent(new CustomEvent('civinity-object-saved',{detail:{id:result.id}}));$('u_sync_status').textContent='✓ Objekts un līguma dati saglabāti serverī.';await loadObjects();if(typeof window.dispatchInit==='function'&&!$('d_workspace').classList.contains('hidden'))window.dispatchInit();}
function renderUnifiedObjects(){const list=$('objectsList');if(!list)return;
 const locals=typeof objects!=='undefined'?objects:[];const remoteCodes=new Set(remote.map(objCode));const localOnly=locals.filter(o=>!remoteCodes.has(objCode(o)));
 const row=(o,server)=>`<div class="list-row"><div><b>${safe(o.name||o.address)}</b><div class="muted">${safe(o.address)} · ${safe(o.code||'Bez koda')} ${server?'<span class="u-server-badge">Serverī</span>':'<span class="u-local-badge">Lokāli</span>'}</div></div><div><button class="btn alt" data-u-open="${server?'s':'l'}:${safe(o.id)}">Atvērt</button></div></div>`;
 list.innerHTML=remote.map(o=>row(o,true)).join('')+localOnly.map(o=>row(o,false)).join('')||'Nav objektu.';
 window.dispatchEvent(new CustomEvent('civinity-objects-rendered',{detail:{objects:remote}}));list.querySelectorAll('[data-u-open]').forEach(b=>b.onclick=()=>{const [kind,id]=b.dataset.uOpen.split(':');const o=kind==='s'?remote.find(x=>String(x.id)===id):locals.find(x=>String(x.id)===id);if(!o)return;if(kind==='s'){const old=locals.find(x=>objCode(x)===objCode(o)&&objCode(o));originalFill(old||{id:'server-'+o.id,name:o.name,address:o.address,customer:o.customer,company:o.company});fillContract(o);}else window.fill(o);});
}
const oldRender=window.renderObjects;window.renderObjects=function(){if(remoteReady)renderUnifiedObjects();else oldRender();};
// Route object management from dispatcher to the existing site section.
const nav=$('dispatch')?.querySelector('.d-menu');if(nav){const b=document.createElement('button');b.type='button';b.className='d-navbtn';b.innerHTML='<span class="d-icon">▦</span><span>Objekti un līgumi ↗</span>';b.onclick=()=>window.page('objects');nav.append(b);}
// Keep registration available on login screen; the account approval remains with admin.
setGate(false); // Stay on login until the user explicitly submits credentials.

})();
