"""CIVINITY live-first research engine. No local price catalogs or invented prices.
Prices are accepted only when retrieved directly from a public source page.
"""
import os, re, json, uuid, time, logging, threading, math
from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import urlparse
from flask import Blueprint, request, jsonify
import requests
from bs4 import BeautifulSoup
from openai import OpenAI

bp=Blueprint('pricing_live',__name__)
LOG=logging.getLogger(__name__)
JOBS={}; LOCK=threading.Lock(); POOL=ThreadPoolExecutor(max_workers=2)
MAX_ITEMS=24; MAX_PAGES=35

SYSTEM='''You are a Latvian building estimator. Produce a TECHNICAL bill of quantities for arbitrary renovation/construction work, no prices. Respond as valid JSON only: {"summary":"...","assumptions":["..."],"items":[{"name":"Latvian product or work name","kind":"material|labor|machine","qty":number or null,"unit":"m2|m|kg|pcs|hour|job|l","spec":"essential technical specifications and standards","search_queries":["Latvian shopping/contractor search query","alternative Latvian search query"]}]}. Include separate material items and work items; no duplicates or material cost included in labor. Quantity must be justified by provided information or null. Never invent dimensions, machine specifications, consumption rates, material thickness, or price. If quantity unknown set null and explain assumption. For materials sold in packs, qty is required physical amount, not guessed number of packages. Up to 18 important items. Write names in Latvian. Search queries should target Latvia and precise product/operation.'''

def client():
    key=os.getenv('OPENAI_API_KEY')
    if not key:raise RuntimeError('OPENAI_API_KEY nav konfigurēta Render vidē')
    return OpenAI(api_key=key,timeout=55,max_retries=0)

def parse_json(s):
    s=s.strip(); a=s.find('{');b=s.rfind('}')
    if a<0 or b<=a:raise ValueError('AI neatgrieza derīgu JSON')
    return json.loads(s[a:b+1])

def create_spec(desc):
    r=client().chat.completions.create(model=os.getenv('LIVE_SPEC_MODEL','gpt-4.1-mini'),temperature=0,response_format={'type':'json_object'},messages=[{'role':'system','content':SYSTEM},{'role':'user','content':desc[:7000]}])
    obj=parse_json(r.choices[0].message.content)
    items=[]
    for it in obj.get('items',[])[:MAX_ITEMS]:
        if not isinstance(it,dict):continue
        kind=it.get('kind');qty=it.get('qty')
        if kind not in ('labor','material','machine'):continue
        try:qty=float(qty) if qty is not None else None
        except (TypeError,ValueError):qty=None
        if qty is not None and (qty<=0 or qty>10000000):qty=None
        items.append({'id':str(len(items)+1),'name':str(it.get('name') or '')[:180], 'kind':kind,'qty':qty,'unit':str(it.get('unit') or '')[:30], 'spec':str(it.get('spec') or '')[:500], 'queries':[str(q)[:180] for q in (it.get('search_queries') or [])[:2]],'offers':[],'status':'searching','price_low':None,'price_mid':None,'price_high':None,'line_total':None})
    return {'summary':obj.get('summary',''),'assumptions':obj.get('assumptions',[]),'items':items}

def discover(items):
    """Search online afresh per request, without a pre-populated product catalog."""
    tasks=[{'id':i['id'],'name':i['name'],'kind':i['kind'],'spec':i['spec'],'queries':i['queries']} for i in items]
    prompt=('Find live public Latvia supplier PRODUCT PAGES for material items and published contractor WORK PRICE LIST pages for labor items. '
            'Search the web now, using the queries. Return ONLY JSON {"results":[{"id":"item id","pages":[{"url":"https://...","reason":"brief match reason"}]}]}. '
            'Prefer specific product pages rather than category/search pages. For work prices use actual contractor published price lists. '
            'No fabricated URLs, prices, or offers. Max 3 distinct pages per item, max 30 pages overall. Do NOT provide any prices; independent page reader will extract them. '
            'Today '+datetime.now(timezone.utc).date().isoformat()+'; ITEMS: '+json.dumps(tasks,ensure_ascii=False)[:15000])
    r=client().responses.create(model=os.getenv('LIVE_SEARCH_MODEL','gpt-4.1-mini'),tools=[{'type':'web_search_preview','search_context_size':'medium'}],input=prompt,timeout=75)
    data=parse_json(r.output_text)
    mapping={str(i['id']):[] for i in items}
    count=0
    for record in data.get('results',[]):
        iid=str(record.get('id'))
        if iid not in mapping:continue
        for p in record.get('pages',[])[:3]:
            url=str(p.get('url') or '')
            if url.startswith('https://') and len(url)<600 and url not in mapping[iid] and count<MAX_PAGES:
                mapping[iid].append(url);count+=1
    return mapping

def nodes(o):
    if isinstance(o,list):
        for v in o:yield from nodes(v)
    elif isinstance(o,dict):
        yield o
        if '@graph' in o:yield from nodes(o['@graph'])

def money(v):
    try:
        if isinstance(v,str):v=v.replace('\u00a0','').replace(' ','').replace(',','.')
        d=Decimal(str(v))
        return d if d.is_finite() and Decimal('0.01')<=d<=Decimal('1000000') else None
    except Exception:return None

def safe_url(url):
    """Public HTTPS only; basic SSRF safeguards incl DNS resolution."""
    import socket, ipaddress
    u=urlparse(url)
    if u.scheme!='https' or not u.hostname or u.username or u.password or u.port not in (None,443):return False
    if u.hostname.lower() in ('localhost',) or '.' not in u.hostname:return False
    try:
        addrs=socket.getaddrinfo(u.hostname,443,type=socket.SOCK_STREAM)
        return bool(addrs) and all(ipaddress.ip_address(x[4][0]).is_global for x in addrs)
    except Exception:return False

def fetch_page(url):
    if not safe_url(url):return None,'URL drošības pārbaude neizdevās'
    try:
        r=requests.get(url,timeout=(4,9),headers={'User-Agent':'Mozilla/5.0 (compatible; CivinityPriceResearch/3.0)'},allow_redirects=False)
        if r.status_code in (301,302,303,307,308):return None,'Lapa pāradresē (nav automātiski pārbaudīta)'
        if r.status_code!=200:return None,'HTTP '+str(r.status_code)
        if 'html' not in r.headers.get('Content-Type','').lower():return None,'Nav HTML lapa'
        if len(r.content)>1600000:return None,'Lapa pārāk liela'
        return BeautifulSoup(r.text,'html.parser'),None
    except Exception as e:return None,type(e).__name__

def tokens(s):
    return set(re.findall(r'[a-zāčēģīķļņšūž0-9]{3,}',(s or '').lower()))

def compatible(item,product_name):
    a=tokens(item['name']+' '+item['spec']);b=tokens(product_name)
    # Check critical dimensions when explicitly specified in query.
    for mm in re.findall(r'\b(\d{2,3})\s*mm\b',(item['name']+' '+item['spec']).lower()):
        if re.search(r'\b\d{2,3}\s*mm\b',product_name.lower()) and not re.search(r'\b'+re.escape(mm)+r'\s*mm\b',product_name.lower()):return False
    return len(a&b)>=2 or (len(a)<=2 and len(a&b)>=1)

def parse_product(soup,item,url):
    offers=[]
    for sc in soup.select('script[type="application/ld+json"]'):
        try:root=json.loads(sc.string or sc.get_text())
        except Exception:continue
        for obj in nodes(root):
            typ=obj.get('@type',[]);typ=[typ] if isinstance(typ,str) else typ
            if not any(str(t).lower().endswith('product') for t in typ):continue
            name=str(obj.get('name') or '')
            if not compatible(item,name):continue
            os_=obj.get('offers') or []
            if isinstance(os_,dict):os_=[os_]
            for o in os_:
                if not isinstance(o,dict):continue
                p=money(o.get('price') or o.get('lowPrice'))
                cur=str(o.get('priceCurrency') or '').upper()
                if p is None or cur!='EUR':continue
                offers.append({'url':url,'name':name,'price_eur':str(p),'currency':'EUR','kind':'product','verified':'page_jsonld','vat':'unknown','unit':'sale_unit_unknown','observed_at':datetime.now(timezone.utc).isoformat(timespec='seconds'),'warning':'Iepakojuma apjoms un PVN nav neatkarīgi apstiprināti; nevar aprēķināt pozīcijas kopsummu.'})
    return offers[:3]

def parse_labor(soup,item,url):
    """Do not convert arbitrary text prices into verified unit rates.
    Candidate lines are shown to the user for review, not automatically priced.
    """
    for s in soup(['script','style','nav','footer']):s.decompose()
    text=soup.get_text(' ',strip=True)
    q=tokens(item['name']);words=list(q)[:5]
    snippets=[]
    for match in re.finditer(r'\b\d{1,5}(?:[,.]\d{1,2})?\s*(?:€|EUR)\b',text,re.I):
        seg=text[max(0,match.start()-130):match.end()+70]
        if len(tokens(seg)&q)>=2:snippets.append(seg[:230])
        if len(snippets)>=2:break
    return [{'url':url,'name':item['name'],'kind':'labor_candidate','verified':'page_text_candidate','snippet':s,'warning':'Nepieciešams pārbaudīt darba apjomu un mērvienību; cena netiek automātiski piemērota.'} for s in snippets]

def research_one(item,urls):
    offers=[];errors=[]
    for url in urls[:3]:
        soup,err=fetch_page(url)
        if err:errors.append({'url':url,'reason':err});continue
        found=parse_product(soup,item,url) if item['kind']=='material' else parse_labor(soup,item,url)
        if found:offers.extend(found)
        else:errors.append({'url':url,'reason':'Nav atbilstošas pārbaudāmas cenas lapā'})
    item['offers']=offers;item['page_errors']=errors
    item['status']='source_found_needs_unit_vat' if any(o['kind']=='product' for o in offers) else ('candidate_requires_review' if offers else 'no_verified_price')
    # NEVER silently infer package volume, VAT, or price per unit from the web page.
    return item

def run(job_id,description):
    try:
        def step(status,progress,**kwargs):
            with LOCK:JOBS[job_id].update(status=status,progress=progress,**kwargs)
        step('specification',8)
        spec=create_spec(description)
        step('web_search',25,summary=spec['summary'],assumptions=spec['assumptions'],items=spec['items'])
        try:links=discover(spec['items'])
        except Exception as e:
            LOG.exception('Live web search failed');links={i['id']:[] for i in spec['items']}
            step('page_verification',50,search_error=str(e)[:300])
        else:step('page_verification',50)
        items=spec['items'];total=max(1,len(items))
        with ThreadPoolExecutor(max_workers=5) as ex:
            futures={ex.submit(research_one,item,links.get(item['id'],[])):item for item in items}
            for n,f in enumerate(as_completed(futures),1):
                try:f.result()
                except Exception:LOG.exception('Page verification error')
                step('page_verification',50+int(45*n/total),items=items)
        step('done',100,items=items,complete=False,verified_count=sum(bool(i['offers']) for i in items),missing_count=sum(not bool(i['offers']) for i in items))
    except Exception as e:
        LOG.exception('Live estimate job failed')
        with LOCK:JOBS[job_id].update(status='failed',error=str(e)[:400],progress=100)

@bp.post('/api/v3/estimate-jobs')
def start():
    data=request.get_json(silent=True) or {}
    description=str(data.get('description') or '').strip()
    if len(description)<8:return jsonify(error='Apraksts ir pārāk īss'),400
    if len(description)>10000:return jsonify(error='Apraksts ir pārāk garš'),400
    job_id=uuid.uuid4().hex
    with LOCK:
        now=time.time()
        for key in list(JOBS):
            if now-JOBS[key]['created']>7200:JOBS.pop(key,None)
        if sum(j['status'] not in ('done','failed') for j in JOBS.values())>=2:return jsonify(error='Divi aprēķini jau tiek veikti; mēģiniet vēlāk'),429
        JOBS[job_id]={'created':now,'status':'queued','progress':0,'items':[]}
    POOL.submit(run,job_id,description)
    return jsonify(job_id=job_id,status='queued'),202

@bp.get('/api/v3/estimate-jobs/<job_id>')
def status(job_id):
    with LOCK:
        j=JOBS.get(job_id)
        if not j:return jsonify(error='Uzdevums nav atrasts vai serveris pārstartēts'),404
        return jsonify({k:v for k,v in j.items() if k!='created'})

@bp.get('/api/v3/health')
def health():return jsonify(version='3.0',mode='live_online_only',catalog_required=False,search='OpenAI web_search_preview',validation='HTTPS source page / schema.org Product offers',labor_auto_pricing=False,price_totals_require_pack_vat=True)
