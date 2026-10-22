/* V6.8 — navigation repair and Excel-style task register */
(()=>{'use strict';
const $=id=>document.getElementById(id),nav=$('nav'),sub=$('civi-dispatch-nav');if(!nav||!sub)return;
const dispatch=nav.querySelector('[data-page="dispatch"]');
// Replace broken legacy subnav handlers with three explicit actions.
sub.replaceChildren();
const make=(label,fn)=>{const b=document.createElement('button');b.type='button';b.className='civi-subnav-button v68-nav';b.textContent=label;b.addEventListener('click',e=>{e.preventDefault();e.stopPropagation();fn();sub.querySelectorAll('button').forEach(x=>x.classList.toggle('v68-selected',x===b))});sub.append(b);return b};
const showBase=()=>{window.page('dispatch');$('v67-ticket-statistics')?.classList.add('hidden');};
const showList=()=>{showBase();window.civiDispatchShow?.('tasks');$('v68-ticket-register')?.classList.remove('hidden');loadTickets()};
const showNew=()=>{showBase();$('v68-ticket-register')?.classList.add('hidden');window.civiDispatchShow?.('new')};
const showStats=()=>{showBase();$('v68-ticket-register')?.classList.add('hidden');document.querySelectorAll('#dispatch .d-view').forEach(x=>x.classList.remove('active'));const stat=$('v67-ticket-statistics');if(stat){stat.classList.remove('hidden');$('v67-refresh')?.click()}};
const list=make('Saraksts',showList);make('Jauns uzdevums',showNew);make('Statistika',showStats);
// Parent opens the register, while maintaining accordion behavior.
dispatch?.addEventListener('click',()=>setTimeout(()=>{if(sub.classList.contains('v65-expanded')){list.classList.add('v68-selected');showList()}},0));
// Restore standalone Uzņēmumi entry and working company workspace.
let companyBtn=nav.querySelector('[data-page="companies"]');
if(!companyBtn){companyBtn=document.createElement('button');companyBtn.type='button';companyBtn.className='nav';companyBtn.dataset.page='companies';companyBtn.innerHTML='<span class="nav-icon">▣</span><span>Uzņēmumi</span>';const obj=nav.querySelector('[data-page="objects"]');(obj||nav.lastElementChild)?.before(companyBtn)}
let companies=$('companies');if(!companies){companies=document.createElement('section');companies.className='page hidden';companies.id='companies';companies.innerHTML='<div class="section-hero"><div class="section-hero-copy"><h2>Uzņēmumi</h2><p>Uzņēmumu pārvaldība un statistika</p></div></div><div class="v68-company-tabs"><button type="button" id="v68-company-list">Jaunie uzņēmumi</button><button type="button" id="v68-company-stats">Statistika</button></div><div class="panel" id="v68-company-content"></div>';document.querySelector('main')?.append(companies)}
const companyContent=$('v68-company-content');function renderCompanies(stats=false){const sel=$('company');const opts=[...(sel?.options||[])];companyContent.innerHTML=stats?'<h2>Uzņēmumu statistika</h2><p>Reģistrēto uzņēmumu skaits: '+opts.length+'</p>':'<h2>Jaunie uzņēmumi</h2><p>Pašlaik konfigurētie uzņēmumi:</p><div class="v68-company-grid">'+opts.map(o=>'<div class="v68-company-card">'+escapeHtml(o.textContent)+'</div>').join('')+'</div><p class="hint">Jaunu juridisku personu reģistrācijas forma nav pieslēgta serverim.</p>'}
function escapeHtml(s){return String(s).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]))}
$('v68-company-list').onclick=()=>renderCompanies(false);$('v68-company-stats').onclick=()=>renderCompanies(true);
const oldPage=window.page;window.page=function(name){if(name==='companies'){document.querySelectorAll('.page').forEach(x=>x.classList.toggle('hidden',x!==companies));document.querySelectorAll('#nav .nav').forEach(x=>x.classList.toggle('active',x===companyBtn));$('pageTitle').textContent='Uzņēmumi';renderCompanies();return}return oldPage(name)};
companyBtn.onclick=()=>window.page('companies');
// Register columns follow the uploaded Tickets worksheet (25 columns).
const cols=[['id','ID'],['type','Type'],['work_manager','Work manager'],['object','Object'],['assignee','Assignee'],['title','Title'],['service','Service'],['status','Status'],['preliminary_price','Preliminary price'],['contractor','Contractor'],['created','Created at'],['description','Description'],['comment','Comment']];
const register=document.createElement('section');register.id='v68-ticket-register';register.className='v68-ticket-register hidden';register.innerHTML='<div class="v68-register-top"><div><h2>Uzdevumu saraksts · Ticket report</h2><p>13 galvenās kolonnas un statusa indikators; dati no saglabātajiem uzdevumiem.</p></div><button type="button" id="v68-ticket-reload">↻ Atjaunot</button></div><div class="v68-register-filters"><input id="v68-ticket-search" type="search" placeholder="Meklēt pēc ID, adreses, statusa, izpildītāja…"><span id="v68-ticket-count"></span></div><div class="v68-ticket-scroll"><table><thead><tr>'+cols.map(x=>'<th>'+escapeHtml(x[1])+'</th>').join('')+'</tr></thead><tbody id="v68-ticket-body"></tbody></table></div><p class="hint" id="v68-ticket-msg"></p>';
$('dispatch')?.append(register);
let data=[];function dateVal(s){const d=new Date(s||'');return Number.isNaN(+d)?'':d.toLocaleDateString('lv-LV')}
function get(t,key){
 const m=t.ticket||{};
 const value=(...keys)=>{for(const k of keys){const v=m[k]??t[k];if(v!==undefined&&v!==null&&String(v).trim()!=='')return v}return ''};
 if(key==='id')return value('number','id');
 if(key==='type')return value('type','task_type');
 if(key==='work_manager')return value('work_manager','manager');
 if(key==='object')return value('object','object_name','address');
 if(key==='assignee')return value('assignee','worker','executors');
 if(key==='title')return value('title','name');
 if(key==='service')return value('service','department');
 if(key==='status')return value('status','ticket_status','stage');
 if(key==='preliminary_price')return value('preliminary_price','preliminaryPrice','estimated_price','price');
 if(key==='contractor')return value('contractor','supplier');
 if(key==='created')return dateVal(value('created','created_at'));
 if(key==='description')return value('description','tasks');
 if(key==='comment')return value('comment','comments','note','notes');
 return value(key)
}
function indicator(t){
 const status=String(get(t,'status')).toLowerCase();
 const done=/done|closed|completed|pabeigts|izpildīts|izpildits|gatavs|pabeig/.test(status);
 if(done)return ['done','Izpildīts'];
 const raw=(t.ticket||{}).deadline||t.deadline||t.due_date||t.due_at;
 const due=raw?new Date(raw):null;
 if(due&&!Number.isNaN(+due)&&due.getTime()<Date.now())return ['overdue','Nokavēts termiņš'];
 if(/process|progress|procesā|procesa|working|started|izpildē|izpilde/.test(status))return ['progress','Procesā'];
 return ['neutral','Nav noteikts'];
}
function draw(){
 const q=$('v68-ticket-search').value.toLowerCase();
 const filtered=data.filter(t=>!q||cols.some(([key])=>String(get(t,key)).toLowerCase().includes(q)));
 $('v68-ticket-count').textContent=filtered.length+' uzdevumi';
 const tbody=$('v68-ticket-body');tbody.replaceChildren();
 if(!filtered.length){const tr=document.createElement('tr'),td=document.createElement('td');td.colSpan=cols.length+1;td.textContent='Nav saglabātu uzdevumu. Excel vēsturiskie ieraksti nav importēti.';tr.append(td);tbody.append(tr);return}
 for(const t of filtered){
  const tr=document.createElement('tr');
  for(const [key,label] of cols){const td=document.createElement('td');td.dataset.label=label;const val=String(get(t,key));td.textContent=val;td.title=val;tr.append(td)}
  const td=document.createElement('td');td.dataset.label='Indikators';td.className='v73-indicator-cell';const [state,label]=indicator(t);const dot=document.createElement('span');dot.className='v73-status-dot v73-'+state;dot.title=label;dot.setAttribute('aria-label',label);dot.setAttribute('role','img');td.append(dot);tr.append(td);tbody.append(tr)
 }
}
async function loadTickets(){const token=sessionStorage.getItem('dispatch_token');if(!token){$('v68-ticket-msg').textContent='Lai skatītu uzdevumus, pieslēdzieties savam kontam.';return}try{const res=await fetch('https://civinity-ai-api.onrender.com/api/dispatch/tasks',{headers:{Authorization:'Bearer '+token}});if(!res.ok)throw Error('HTTP '+res.status);const rows=await res.json();if(!Array.isArray(rows))throw Error('Nepareizs servera datu formāts');data=rows;draw();$('v68-ticket-msg').textContent='Tabulā redzami tikai serverī saglabātie uzdevumi. Excel vēsturiskie dati nav importēti.'}catch(e){$('v68-ticket-msg').textContent='Neizdevās ielādēt uzdevumus: '+e.message}}
$('v68-ticket-search').addEventListener('input',draw);$('v68-ticket-reload').onclick=loadTickets;
})();