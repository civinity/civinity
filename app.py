import base64
import io
import json
import logging
import statistics
import re
from urllib.parse import urlsplit
from urllib.parse import urlparse
import os
from datetime import datetime
from xml.sax.saxutils import escape
from flask import Flask, jsonify, request, send_file
from flask_cors import CORS
from openai import OpenAI

app = Flask(__name__)
from pricing_v2 import bp as pricing_v2_bp
app.register_blueprint(pricing_v2_bp)
app.config['MAX_CONTENT_LENGTH'] = 18 * 1024 * 1024
CORS(app, resources={r'/api/*': {'origins': os.getenv('FRONTEND_URL', 'https://civiniai.onrender.com')}})

@app.get('/')
def home():
    return jsonify(status='online', service='CIVINITY AI BuvTame API', version='18.0')

# Web price evidence is researched for each estimate. Never label model guesses as verified.
PRICE_SITES = ['baufonds.lv','kalkulatori.meistarpro.lv','getapro.lv','kursi.lv','ksenukai.lv','online.depo.lv','buvserviss.lv','remontaizmaksas.lv']

def research_prices(client, description):
    today=datetime.now().strftime('%Y-%m-%d')
    prompt=("Find CURRENT PUBLIC Latvia market prices for the specific renovation works and required construction materials below. "
            "Search Latvian contractors' published work price lists and Latvian building stores. "
            "Prefer baufonds.lv, kalkulatori.meistarpro.lv, getapro.lv, kursi.lv, ksenukai.lv, online.depo.lv, buvserviss.lv; other credible Latvia suppliers permitted. "
            "Work prices and product prices MUST be kept separate. Product bundles must not double count included components. "
            "Return ONLY JSON with sources array: [{title, url, item, category:'labor' or 'material' or 'machine', unit, price_eur, "
            "price_min_eur, price_max_eur, includes_vat: true/false/null, observed_date:'YYYY-MM-DD or unknown', notes}]. "
            "Use exact URL for a publicly discoverable page. NEVER invent prices, URLs, dates, VAT treatment, or products. "
            "If only range available leave price_eur null. If unverified, OMIT it. Max 35 sources. Include at least two independently published offers per major work/material where possible. "
            "Today: "+today+". Job: "+description[:2800])
    try:
        result=client.with_options(max_retries=0).responses.create(model=os.getenv('PRICE_RESEARCH_MODEL','gpt-4.1-mini'),tools=[{'type':'web_search_preview','search_context_size':'medium'}],input=prompt,timeout=20)
        raw=result.output_text.strip();start=raw.find('{');end=raw.rfind('}')
        obj=json.loads(raw[start:end+1]) if start>=0 and end>start else {}
        sources=[]
        for x in (obj.get('sources') or [])[:35]:
            if not isinstance(x,dict):continue
            url=str(x.get('url') or '').strip()
            if not url.startswith('https://') or len(url)>700:continue
            domain=urlparse(url).hostname or ''
            if domain in ('example.com','www.example.com','localhost') or '.' not in domain:continue
            def price(k):
                try:
                    v=float(x.get(k))
                    return round(v,4) if 0 < v < 10000000 else None
                except (TypeError,ValueError):return None
            item={k:x.get(k) for k in ('title','url','item','category','unit','includes_vat','observed_date','notes')}
            item.update({k:price(k) for k in ('price_eur','price_min_eur','price_max_eur')})
            if item['price_eur'] is None and item['price_min_eur'] is None and item['price_max_eur'] is None:continue
            item['id']='S'+str(len(sources)+1)
            item['verification']='AI web-search extracted; original page not independently validated'
            sources.append(item)
        return sources
    except Exception:
        app.logger.exception('Market price research unavailable')
        return []

# Supplier pages are checked independently from AI output. Only Product offers
# with machine-readable, on-page price data are accepted as shop prices.
SHOP_HOSTS = ('depo.lv', 'kurshi.lv', 'ksenukai.lv', 'buvserviss.lv', 'bauhof.lv', 'prof.lv', 'buvniecibas-abc.lv', 'online.depo.lv')

def _shop_host(url):
    try:
        u=urlsplit(url)
        host=(u.hostname or '').lower()
        return u.scheme=='https' and any(host==h or host.endswith('.'+h) for h in SHOP_HOSTS)
    except Exception:return False

def _jsonld_nodes(value):
    if isinstance(value,list):
        for x in value:yield from _jsonld_nodes(x)
    elif isinstance(value,dict):
        yield value
        if '@graph' in value:yield from _jsonld_nodes(value['@graph'])

def _numeric_price(value):
    if isinstance(value,str):value=value.replace(' ', '').replace('\u00a0','').replace(',','.')
    try:
        x=float(value)
        return round(x,2) if 0<x<1000000 else None
    except (ValueError,TypeError):return None

def verify_shop_prices(sources):
    import requests
    from bs4 import BeautifulSoup
    session=requests.Session()
    session.headers.update({'User-Agent':'Mozilla/5.0 (compatible; CivinityEstimate/1.0; price-evidence-check)'})
    checked=0
    for x in sources:
        x['verification']='not_independently_verified'
        x['shop_verified']=False
        if x.get('category')!='material' or not _shop_host(str(x.get('url') or '')):continue
        if checked>=4:break
        checked+=1
        try:
            response=session.get(x['url'],timeout=2,allow_redirects=True)
            if response.status_code!=200 or len(response.content)>3_000_000 or not _shop_host(response.url):continue
            soup=BeautifulSoup(response.text,'html.parser')
            products=[]
            for script in soup.select('script[type="application/ld+json"]'):
                try:
                    for node in _jsonld_nodes(json.loads(script.string or script.get_text())):
                        typ=node.get('@type',[])
                        if isinstance(typ,str):typ=[typ]
                        if 'Product' in typ:products.append(node)
                except (ValueError,TypeError):pass
            expected=str(x.get('item') or '').lower()
            expected_words={w for w in re.findall(r'[\wāčēģīķļņšūž]{4,}',expected) if not w.isdigit()}
            for product in products:
                title=str(product.get('name') or '').lower()
                overlap=len(expected_words & set(re.findall(r'[\wāčēģīķļņšūž]{4,}',title)))
                if expected_words and overlap<max(1,min(2,len(expected_words))):continue
                offers=product.get('offers') or []
                if isinstance(offers,dict):offers=[offers]
                for offer in offers:
                    if not isinstance(offer,dict):continue
                    price=_numeric_price(offer.get('price'))
                    currency=str(offer.get('priceCurrency') or '').upper()
                    if price is None or currency!='EUR':continue
                    x['price_eur']=price
                    x['price_min_eur']=None
                    x['price_max_eur']=None
                    x['includes_vat']=None  # VAT not inferable from JSON-LD
                    x['verification']='shop_page_jsonld_product_price'
                    x['shop_verified']=True
                    x['verified_product_name']=str(product.get('name') or '')[:220]
                    x['verified_url']=response.url
                    break
                if x['shop_verified']:break
        except (requests.RequestException,ValueError,TypeError,UnicodeError):pass
    return sources

def apply_evidence_prices(rows, sources, level):
    """Use published evidence only when product/work and units match.
    A missing price is explicit; never turn an unknown into a fictitious price.
    """
    from decimal import Decimal, ROUND_HALF_UP
    by_id={str(x.get('id')):x for x in sources}
    rank={'low':0,'mid':1,'high':2}.get(level,1)
    def tokens(value):
        return set(re.findall(r'[a-zāčēģīķļņšūž]{4,}',str(value or '').lower()))
    def matching(row,x,kind):
        if x.get('category')!=kind:return False
        if str(x.get('unit') or '').strip().lower()!=str(row.get('unit') or '').strip().lower():return False
        a=tokens(row.get('name'));b=tokens(x.get('verified_product_name') or x.get('item'))
        return bool(a and b and len(a & b)>=min(2,len(a),len(b)))
    report=[]
    for row in rows:
        ids=row.pop('source_ids',[])
        if not isinstance(ids,list):ids=[]
        used=[];missing=[]
        # Preserve AI draft only for labor, explicitly tagged as NOT verified.
        # Material and machinery require a published product/rental price.
        for field,kind in [('labor','labor'),('material','material'),('machine','machine')]:
            offers=[]
            for x in sources:
                if not matching(row,x,kind):continue
                if kind=='material' and not x.get('shop_verified'):continue
                price=x.get('price_eur')
                if not isinstance(price,(float,int)) or price<=0:continue
                vat=x.get('includes_vat')
                # Latvian retail product pages normally show consumer gross prices.
                # If VAT isn't explicitly known, retain gross source value and mark
                # the net conversion as an ASSUMPTION, not a verified net price.
                if kind=='material' and vat is None:
                    net=Decimal(str(price))/Decimal('1.21')
                    status='SHOP_GROSS_VAT_ASSUMED_21_PERCENT'
                elif vat is True:
                    net=Decimal(str(price))/Decimal('1.21')
                    status='SOURCE_VAT_INCLUDED'
                else:
                    net=Decimal(str(price))
                    status='SOURCE_VAT_EXCLUDED' if vat is False else 'VAT_NOT_SPECIFIED'
                offers.append((net,str(x['id']),status))
            if offers:
                offers.sort(key=lambda o:o[0]);chosen=offers[0] if rank==0 else offers[-1] if rank==2 else offers[len(offers)//2]
                row[field]=float(chosen[0].quantize(Decimal('0.01'),rounding=ROUND_HALF_UP))
                used.append(chosen[1]);row[field+'_price_status']=chosen[2]
            elif kind=='material':
                # Missing prices stay missing; UI and exports must show this status.
                if row.get('material',0)>0 or str(row.get('category','')).lower() in ('materiali','materiāli','material') or any(word in tokens(row.get('name')) for word in ('plāksnes','stiprinājumi','līmes','krāsa','materiāls','putuplasta','komplekts')):
                    row['material']=0.0;row['material_price_status']='MISSING_SHOP_PRICE';missing.append('materiāli')
            elif kind=='labor' and row.get('labor',0)>0:
                row['labor_price_status']='AI_PROVISIONAL_NOT_MARKET_VERIFIED';missing.append('darbu cenas')
            elif kind=='machine' and row.get('machine',0)>0:
                row['machine_price_status']='AI_PROVISIONAL_NOT_MARKET_VERIFIED';missing.append('mehānismi')
        row['evidence_ids']=used
        row['pricing_status']='incomplete' if missing else ('source_backed' if used else 'no_price_evidence')
        row['material_price_note']='NAV VEIKALA CENAS — summa nav pilnīga' if 'materiāli' in missing else ''
        report.append({'name':row['name'],'status':row['pricing_status'],'missing':missing,'sources':used})
    return report

@app.get('/api/pricing-health')
def pricing_health():
    return jsonify(status='online',mode='source_evidence_only',note='No price is called verified without product page + VAT and unit checks.',version='18.0')

@app.post('/api/estimate')
def estimate():
    data = request.get_json(silent=True)
    if not isinstance(data, dict) or not str(data.get('description', '')).strip():
        return jsonify(error='Ievadiet darba aprakstu.'), 400
    key = os.getenv('OPENAI_API_KEY')
    if not key:
        return jsonify(error='OPENAI_API_KEY nav konfigurēts Render Environment.'), 503
    description = str(data['description'])[:12000]
    price_level = str(data.get('price_level','mid'))
    price_hint = {'low':'ekonomiskā līmeņa','mid':'Latvijas vidējā tirgus līmeņa','high':'augstākā cenu līmeņa'}.get(price_level,'Latvijas vidējā tirgus līmeņa')
    description += '\nIzvēlētais cenu segments: '+price_hint+'. Norādi cenu pieņēmumus un nenosauc tās par reāllaikā pārbaudītām.'
    images = data.get('images') or []
    if not isinstance(images, list):
        images = []
    content = [{'type':'text', 'text':description}]
    for img in images[:3]:
        if isinstance(img, str) and img.startswith(('data:image/jpeg;base64,', 'data:image/png;base64,', 'data:image/webp;base64,')) and len(img)<6_000_000:
            content.append({'type':'image_url', 'image_url':{'url':img, 'detail':'low'}})
    instructions = 'Tu esi Latvijas būvdarbu tāmētājs un cenu datu analītiķis. Sagatavo detalizētu, pārbaudāmu būvdarbu tāmi latviešu valodā. Atgriez tikai JSON.\n\nOBLIGĀTĀS PRASĪBAS:\n1. NODALI DARBUS, MATERIĀLUS UN MEHĀNISMUS. Katrai pozīcijai norādi nosaukumu, mērvienību, daudzumu, darba vienības cenu (labor), materiāla vienības cenu (material), mehānisma vienības cenu (machine), avotu ID un kategoriju. Vienu izmaksu nedrīkst ieskaitīt divreiz. Neizdomā apjomus; nezināmo atzīmē assumptions/missing_data.\n2. MATERIĀLI: izmanto tikai KONKRĒTU Latvijas veikala preces lapu (piem., DEPO, K Senukai, Būvserviss vai cits Latvijas tirgotājs), kur pieejama preces identitāte, iepakojums, mērvienība, publicētā cena un tiešā saite. Saglabā precīzu publicēto cenu ar centiem (2,37 EUR ir 2,37, nevis 2,00 vai 2,50). NEDRĪKST izdomāt centus, cenas, SKU, saites vai pieejamību. Pārbaudi vienības atbilstību: gab./iepakojums/m²/m³/kg/l/m; ja vajag, aprēķini pārrēķinu no pārbaudīta iepakojuma izmēra. Nepieciešamo daudzumu aprēķini pēc tehniskā patēriņa normas un atsevišķi norādi rezervi. Ja preces cenu nevar pārbaudīt, materiāla pozīciju SAGLABĀ, norādi cenu 0 TIKAI kā nezināmas cenas tehnisko vietturi un skaidru statusu \'cena nav pārbaudīta\'; tas NAV apgalvojums, ka materiāls ir bezmaksas.\n3. PVN: fiksē, vai veikala cena ir ar 21% PVN. Ja cena ir ar PVN, dalīšana ar 1,21 ir matemātisks pārrēķins, nevis jauna veikala cena; saglabā oriģinālo cenu un PVN statusu cenu avotu pielikumā. Ja PVN statuss nav zināms, NEPIEŅEM to automātiski un nepiešķir cenai statusu \'pārbaudīta cena bez PVN\'. Gala tāme ir bez PVN, PVN atsevišķi 21%.\n4. DARBU CENAS: meklē publiski pieejamus Latvijas būvniecības un remontdarbu pakalpojumu cenrāžus. Vienādo darba saturu, mērvienības, reģionu un PVN. Trīs izvēles: low = salīdzināmu zemāko publicēto piedāvājumu segments, mid = salīdzināmu piedāvājumu mediāna, high = salīdzināmu augstāko publicēto piedāvājumu segments. Nedrīkst izmantot fiksētus procentu koeficientus vai izdomāt tirgus sadalījumu. Ja ir tikai viens publicēts piedāvājums, NEUZDOD to par statistisku mediānu vai trīs neatkarīgiem līmeņiem. Ja datu nepietiek, atzīmē cenu kā provizorisku un paskaidro metodoloģiju. Saglabā avotā esošos centus; darba izmaksu aprēķinam norādi stundas un likmes, ja tās ir zināmas.\n5. IZMANTO TIKAI DATU AVOTUS no pievienotā PĀRBAUDĀMIE CENU AVOTI saraksta. \'source_ids\' drīkst norādīt tikai precīzai preces/darba un mērvienības sakritībai. Neuzdod AI meklēšanas fragmentu par neatkarīgi verificētu veikala cenu. Nekad neizdomā trūkstošās cenas, datumus vai avotus.\n6. Ja ir foto, atšķir redzamo no pieņēmumiem. Nenovērtē precīzus izmērus no attēla. Sagatavo atsevišķu apsekošanas akta PROJEKTU, neapgalvo, ka apsekošana jau veikta.\n7. Detalizē katru būvprocesu un katru materiālu atsevišķi, ieskaitot stiprinājumus, palīgmateriālus, demontāžu, montāžu, atkritumus, transportu tikai tad, ja tas ir attiecināms. Neizdomā vajadzību pēc darbiem.\n8. Nekad neapaļo cenu līdz veseliem eiro, desmitiem vai simtiem, ja avotā ir precīzi centi. Neģenerē nejaušus centus ticamības imitācijai. Arī reizinājumu un PVN aprēķinu veic programma.\n\nJSON SHĒMA: {"summary":"...", "rows":[{"name":"...", "unit":"gab.", "qty":1, "labor":0, "material":0, "machine":0, "category":"darbi vai materiali vai mehanismi", "source_ids":[]}], "act":{"observations":"...", "defects":"...", "recommendations":"...", "limitations":"..."}, "assumptions":["..."], "missing_data":["..."]}.\n'
    try:
        client = OpenAI(api_key=key, timeout=48, max_retries=0)
        sources=verify_shop_prices(research_prices(client,description))
        evidence=json.dumps(sources,ensure_ascii=False)[:18000]
        content[0]['text'] += '\nPĀRBAUDĀMIE CENU AVOTI (no tīmekļa meklēšanas): '+evidence+'\nJa avotu nav vai tie nav pietiekami, cenas atzīmē kā NEPĀRBAUDĪTAS un neapgalvo, ka tās ir tirgus vidējās.'
        res = client.chat.completions.create(model=os.getenv('OPENAI_MODEL', 'gpt-4.1-mini'), messages=[{'role':'system','content':instructions},{'role':'user','content':content}], response_format={'type':'json_object'},temperature=0.15, max_tokens=6500)
        obj = json.loads(res.choices[0].message.content)
        if not isinstance(obj.get('rows'), list) or not isinstance(obj.get('act'), dict):
            raise ValueError('AI returned unexpected structure')
        rows=[]
        for r in obj['rows'][:100]:
            if not isinstance(r, dict): continue
            def num(k):
                try:return max(0,min(float(r.get(k) or 0),1e8))
                except (ValueError,TypeError):return 0
            rows.append(dict(name=str(r.get('name') or '')[:300],unit=str(r.get('unit') or 'gab.')[:20],qty=num('qty'),labor=num('labor'),material=num('material'),machine=num('machine'),category=str(r.get('category') or 'darbi')[:30],source_ids=r.get('source_ids') or []))
        # Keep estimate requests below hosting proxy timeout. A second synchronous
        # AI web search previously caused browser "Failed to fetch" errors.
        # Unverified material prices remain visibly provisional, never "shop verified".
        pricing_report=apply_evidence_prices(rows,sources,price_level)
        if any(r.get('material_price_note') for r in rows):
            obj.setdefault('missing_data',[]).append('UZMANĪBU: materiālu cenas nav pilnībā pārbaudītas; kopsumma ir nepilnīga un nav izmantojama kā galīgais piedāvājums.')
        return jsonify(estimate_complete=not any(r.get('pricing_status')=='incomplete' for r in rows),pricing_report=pricing_report,material_prices_missing=sum(1 for r in rows if r.get('material_price_note')),success=True,estimate=obj.get('summary',''),rows=rows,act=obj['act'],assumptions=obj.get('assumptions',[]),missing_data=obj.get('missing_data',[]),price_sources=sources,price_verified=False,price_research_status="source_only_with_explicit_missing_prices",price_checked_at=datetime.now().isoformat(timespec='seconds'),price_level=price_level)
    except Exception as exc:
        app.logger.exception('AI estimate failed')
        kind=type(exc).__name__
        return jsonify(error='AI tāmes izveide neizdevās ('+kind+'). Pārbaudiet Render Logs.', error_type=kind),502

# Export actual styled Excel and PDF, not a CSV renamed to .xlsx.
def safe(v):return str(v or '').strip()
def num(v):
    try:return max(0,float(v or 0))
    except (ValueError,TypeError):return 0

def logo_bytes(company):
    raw=safe(company.get('logo'))
    if raw.startswith(('data:image/png;base64,','data:image/jpeg;base64,')):
        try:return base64.b64decode(raw.split(',',1)[1])
        except Exception:return None
    return None

def workbook(payload):
    from openpyxl import Workbook
    from openpyxl.styles import Font,PatternFill,Alignment,Border,Side
    from openpyxl.utils import get_column_letter
    from openpyxl.drawing.image import Image
    wb=Workbook();ws=wb.active;ws.title='Tāme';co=payload['company'];obj=payload['object'];rows=payload['rows']
    navy='0C3153';blue='08699B';pale='EAF2F8';white='FFFFFF';gray='D3DFE8'
    ws.merge_cells('A1:H2');ws['A1']=safe(co.get('name'))+'  |  BŪVDARBU TĀME';ws['A1'].font=Font(size=18,bold=True,color=white);ws['A1'].fill=PatternFill('solid',fgColor=navy);ws['A1'].alignment=Alignment(vertical='center');ws.row_dimensions[1].height=29
    ws.merge_cells('A4:H4');ws['A4']='Objekts: '+safe(obj.get('name'))+'  •  '+safe(obj.get('address'));ws['A4'].font=Font(bold=True,color=navy,size=12)
    ws.merge_cells('A5:H5');ws['A5']='Izpildītājs: '+safe(co.get('name'))+'  |  '+safe(co.get('reg'))+'  |  '+safe(co.get('address'))
    ws.merge_cells('A6:H6');ws['A6']='Banka: '+safe(co.get('bank'))+'  |  '+safe(co.get('iban'))
    headers=['Nr.','Darba / materiāla nosaukums','Mērv.','Daudz.','Darbi EUR/v.','Materiāli EUR/v.','Mehānismi EUR/v.','Summa EUR']
    for j,v in enumerate(headers,1):
        c=ws.cell(8,j,v);c.fill=PatternFill('solid',fgColor=blue);c.font=Font(color=white,bold=True);c.alignment=Alignment(wrap_text=True,vertical='center');c.border=Border(bottom=Side(style='thin',color=gray))
    ws.row_dimensions[8].height=35
    for i,r in enumerate(rows,9):
        vals=[i-8,safe(r.get('name')),safe(r.get('unit')),num(r.get('qty')),num(r.get('labor')),num(r.get('material')),num(r.get('machine')),f'=D{i}*(E{i}+F{i}+G{i})']
        for j,v in enumerate(vals,1):
            c=ws.cell(i,j,v);c.fill=PatternFill('solid',fgColor='FFFFFF' if i%2 else pale);c.border=Border(bottom=Side(style='hair',color=gray));c.alignment=Alignment(vertical='top',wrap_text=j==2)
            if j>=4:c.number_format='#,##0.00'
        ws.row_dimensions[i].height=29
    end=8+len(rows);start=end+2
    for row,label,formula in [(start,'Kopā bez PVN',f'=SUM(H9:H{end})'),(start+1,'PVN 21%',f'=H{start}*21%'),(start+2,'PAVISAM KOPĀ',f'=H{start}+H{start+1}')]:
        ws.cell(row,7,label);ws.cell(row,8,formula);ws.cell(row,7).font=Font(bold=True,color=navy);ws.cell(row,8).font=Font(bold=True,color=navy);ws.cell(row,8).number_format='#,##0.00 "EUR"'
    ws.merge_cells(start_row=start+5,start_column=1,end_row=start+5,end_column=8);ws.cell(start+5,1,'Provizoriska tāme. Cenas un apjomi jāprecizē pirms apstiprināšanas.');ws.cell(start+5,1).font=Font(italic=True,color='64748B')
    for j,w in enumerate([7,62,11,12,17,19,19,19],1):ws.column_dimensions[get_column_letter(j)].width=w
    ws.freeze_panes='C9';ws.sheet_properties.pageSetUpPr.fitToPage=True;ws.page_setup.fitToWidth=1;ws.print_options.horizontalCentered=True
    logo=logo_bytes(co)
    if logo:
        try:
            im=Image(io.BytesIO(logo));im.width=120;im.height=45;ws.add_image(im,'F3')
        except Exception:pass
    evidence=wb.create_sheet('Cenu pamatojums')
    evidence.append(['CENU PAMATOJUMS — PIELIKUMS (nav tāmes pamatdaļa)'])
    evidence.append(['Pārbaudes datums',safe(payload.get('price_checked_at'))])
    evidence.append(['Cenu līmenis',safe(payload.get('price_level') or 'mid')])
    evidence.append(['Piezīme','Tīmekļa meklēšanas AI iegūti dati, nevis neatkarīgi pārbaudītas cenas. Avotu cenu, PVN un komplektāciju apstiprināt manuāli.'])
    evidence.append(['Nr.','Pozīcija','Veids','Avots','Cena EUR','No EUR','Līdz EUR','PVN iekļauts?','Datums','Saite','Piezīmes'])
    for i,x in enumerate(payload.get('price_sources') or [],1):
        if not isinstance(x,dict):continue
        evidence.append([i,safe(x.get('item')),safe(x.get('category')),safe(x.get('title')),x.get('price_eur'),x.get('price_min_eur'),x.get('price_max_eur'),str(x.get('includes_vat')),safe(x.get('observed_date')),safe(x.get('url')),safe(x.get('notes'))])
        c=evidence.cell(evidence.max_row,10)
        if safe(x.get('url')).startswith('https://'):c.hyperlink=safe(x.get('url'));c.style='Hyperlink'
    evidence.append(['Tāmes pozīcijas un to avotu piesaiste'])
    evidence.append(['Pozīcija','Statuss','Izmantoto avotu ID'])
    for r in rows:evidence.append([safe(r.get('name')),safe(r.get('pricing_status') or 'AI_estimate_unverified'),', '.join(r.get('evidence_ids') or [])])
    if not payload.get('price_sources'):evidence.append(['Nav pārbaudītu tīmekļa cenu avotu. AI norādītās cenas ir tikai provizoriskas.'])
    for col,w in {'A':9,'B':43,'C':15,'D':29,'E':16,'F':16,'G':16,'H':18,'I':17,'J':65,'K':60}.items():evidence.column_dimensions[col].width=w
    for cell in evidence[5]:cell.fill=PatternFill('solid',fgColor=navy);cell.font=Font(color=white,bold=True)
    evidence.freeze_panes='B6';evidence.sheet_view.showGridLines=False
    output=io.BytesIO();wb.save(output);output.seek(0);return output

def pdf(payload):
    from reportlab.platypus import SimpleDocTemplate,Paragraph,Table,TableStyle,Spacer,Image,KeepTogether
    from reportlab.lib import colors
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib.enums import TA_CENTER,TA_RIGHT
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    from reportlab.lib.utils import ImageReader
    from PIL import Image as PILImage
    font='/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf';bold='/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf'
    if 'DejaVu' not in pdfmetrics.getRegisteredFontNames():pdfmetrics.registerFont(TTFont('DejaVu',font));pdfmetrics.registerFont(TTFont('DejaVu-Bold',bold))
    co=payload['company'];obj=payload['object'];kind=payload['kind'];rows=payload['rows'];output=io.BytesIO()
    doc=SimpleDocTemplate(output,pagesize=A4,rightMargin=32,leftMargin=32,topMargin=34,bottomMargin=34)
    st=ParagraphStyle('body',fontName='DejaVu',fontSize=8,leading=12,spaceAfter=7)
    sm=ParagraphStyle('small',parent=st,fontSize=7,leading=10)
    title=ParagraphStyle('title',parent=st,fontName='DejaVu-Bold',fontSize=16,leading=21,alignment=TA_CENTER,spaceAfter=15)
    heading=ParagraphStyle('heading',parent=st,fontName='DejaVu-Bold',fontSize=10,leading=15,spaceBefore=13)
    def p(x,style=st):return Paragraph(escape(safe(x)).replace('\n','<br/>'),style)
    story=[]
    logo=logo_bytes(co)
    if logo:
        try:
            pil=PILImage.open(io.BytesIO(logo));pil.thumbnail((400,130));b=io.BytesIO();pil.convert('RGB').save(b,format='PNG');b.seek(0);story.append(Image(b,width=min(pil.width*.45,165),height=min(pil.height*.45,55)))
        except Exception:pass
    story += ([p(co.get('name'),heading)] if kind=='act' else []) + [p('Reģ. Nr.: '+safe(co.get('reg'))+'   '+safe(co.get('address')),sm),p('Banka: '+safe(co.get('bank'))+'   IBAN: '+safe(co.get('iban')),sm),Spacer(1,10),p('APSEKOŠANAS AKTS — PROJEKTS' if kind=='act' else 'BŪVDARBU TĀME',title),p('Objekts: '+safe(obj.get('name'))),p('Adrese: '+safe(obj.get('address'))),p('Būves veids: '+safe(obj.get('type')))]
    if kind=='act':
        story.append(p('Apsekošanas datums: '+safe(obj.get('inspectionDate'))+'     Apsekotājs: '+safe(obj.get('inspector'))))
        for label,key in [('Sniegtā informācija','description'),('Konstatētais (pēc sniegtās informācijas)','observations'),('Defekti / bojājumi','defects'),('Ieteicamie pasākumi','recommendations'),('Apsekošanas ierobežojumi','limitations')]:story.extend([p(label,heading),p(obj.get(key) or 'Nav norādīts')])
        inspections=payload.get('inspection') or []
        if inspections:
            story.append(p('Vizuālās apskates kontrolsaraksts (MK Nr. 907, 11.–13. punkts)',heading))
            rows_data=[[p(x,sm) for x in ('Nr.','Elements','Rezultāts / konstatētais','Nepieciešamās darbības')]]
            states={'unseen':'Nav apskatīts','ok':'Bez redzamiem bojājumiem','defect':'Konstatēti bojājumi','inaccessible':'Nav piekļuves','na':'Nav attiecināms'}
            for n,item in enumerate(inspections,1):
                if not isinstance(item,dict):continue
                result=(states.get(item.get('status'),'Nav apskatīts')+'; '+safe(item.get('note'))).strip('; ')
                rows_data.append([p(n,sm),p(item.get('name'),sm),p(result,sm),p(item.get('action'),sm)])
            t=Table(rows_data,colWidths=[27,138,197,141],repeatRows=1,hAlign='LEFT')
            t.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),colors.HexColor('#0C3153')),('ROWBACKGROUNDS',(0,1),(-1,-1),[colors.white,colors.HexColor('#EFF5FA')]),('GRID',(0,0),(-1,-1),.4,colors.HexColor('#B8CBDC')),('VALIGN',(0,0),(-1,-1),'TOP')]))
            for cell in rows_data[0]:cell.style=ParagraphStyle('inspectionHead',parent=sm,textColor=colors.white,fontName='DejaVu-Bold')
            story.append(t)
            story.append(p('MK Nr. 907, 3. pielikuma žurnāla ierakstam: datums, objekts, rezultāts, nepieciešamās darbības, apsekotājs un paraksts.',sm))
            for item in inspections:
                for n,raw in enumerate((item.get('photos') or [])[:4],1):
                    if not isinstance(raw,str) or not raw.startswith('data:image/'):continue
                    try:
                        im=PILImage.open(io.BytesIO(base64.b64decode(raw.split(',',1)[1])));im.thumbnail((900,700));b=io.BytesIO();im.convert('RGB').save(b,'JPEG',quality=72);b.seek(0)
                        factor=min(440/im.width,260/im.height)
                        story.append(KeepTogether([p('Foto: '+safe(item.get('name'))+' Nr. '+str(n),sm),Image(b,width=im.width*factor,height=im.height*factor)]))
                    except Exception:pass
        story.extend([Spacer(1,15),p('Apsekotājs: _________________________     Pasūtītājs: _________________________'),p('Šis dokuments ir projekta variants; faktisko apsekošanu un konstatējumus jāapstiprina atbildīgajai personai.',sm)])
    else:
        story.extend([p('Darbu apraksts: '+safe(obj.get('description'))),Spacer(1,10)])
        head=['Nr.','Darba / materiāla nosaukums','Mērv.','Daudz.','Darbi €/v.','Mater. €/v.','Meh. €/v.','Kopā €']
        data=[[p(x,sm) for x in head]];subtotal=0
        for i,r in enumerate(rows,1):
            q=num(r.get('qty'));lab=num(r.get('labor'));mat=num(r.get('material'));mach=num(r.get('machine'));amount=q*(lab+mat+mach);subtotal+=amount
            data.append([p(i,sm),p(r.get('name'),sm),p(r.get('unit'),sm),p(f'{q:.2f}',sm),p(f'{lab:.2f}',sm),p(f'{mat:.2f}',sm),p(f'{mach:.2f}',sm),p(f'{amount:.2f}',sm)])
        tab=Table(data,colWidths=[23,169,37,39,57,62,54,55],repeatRows=1,hAlign='LEFT')
        tab.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),colors.HexColor('#0C3153')),('TEXTCOLOR',(0,0),(-1,0),colors.white),('ROWBACKGROUNDS',(0,1),(-1,-1),[colors.white,colors.HexColor('#F0F5FA')]),('GRID',(0,0),(-1,-1),.3,colors.HexColor('#CCD8E3')),('VALIGN',(0,0),(-1,-1),'TOP'),('TOPPADDING',(0,0),(-1,-1),6),('BOTTOMPADDING',(0,0),(-1,-1),6)]))
        # Header Paragraph text color must be white explicitly
        for cell in data[0]:cell.style=ParagraphStyle('headercell',parent=sm,textColor=colors.white,fontName='DejaVu-Bold')
        story.append(tab)
        story.extend([Spacer(1,15),p(f'Kopā bez PVN: {subtotal:,.2f} EUR'),p(f'PVN 21%: {subtotal*.21:,.2f} EUR'),p(f'PAVISAM KOPĀ: {subtotal*1.21:,.2f} EUR',heading),p('Provizoriska tāme. Cenas un apjomi jāpārbauda pirms apstiprināšanas.',sm)])
    for i,raw in enumerate(payload.get('pics',[])[:6],1):
        if not isinstance(raw,str) or not raw.startswith(('data:image/jpeg;base64,','data:image/png;base64,')):continue
        try:
            im=PILImage.open(io.BytesIO(base64.b64decode(raw.split(',',1)[1])));im.thumbnail((900,650));b=io.BytesIO();im.convert('RGB').save(b,'JPEG',quality=75);b.seek(0)
            story.append(KeepTogether([p('Fotopielikums Nr. '+str(i),heading),Image(b,width=im.width*min(470/im.width,330/im.height),height=im.height*min(470/im.width,330/im.height))]))
        except Exception:pass
    if kind=='estimate':
        from reportlab.platypus import PageBreak
        story.append(PageBreak())
        story.append(p('PIELIKUMS Nr. 1 — CENU PAMATOJUMS',title))
        story.append(p('Avoti iegūti ar AI tīmekļa meklēšanu; saites un cenas nav neatkarīgi verificētas. Pirms piedāvājuma apstiprināšanas pārbaudiet katru avotu.',sm))
        story.append(p('Šis pielikums ir informatīvs un nav tāmes pamatdaļa. Pārbaudes laiks: '+safe(payload.get('price_checked_at')),sm))
        story.append(p('Cenu segments: '+{'low':'Ekonomiskais','mid':'Vidējais tirgus','high':'Augstākais'}.get(payload.get('price_level'),'Vidējais tirgus'),sm))
        evidence=payload.get('price_sources') or []
        if not evidence:story.append(p('Pārbaudīti tīmekļa cenu avoti nav pieejami. Tāmes cenas ir provizoriskas un nav apstiprinātas tirgus cenas.'))
        else:
            for i,x in enumerate(evidence,1):
                if not isinstance(x,dict):continue
                story.append(p(str(i)+'. '+safe(x.get('item'))+' — '+safe(x.get('title')),heading))
                story.append(p('Cena: '+safe(x.get('price_eur'))+' EUR; diapazons: '+safe(x.get('price_min_eur'))+'–'+safe(x.get('price_max_eur'))+' EUR / '+safe(x.get('unit'))+'; PVN iekļauts: '+str(x.get('includes_vat'))+'; datums: '+safe(x.get('observed_date')),sm))
                url=safe(x.get('url'))
                if url.startswith('https://'):story.append(Paragraph('<link href="'+escape(url,{'"':'&quot;'})+'" color="blue">'+escape(url)+'</link>',sm))
                if x.get('notes'):story.append(p(x.get('notes'),sm))
        story.append(p('Tāmes pozīciju cenu pamatojuma statuss',heading))
        for r in rows:story.append(p(safe(r.get('name'))+' — '+('AI provizoriska cena, bez tieša avota' if not r.get('evidence_ids') else 'Tīmekļa meklēšanas avoti: '+', '.join(r.get('evidence_ids'))),sm))
        story.append(p('Avotu cenu, PVN statusu, komplektāciju un pieejamību pirms piedāvājuma apstiprināšanas jāpārbauda.',sm))
    doc.build(story);output.seek(0);return output


@app.post('/api/inspection-refine')
def inspection_refine():
    data=request.get_json(silent=True) or {}
    entries=data.get('entries') or []
    if not isinstance(entries,list) or len(entries)>50:return jsonify(error='Pārāk daudz punktu'),400
    key=os.getenv('OPENAI_API_KEY')
    if not key:return jsonify(error='OPENAI_API_KEY nav konfigurēts'),503
    clean=[]
    for e in entries:
        if not isinstance(e,dict):continue
        clean.append({'id':str(e.get('id',''))[:40],'name':str(e.get('name',''))[:150],'status':str(e.get('status',''))[:30],'note':str(e.get('note',''))[:2000],'photos':[(x) for x in (e.get('photos') or [])[:2] if isinstance(x,str) and x.startswith(('data:image/jpeg;base64,','data:image/png;base64,')) and len(x)<1500000]})
    if not any(e['note'] or e['photos'] for e in clean):return jsonify(error='Pievienojiet tekstu vai foto'),400
    try:
        client=OpenAI(api_key=key,timeout=95)
        content=[{'type':'text','text':json.dumps([{k:v for k,v in e.items() if k!='photos'} for e in clean],ensure_ascii=False)}]
        for e in clean:
            for photo in e['photos'][:2]:
                if sum(1 for x in content if x.get('type')=='image_url')>=8:break
                content.append({'type':'text','text':'Foto attiecas uz punktu '+e['id']+' '+e['name']})
                content.append({'type':'image_url','image_url':{'url':photo,'detail':'low'}})
        result=client.chat.completions.create(model=os.getenv('OPENAI_MODEL','gpt-4.1-mini'),response_format={'type':'json_object'},messages=[{'role':'system','content':'Tu esi Latvijas dzīvojamo māju vizuālās apskates akta redaktors. MK Nr.907. Raksti latviski. NEIZDOMĀ neredzamus defektus, veiktas darbības vai tehniskās pārbaudes. Pārfrāzē tikai ievadītos faktus un redzamo foto, neskaidrības atzīmē. Foto nedod precīzus izmērus. Atgriez JSON {"entries":[{"id":"...","note":"...","action":"..."}]}. Ieteikumus sniedz tikai ja fakti to pamato.'},{'role':'user','content':content}],temperature=0.1)
        parsed=json.loads(result.choices[0].message.content)
        return jsonify(entries=[{'id':str(e.get('id',''))[:40],'note':str(e.get('note',''))[:2000],'action':str(e.get('action',''))[:1000]} for e in parsed.get('entries',[]) if isinstance(e,dict)])
    except Exception:
        app.logger.exception('Inspection refinement failed')
        return jsonify(error='AI apsekošanas apstrāde neizdevās'),502

@app.post('/api/document')
def document():
    data=request.get_json(silent=True)
    if not isinstance(data,dict) or not isinstance(data.get('rows'),list):return jsonify(error='Nederīgi dokumenta dati'),400
    data['rows']=data['rows'][:150];data['company']=data.get('company') or {};data['object']=data.get('object') or {}
    kind=data.get('kind','estimate');fmt=data.get('format','pdf')
    if kind not in ('act','estimate') or fmt not in ('pdf','xlsx') or (kind=='act' and fmt=='xlsx'):return jsonify(error='Neatbalstīts dokumenta formāts'),400
    try:
        stream=workbook(data) if fmt=='xlsx' else pdf(data)
        mime='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet' if fmt=='xlsx' else 'application/pdf'
        return send_file(stream,as_attachment=True,download_name=('Apsekosanas_akts' if kind=='act' else 'Buvdarbu_tame')+'.'+fmt,mimetype=mime)
    except Exception:
        app.logger.exception('Document generation failed');return jsonify(error='Dokumenta ģenerēšana neizdevās'),500

if __name__=='__main__':app.run(host='0.0.0.0',port=int(os.getenv('PORT','10000')))
