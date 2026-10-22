/* V7.2: single authoritative sidebar controller. */
(()=>{'use strict';
const $=id=>document.getElementById(id);
function init(){
 const nav=$('nav'), task=$('civi-dispatch-nav'), companyBtn=nav?.querySelector('[data-page="companies"]'), parent=nav?.querySelector('[data-page="dispatch"]');
 if(!nav||!task||!companyBtn||!parent)return;
 // Legacy CSS specifically hides buttons without data-view except the first.
 // Assign data-view to each button and build an independent, explicit three-item menu.
 task.replaceChildren();task.className='v72-task-menu';task.hidden=true;
 const stat=$('v67-ticket-statistics'),table=$('v68-ticket-register');
 function hideExtras(){for(const x of [stat,table])if(x){x.classList.add('hidden');x.style.display='none'}}
 function show(mode){
  window.page('dispatch');hideExtras();
  if(mode==='list'){
   window.civiDispatchShow?.('tasks');
   if(table){table.classList.remove('hidden');table.style.display='block';$('v68-ticket-reload')?.click()}
  }else if(mode==='new'){
   window.civiDispatchShow?.('new');
   const view=document.querySelector('#dispatch .d-view[data-view="new"]');
   if(view){view.classList.add('active');view.classList.remove('hidden')}
   const form=$('civi-create-panel');if(form){form.classList.remove('hidden');form.style.display='block'}
  }else if(mode==='stats'){
   window.civiDispatchShow?.('tasks');
   document.querySelectorAll('#dispatch .d-view').forEach(v=>v.classList.remove('active'));
   if(table){table.classList.add('hidden');table.style.display='none'}
   if(stat){stat.classList.remove('hidden');stat.style.display='block';$('v67-refresh')?.click()}
  }
  task.querySelectorAll('button').forEach(b=>b.classList.toggle('v72-current',b.dataset.view===mode));
 }
 for(const [mode,label] of [['list','Saraksts'],['new','Jauns uzdevums'],['stats','Statistika']]){
  const b=document.createElement('button');b.type='button';b.className='v72-link';b.dataset.view=mode;b.textContent=label;
  b.addEventListener('click',e=>{e.preventDefault();e.stopPropagation();show(mode)});task.append(b);
 }
 // Replace parent node: removes all old click listeners and their setTimeout redirects.
 const fresh=parent.cloneNode(true);parent.replaceWith(fresh);
 fresh.addEventListener('click',e=>{e.preventDefault();e.stopPropagation();task.hidden=!task.hidden;fresh.setAttribute('aria-expanded',String(!task.hidden));if(!task.hidden)show('list')});
 fresh.setAttribute('aria-expanded','false');
 // Uzņēmumi is ONE ordinary navigation item, without a submenu.
 const companyMenu=$('v69-company-sub');if(companyMenu)companyMenu.remove();
 const companyFresh=companyBtn.cloneNode(true);companyBtn.replaceWith(companyFresh);
 companyFresh.querySelector('.v71-chevron,.v70-arrow')?.remove();
 companyFresh.addEventListener('click',e=>{e.preventDefault();e.stopPropagation();window.page('companies')});
 const page=$('companies');
 if(page){
  page.querySelector('.v68-company-tabs')?.remove();
  const content=$('v68-company-content');
  if(content){
   function render(){
    const select=$('company');const options=Array.from(select?.options||[]);
    content.innerHTML='<h2>Uzņēmumu iestatījumi</h2><p>Izvēlieties uzņēmumu vai pievienojiet jaunu.</p><div class="v72-company-list"></div><h3>Jauns uzņēmums</h3><form id="v72-company-form"><label>Uzņēmuma nosaukums<input name="name" required maxlength="160"></label><label>Reģistrācijas numurs<input name="reg" maxlength="32"></label><label>Juridiskā adrese<input name="address" maxlength="240"></label><button class="btn" type="submit">Pievienot uzņēmumu</button><p id="v72-company-msg" role="status"></p></form>';
    const list=content.querySelector('.v72-company-list');for(const opt of options){const b=document.createElement('button');b.type='button';b.className='btn alt';b.textContent=opt.textContent;b.onclick=()=>{select.value=opt.value;select.dispatchEvent(new Event('change',{bubbles:true}));window.page('settings')};list.append(b)}
    $('v72-company-form').onsubmit=e=>{e.preventDefault();const f=new FormData(e.currentTarget),name=String(f.get('name')||'').trim();if(!name)return;const id='company_'+Date.now();select.add(new Option(name,id));const raw=localStorage.getItem('civinity_companies');let companies={};try{companies=JSON.parse(raw||'{}')}catch{}companies[id]={name,reg:String(f.get('reg')||''),address:String(f.get('address')||'')};localStorage.setItem('civinity_companies',JSON.stringify(companies));select.value=id;select.dispatchEvent(new Event('change',{bubbles:true}));render();$('v72-company-msg').textContent='Uzņēmums pievienots šajā pārlūkā.'};
   }
   // Old page() wrapper rerenders the company placeholder; override AFTER calling it.
   const previous=window.page;
   window.page=function(name){const r=previous(name);if(name==='companies')render();return r};
  }
 }
 // Preserve sidebar company selection under logo, remove any topbar duplicate.
 const select=$('company'),brand=document.querySelector('aside .brand');
 if(select&&brand){let box=$('v71-company')||$('v67-company');if(!box){box=document.createElement('div');box.id='v71-company'}brand.after(box);const label=document.querySelector('label[for="company"]');if(label)box.append(label);box.append(select)}
 window.CIVINITY_V72_READY=true;
}
if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',init,{once:true});else init();
})();
