/* CIVINITY object dossier: PostgreSQL-backed cadastral attachment, photos, documents. */
(()=>{'use strict';
const BASE='https://civinity-ai-api.onrender.com/api/dispatch';
const token=()=>sessionStorage.getItem('dispatch_token')||'';
const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
let objects=[], current=null, files=[];
const box=document.createElement('div');box.id='obj56';box.className='obj56-overlay';box.hidden=true;
box.innerHTML=`<div class="obj56-dialog" role="dialog" aria-modal="true" aria-label="Objekta dokumentācija">
<header class="obj56-head"><div><small>CiViNiTY · OBJEKTA KARTE</small><h2 id="obj56_title">Objekts</h2><p id="obj56_address"></p></div><button type="button" id="obj56_close" aria-label="Aizvērt">✕</button></header>
<div class="obj56-content"><div class="obj56-photo"><div id="obj56_image" class="obj56-image"><span>▥</span><p>Objekta fotogrāfija</p></div><label class="obj56-upload">📷 Pievienot objekta foto<input id="obj56_photo" type="file" accept="image/jpeg,image/png,image/webp" hidden></label></div>
<div class="obj56-info"><label>Kadastra numurs <span class="obj56-optional">(nav obligāts)</span><div class="obj56-cad-row"><input id="obj56_cad" placeholder="Kadastra numurs" maxlength="90"><button id="obj56_savecad" type="button">Saglabāt</button></div></label>
<div class="obj56-kad"><b>Kadastra dokuments</b><p>PDF vai attēls · pievienošana nav obligāta</p><div id="obj56_cadfile"></div><label class="obj56-upload">📎 Browse / Pārlūkot<input id="obj56_cad_upload" type="file" accept=".pdf,.jpg,.jpeg,.png,.webp" hidden></label></div>
<div class="obj56-doc"><div class="obj56-doc-head"><div><b>📁 Dokumentācija</b><p>Projekti, līgumi, akti, rasējumi un citi faili</p></div><label class="obj56-upload">＋ Pievienot<input id="obj56_document" type="file" accept=".pdf,.jpg,.jpeg,.png,.webp,.doc,.docx,.xls,.xlsx" hidden></label></div><div id="obj56_docs"></div></div></div></div>
<div id="obj56_msg" role="status"></div></div>`;
document.body.append(box);
const $=id=>document.getElementById(id);
async function api(path,opts={}){const r=await fetch(BASE+path,{...opts,headers:{Authorization:'Bearer '+token(),...(opts.headers||{})}});if(!r.ok){let msg;try{msg=(await r.json()).error}catch{}throw Error(msg||`HTTP ${r.status}`)}return r;}
async function get(path){return (await api(path)).json()}
function message(s,error=false){$('obj56_msg').textContent=s;$('obj56_msg').classList.toggle('error',error)}
function fileRow(f){return `<div class="obj56-file"><span>📄</span><div><b>${esc(f.filename)}</b><small>${esc(f.created?.slice(0,10)||'')}</small></div><button type="button" data-openfile="${f.id}">Atvērt</button><button type="button" data-deletefile="${f.id}" title="Dzēst">✕</button></div>`}
async function showFile(id){try{const r=await api(`/objects/${current.id}/files/${id}`);const blob=await r.blob();const url=URL.createObjectURL(blob);window.open(url,'_blank','noopener');setTimeout(()=>URL.revokeObjectURL(url),60000)}catch(e){message(e.message,true)}}
async function refresh(){files=await get(`/objects/${current.id}/files`);$('obj56_cadfile').innerHTML=files.filter(x=>x.category==='cadastre').map(fileRow).join('')||'<em>Nav pievienots</em>';
$('obj56_docs').innerHTML=files.filter(x=>x.category==='document').map(fileRow).join('')||'<em>Dokumenti vēl nav pievienoti.</em>';
const photo=files.find(x=>x.category==='photo');const target=$('obj56_image');target.innerHTML=photo?'<img alt="Objekta fotogrāfija">':'<span>▥</span><p>Objekta fotogrāfija</p>';
if(photo){try{const r=await api(`/objects/${current.id}/files/${photo.id}`);const blob=await r.blob();const url=URL.createObjectURL(blob);target.querySelector('img').src=url;target.querySelector('img').onload=()=>setTimeout(()=>URL.revokeObjectURL(url),10000)}catch(e){message(e.message,true)}}
box.querySelectorAll('[data-openfile]').forEach(b=>b.onclick=()=>showFile(b.dataset.openfile));box.querySelectorAll('[data-deletefile]').forEach(b=>b.onclick=async()=>{if(!confirm('Dzēst šo dokumentu?'))return;try{await api(`/objects/${current.id}/files/${b.dataset.deletefile}`,{method:'DELETE'});await refresh();message('Dokuments dzēsts.')}catch(e){message(e.message,true)}});
}
async function open(o){current=o;box.hidden=false;document.body.classList.add('obj56-open');$('obj56_title').textContent=o.name||'Objekts';$('obj56_address').textContent=o.address||'';$('obj56_cad').value=o.cadastral_number||'';message('');try{await refresh()}catch(e){message(e.message,true)}}
function close(){box.hidden=true;document.body.classList.remove('obj56-open');current=null}
$('obj56_close').onclick=close;box.addEventListener('click',e=>{if(e.target===box)close()});document.addEventListener('keydown',e=>{if(e.key==='Escape'&&!box.hidden)close()});
$('obj56_savecad').onclick=async()=>{if(!current)return;const number=$('obj56_cad').value.trim();try{const o=await (await api(`/objects/${current.id}`,{method:'PATCH',headers:{'Content-Type':'application/json'},body:JSON.stringify({cadastral_number:number})})).json();current=o;objects=objects.map(x=>x.id===o.id?o:x);message('Kadastra numurs saglabāts.')}catch(e){message(e.message,true)}};
async function upload(input,category){if(!current||!input.files?.length)return;const f=input.files[0];input.value='';if(f.size>10*1024*1024)return message('Maksimālais faila izmērs ir 10 MB.',true);const fd=new FormData();fd.append('file',f);fd.append('category',category);message('Augšupielādē...');try{await api(`/objects/${current.id}/files`,{method:'POST',body:fd});await refresh();message('Fails saglabāts serverī.')}catch(e){message(e.message,true)}}
$('obj56_photo').onchange=e=>upload(e.target,'photo');$('obj56_cad_upload').onchange=e=>upload(e.target,'cadastre');$('obj56_document').onchange=e=>upload(e.target,'document');
// Add action to each server object row without replacing existing navigation.
function decorate(){const list=$('objectsList');if(!list)return;const rows=[...list.querySelectorAll('.list-row')];for(let i=0;i<objects.length&&i<rows.length;i++){const o=objects[i],row=rows[i];if(row.querySelector('.obj56-openbtn'))continue;const controls=row.lastElementChild;const btn=document.createElement('button');btn.className='btn alt obj56-openbtn';btn.textContent='📁 Dokumentācija';btn.onclick=()=>open(o);controls.append(btn);const cad=document.createElement('div');cad.className='obj56-row-cad';cad.textContent='Kadastra Nr.: '+(o.cadastral_number||'nav norādīts');row.firstElementChild.append(cad);}}
window.addEventListener('civinity-objects-rendered',e=>{objects=e.detail.objects||[];setTimeout(decorate,0)});
// Cadastral number and attachment are optional; retain existing GPS and contract fields.
const cadUpload=document.createElement('div');cadUpload.className='obj56-required';cadUpload.innerHTML='<label>Kadastra dokuments (nav obligāts) <input id="obj56_initialcad" type="file" accept=".pdf,.jpg,.jpeg,.png,.webp"></label><p>Var pievienot tagad vai vēlāk sadaļā Dokumentācija.</p>';
const status=$('u_sync_status');if(status)status.parentElement.insertBefore(cadUpload,status);
// Do not override object saving: all cadastral fields are optional.
window.addEventListener('civinity-object-saved',async e=>{const f=$('obj56_initialcad')?.files[0];if(!f)return;const fd=new FormData();fd.append('file',f);fd.append('category','cadastre');try{await api(`/objects/${e.detail.id}/files`,{method:'POST',body:fd});$('obj56_initialcad').value='';$('u_sync_status').textContent='✓ Objekts un kadastra dokuments saglabāti serverī.'}catch(err){$('u_sync_status').textContent='Objekts saglabāts, bet kadastra fails netika augšupielādēts: '+err.message}});
})();
