"""Independent, evidence-only pricing. AI cannot set money amounts."""
import os, csv, io, json, re, math, statistics, threading, uuid, time
from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
from urllib.parse import urlsplit
from concurrent.futures import ThreadPoolExecutor
from flask import Blueprint, request, jsonify
from openai import OpenAI

bp=Blueprint('verified_pricing',__name__)
POOL=ThreadPoolExecutor(max_workers=2)
JOBS={}
LOCK=threading.Lock()
SHOP_HOSTS=('depo.lv','ksenukai.lv','buvserviss.lv','kursi.lv','prof.lv','bauhof.lv','buvniecibas-abc.lv')
D=lambda x: Decimal(str(x))
def money(x):return str(D(x).quantize(D('0.01'),rounding=ROUND_HALF_UP))
def valid_url(url):
 try:
  u=urlsplit(url);host=(u.hostname or '').lower()
  return u.scheme=='https' and u.username is None and u.password is None and u.port in (None,443) and any(host==h or host.endswith('.'+h) for h in SHOP_HOSTS)
 except (ValueError,TypeError):return False

def tokens(s):return set(re.findall(r'[a-zāčēģīķļņšūž0-9]{3,}',str(s).lower()))
def match(a,b):
 a=tokens(a);b=tokens(b)
 return len(a&b)>=max(1,min(2,len(a)))

def load_csv(filename):
 path=os.path.join(os.path.dirname(__file__),filename)
 if not os.path.exists(path):return []
 with open(path,encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))

def parse_money(v):
 try:
  v=D(str(v).replace(',','.').replace(' ',''))
  return v if v>0 and v<1000000 else None
 except Exception:return None

def verified_catalog():
 """Only operator-curated rows with a direct URL and explicit VAT/pack data."""
 result=[]
 for r in load_csv('materials_catalog.csv'):
  if not valid_url(r.get('url','')) or not parse_money(r.get('price_eur')):continue
  if r.get('vat_included') not in ('yes','no'):continue
  if not parse_money(r.get('pack_quantity')):continue
  result.append(r)
 return result

def work_catalog():
 result=[]
 for r in load_csv('labor_prices.csv'):
  if not r.get('url','').startswith('https://') or not parse_money(r.get('price_eur')):continue
  if r.get('vat_included') not in ('yes','no'):continue
  result.append(r)
 return result

def extract_product(url, expected):
 """Verify a public product page JSON-LD, never use model-extracted prices."""
 if not valid_url(url):return None
 import requests
 from bs4 import BeautifulSoup
 try:
  r=requests.get(url,timeout=(3,6),headers={'User-Agent':'Mozilla/5.0 CivinityPriceChecker/2.0'},allow_redirects=False)
  if r.status_code!=200 or len(r.content)>2000000:return None
  soup=BeautifulSoup(r.text,'html.parser')
  for tag in soup.select('script[type="application/ld+json"]'):
   try:data=json.loads(tag.string or tag.get_text())
   except Exception:continue
   nodes=data if isinstance(data,list) else [data]
   while nodes:
    n=nodes.pop()
    if isinstance(n,list):nodes.extend(n);continue
    if not isinstance(n,dict):continue
    if '@graph' in n:nodes.append(n['@graph'])
    typ=n.get('@type',[]);typ=[typ] if isinstance(typ,str) else typ
    if 'Product' not in typ or not match(expected,n.get('name','')):continue
    offers=n.get('offers',[]);offers=[offers] if isinstance(offers,dict) else offers
    for o in offers:
     if not isinstance(o,dict) or str(o.get('priceCurrency','')).upper()!='EUR':continue
     p=parse_money(o.get('price'))
     if p:return {'name':n.get('name',''),'price_eur':money(p),'url':url,'vat_included':None,'source':'LIVE_JSONLD','checked_at':datetime.now(timezone.utc).isoformat()}
 except Exception:return None
 return None

def candidate_urls(ai,term):
 """Web search only discovers URLs; prices always validated from original page."""
 try:
  result=ai.responses.create(model=os.getenv('PRICE_RESEARCH_MODEL','gpt-4.1-mini'),tools=[{'type':'web_search_preview','search_context_size':'low'}],input='Find up to 3 direct Latvian construction retailer product URLs for '+term[:150]+'. Return ONLY JSON {"urls":["https://..."]}. No price claims.',timeout=15)
  raw=result.output_text;start=raw.find('{');end=raw.rfind('}')
  return [u for u in json.loads(raw[start:end+1]).get('urls',[]) if valid_url(u)][:3]
 except Exception:return []

def spec_from_ai(description,images):
 ai=OpenAI(api_key=os.environ['OPENAI_API_KEY'],timeout=45,max_retries=0)
 content=[{'type':'text','text':description[:6000]}]
 for img in images[:2]:
  if isinstance(img,str) and img.startswith(('data:image/jpeg;base64,','data:image/png;base64,','data:image/webp;base64,')) and len(img)<4000000:content.append({'type':'image_url','image_url':{'url':img,'detail':'low'}})
 prompt="""You are a Latvian building quantity surveyor. Return JSON only. You MUST NOT suggest ANY prices, prices are calculated by separate software. Output {"summary":"...","items":[{"name":"...","kind":"labor|material|machine","unit":"m²|m|gab.|kg|l|h|iep.","quantity":1,"specification":"technical characteristics, packaging or consumption","quantity_basis":"calculation or assumption"}],"assumptions":[],"missing_data":[]}. Separate every material and labor task, include realistic consumption, allow quantities unknown as null. No made-up dimensions from photos. In Latvian. Material items must be separate from labor. Use no money fields.""" 
 r=ai.chat.completions.create(model=os.getenv('OPENAI_MODEL','gpt-4.1-mini'),messages=[{'role':'system','content':prompt},{'role':'user','content':content}],response_format={'type':'json_object'},max_tokens=3300,temperature=0.1)
 obj=json.loads(r.choices[0].message.content)
 return obj,ai

def facade_spec(description):
 """Deterministic ETICS takeoff; assumptions are explicitly labeled, not AI guesses."""
 text=description.lower()
 if not any(w in text for w in ('fasād','fasad')) or not any(w in text for w in ('siltin','putupolistirol','polistirol','eps')):return None
 area_match=re.search(r'(?:platība|platiba|площадь|area)\s*[:=]?\s*(\d+(?:[.,]\d+)?)\s*m',text)
 if not area_match:
  area_match=re.search(r'(\d+(?:[.,]\d+)?)\s*(?:m²|m2|kv\.?m)',text)
 if not area_match:return None
 a=D(area_match.group(1).replace(',','.'))
 if a<1 or a>100000:return None
 thick=re.search(r'(?:eps|putupolistirol\w*|polistirol\w*|пенополистирол\w*)[^\n]{0,65}?(30|50|100|150|200)\s*mm',text)
 thickness=thick.group(1) if thick else None
 def it(name,kind,unit,qty,basis,spec='',sku=None):
  row={'name':name,'kind':kind,'unit':unit,'quantity':str(qty) if qty is not None else None,'quantity_basis':basis,'specification':spec}
  if sku:row['catalog_sku']=sku
  return row
 items=[it('Fasādes virsmas sagatavošana','labor','m²',a,'Fasādes laukums')]
 items.append(it('EPS 100 siltumizolācijas plāksnes'+(' '+thickness+' mm' if thickness else ' (biezums jāprecizē)'),'material','m²',(a*D('1.05')).quantize(D('.01')),'Platība × 1,05; 5% griešanas rezerve (pieņēmums)','EPS 100, biezums jāapstiprina', 'eps_'+thickness if thickness else None))
 items += [
 it('Siltumizolācijas līmjava','material','kg',(a*D('5')).quantize(D('.01')),'5 kg/m² provizorisks patēriņš; precizēt pēc ražotāja','Sakret BK 25 kg','sakret_bk'),
 it('Fasādes dībeļi','material','gab.',(a*D('6')).to_integral_value(rounding='ROUND_CEILING'),'6 gab./m² provizoriski; nepieciešams stiprinājumu projekts','Garums atkarīgs no pamatnes un EPS biezuma'),
 it('Armējošais stiklašķiedras siets 160 g/m²','material','m²',(a*D('1.10')).quantize(D('.01')),'10% pārlaidumu rezerve (pieņēmums)','Tikai ETICS siets 160 g/m², nevis 70 g/m²'),
 it('Armēšanas java','material','kg',(a*D('5')).quantize(D('.01')),'5 kg/m² provizoriski; precizēt pēc sistēmas','Sakret BAK 25 kg','sakret_bak'),
 it('Grunts pirms dekoratīvā apmetuma','material','kg',(a*D('0.3')).quantize(D('.01')),'0,3 kg/m² provizoriski; ražotāja norma ir jāapstiprina','Sakret PG','sakret_pg'),
 it('Dekoratīvais apmetums 1,5 mm','material','kg',(a*D('2.5')).quantize(D('.01')),'2,5 kg/m² provizoriski; atkarīgs no faktūras','Sakret SMS B 25 kg','sakret_smsb'),
 it('EPS plākšņu līmēšana','labor','m²',a,'Fasādes laukums'),
 it('Fasādes armēšana ar sietu','labor','m²',a,'Fasādes laukums'),
 it('Gruntēšana un dekoratīvā apmetuma uzklāšana','labor','m²',a,'Fasādes laukums')]
 return {'summary':f'ETICS fasādes siltināšanas provizoriska specifikācija: {a} m². Patēriņa normas ir pieņēmumi, nevis projekta aprēķins.','items':items,'assumptions':['5% EPS rezerve, 10% sieta pārlaidums, 5 kg/m² līmjava, 5 kg/m² armēšana, 6 dībeļi/m², 0,3 kg/m² grunts, 2,5 kg/m² apmetums — provizoriski.'],'missing_data':(['EPS biezums nav norādīts; cena netiks automātiski izvēlēta.'] if not thickness else [])+['Jāprecizē fasādes atvērumi, stūri, profili, cokols, ailes, sastatnes, pamatne un ražotāja patēriņa normas.']}

def exact_catalog_matches(item,catalog):
 """Never fuzzy-match technical construction products. Match curated SKU rules only."""
 sku=item.get('catalog_sku')
 if not sku:return []
 rules={
  'eps_100':lambda n:'tenapors eps 100' in n and '100 mm' in n,
  'eps_50':lambda n:'tenapors eps 100' in n and '50 mm' in n,
  'eps_30':lambda n:'tenapors eps 100' in n and '30 mm' in n,
  'sakret_bk':lambda n:'sakret bk ' in n,
  'sakret_bak':lambda n:'sakret bak ' in n,
  'sakret_pg':lambda n:'sakret pg ' in n,
  'sakret_smsb':lambda n:'sakret sms b ' in n,
 }
 rule=rules.get(sku)
 return [r for r in catalog if rule and rule(r['name'].lower()) and r['usage_unit']==item['unit']]

def calculate(description,images):
 obj=facade_spec(description)
 if obj is None:obj,ai=spec_from_ai(description,images)
 else:ai=None
 catalog=verified_catalog(); labor=work_catalog();out=[];sources=[]
 for i,it in enumerate(obj.get('items',[])[:70]):
  kind=it.get('kind','material');name=str(it.get('name',''))[:220];unit=str(it.get('unit','gab.'))[:15]
  try:qty=D(it.get('quantity'));qty=qty if qty>0 else None
  except Exception:qty=None
  record={'id':i+1,'name':name,'kind':kind,'unit':unit,'qty':str(qty) if qty is not None else None,'specification':it.get('specification',''),'quantity_basis':it.get('quantity_basis',''),'price_low':None,'price_mid':None,'price_high':None,'selected_product':None,'status':'NO_VERIFIED_PRICE','offers':[],'line_total':None}
  if kind=='material':
   matches=exact_catalog_matches(it,catalog)
   # Live discovery limited to first 8 material positions; direct pages must carry structured prices.
   if ai is not None and not matches and sum(1 for v in out if v['kind']=='material')<8:
    for url in candidate_urls(ai,name+' '+str(it.get('specification',''))):
     product=extract_product(url,name)
     if product:
      record['offers'].append({**product,'status':'PRICE_OBSERVED_VAT_UNKNOWN','unit':'product listing; pack size unknown'})
   for r in matches:
    pack=parse_money(r.get('pack_quantity'))
    if not pack:continue
    gross=D(r['price_eur']);net=gross/D('1.21') if r['vat_included']=='yes' else gross
    packages=int((qty/pack).to_integral_value(rounding='ROUND_CEILING')) if qty else None
    record['offers'].append({'name':r['name'],'url':r['url'],'gross_or_source_price':money(gross),'net_pack_price':money(net),'pack_quantity':str(pack),'pack_unit':r.get('usage_unit'),'packages':packages,'vat_included':r['vat_included'],'checked_at':r.get('checked_at'),'source':'CURATED_CATALOG','total_net':money(net*packages) if packages else None})
   complete=[o for o in record['offers'] if o.get('total_net')]
   if complete:
    selected=min(complete,key=lambda o:D(o['total_net']))
    record['selected_product']=selected;record['line_total']=selected['total_net'];record['status']='CATALOG_REFERENCE_NOT_LIVE_VERIFIED'
  elif kind=='labor':
   matches=[r for r in labor if r.get('unit')==unit and match(name,r.get('name',''))]
   vals=[]
   for r in matches:
    p=D(r['price_eur']);p=p/D('1.21') if r['vat_included']=='yes' else p
    vals.append(p);record['offers'].append({'url':r['url'],'name':r['name'],'net_unit_price':money(p),'checked_at':r.get('checked_at'),'source':'CURATED_WORK_PRICELIST'})
   if len(vals)>=3:
    vals.sort();record['price_low']=money(vals[max(0,int((len(vals)-1)*.25))]);record['price_mid']=money(statistics.median(vals));record['price_high']=money(vals[min(len(vals)-1,math.ceil((len(vals)-1)*.75))]);record['status']='THREE_LEVELS_FROM_PUBLISHED_OFFERS'
   elif vals:record['status']='INSUFFICIENT_QUOTES_FOR_THREE_LEVELS'
  out.append(record)
 return {'summary':obj.get('summary',''),'items':out,'assumptions':obj.get('assumptions',[]),'missing_data':obj.get('missing_data',[]),'complete':all(x['status'] in ('LIVE_PRODUCT_VERIFIED','THREE_LEVELS_FROM_PUBLISHED_OFFERS') for x in out),'material_catalog_count':len(catalog),'labor_catalog_count':len(labor),'checked_at':datetime.now(timezone.utc).isoformat(),'note':'Catalog prices are historical reference entries, not live-verified. Supplier/category pages are not proof of a specific product price. Never treat a partial estimate as final.'}

def run_job(job_id,description,images):
 try:
  result=calculate(description,images)
  with LOCK:JOBS[job_id].update(status='done',result=result)
 except Exception as e:
  with LOCK:JOBS[job_id].update(status='failed',error=type(e).__name__+': '+str(e)[:250])

@bp.post('/api/v2/estimate-jobs')
def start():
 d=request.get_json(silent=True) or {};description=str(d.get('description','')).strip()
 if not description:return jsonify(error='Apraksts ir obligāts'),400
 if not os.getenv('OPENAI_API_KEY'):return jsonify(error='OPENAI_API_KEY missing'),503
 job_id=uuid.uuid4().hex
 with LOCK:
  if len(JOBS)>100:
   for key in list(JOBS)[:50]:JOBS.pop(key,None)
  JOBS[job_id]={'status':'working','created_at':time.time()}
 POOL.submit(run_job,job_id,description,(d.get('images') or [])[:2]);return jsonify(job_id=job_id,status='working'),202

@bp.get('/api/v2/estimate-jobs/<job_id>')
def poll(job_id):
 with LOCK:job=JOBS.get(job_id)
 if not job:return jsonify(error='Job not found; worker restarted or request expired'),404
 return jsonify(job)

@bp.get('/api/v2/health')
def health():return jsonify(version='2.0-mvp',material_catalog_rows=len(verified_catalog()),labor_catalog_rows=len(work_catalog()),jobs_in_memory=True,live_shop_lookup='jsonld-only',status='online')
