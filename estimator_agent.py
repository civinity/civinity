"""CIVINITY photo-to-estimate agent. Research results are evidence, not automatically verified shop prices."""
import base64, io, json, os, re, threading, uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from flask import Blueprint, jsonify, request, send_file
from openai import OpenAI
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment
from openpyxl.utils import get_column_letter

bp=Blueprint('estimator_agent',__name__)
_jobs={}; _lock=threading.Lock(); _pool=ThreadPoolExecutor(max_workers=2)

def _json(s):
    s=s.strip(); a=s.find('{'); b=s.rfind('}')
    if a<0 or b<a: raise ValueError('AI neatgrieza JSON objektu')
    return json.loads(s[a:b+1])

def _client():
    return OpenAI(api_key=os.environ['OPENAI_API_KEY'],timeout=110,max_retries=1)

def _update(jid,**kw):
    with _lock: _jobs[jid].update(kw)

def _run(jid,description,images):
    try:
        client=_client(); model=os.getenv('ESTIMATOR_MODEL','gpt-4.1')
        _update(jid,status='vision',progress=12)
        content=[{'type':'text','text':description}]
        for pic in images:
            content.append({'type':'image_url','image_url':{'url':pic,'detail':'high'}})
        spec_prompt='''Tu esi pieredzējis Latvijas būvdarbu tāmētājs. Analizē lietotāja tekstu, shēmas un foto. Neizdomā izmērus, ko nevar nolasīt; izskaidro ģeometriju un atzīmē pieņēmumus. Ja atkritumu laukums atrodas kopējā laukumā, nepieskaiti to otrreiz. Izveido pilnu būvdarbu tehnoloģiju, no demontāžas līdz nodošanai, atsevišķi materiālus, darbus, mehānismus, izvešanas, rezerves, zudumus un drenāžas riskus. Neizdomā veikalu cenas. Atgriez tikai JSON: {"title":"...","summary":"...","geometry":[{"name":"...","formula":"...","area_m2":0}],"assumptions":["..."],"clarifications":["..."],"work_scope":["..."],"items":[{"name":"...","category":"labor|material|machine","unit":"m2|m3|m|gab.|kg|diena|kompl.","quantity":1,"technical_spec":"...","quantity_formula":"...","waste_pct":0}],"research_queries":["..."],"risks":["..."]}. Izmanto latviešu valodu. Precīzi ievēro lietotāja norādītos izmērus un pārbaudi aritmētiku.'''
        res=client.chat.completions.create(model=model,messages=[{'role':'system','content':spec_prompt},{'role':'user','content':content}],response_format={'type':'json_object'},max_tokens=8500)
        spec=_json(res.choices[0].message.content)
        _update(jid,status='research',progress=37,spec=spec)
        queries=(spec.get('research_queries') or [])[:14]
        itemnames=', '.join(str(x.get('name','')) for x in (spec.get('items') or [])[:38])
        research_prompt='''Meklē Latvijas internetā AKTUĀLUS publicētus būvmateriālu piedāvājumus un būvdarbu cenrāžus konkrētajam projektam. Izmanto web search. Atgriez tikai JSON ar {"offers":[{"item":"tāmes pozīcija","supplier":"...","product":"...","url":"https://...","price_eur":12.34,"unit":"m2","vat_included":true,"notes":"...","evidence":"published_page|search_snippet|price_range"}],"research_notes":["..."]}. Nedrīkst izdomāt cenas vai saites. Ja cenas nav, NEVEIDO piedāvājumu. Atšķir darbu likmes no materiālu cenām. Nekādā gadījumā neizmanto AI izdomātus cenu avotus. Preferē Latvijas tirgotājus un būvniekus. Maksimums 45 piedāvājumi. Lietotāja uzdevums: '''+description[:2500]+'\nPozīcijas: '+itemnames[:4200]+'\nMeklējumi: '+json.dumps(queries,ensure_ascii=False)
        evidence={'offers':[],'research_notes':[]}
        try:
            rr=client.responses.create(model=os.getenv('ESTIMATOR_RESEARCH_MODEL','gpt-4.1'),tools=[{'type':'web_search_preview','search_context_size':'high'}],input=research_prompt,max_output_tokens=5500,timeout=110)
            evidence=_json(rr.output_text)
        except Exception as e:
            evidence['research_notes']=['Tiešsaistes izpēte nav pabeigta: '+str(e)[:180]]
        # An LLM web search result alone is never a shop-page verification.
        cleaned=[]
        for o in evidence.get('offers',[])[:50]:
            if not isinstance(o,dict):continue
            url=str(o.get('url',''))
            if not url.startswith('https://') or len(url)>900:continue
            try:
                price=float(o.get('price_eur'))
                if not 0<price<1e7:continue
            except (ValueError,TypeError):continue
            o['price_eur']=round(price,2)
            o['verification']='web_search_reported_not_independently_verified'
            cleaned.append(o)
        evidence['offers']=cleaned
        _update(jid,status='estimate',progress=70,evidence=evidence)
        prompt='''Sagatavo PROFESIONĀLU Latvijas būvdarbu TĀMI pēc tehniskās specifikācijas un interneta cenu izpētes. Neizmanto nulles cenas kā bezmaksas materiālus. Katram darbam un materiālam, kam nav pierādītas cenas, drīksti ieteikt BUDŽETA NOVĒRTĒJUMU, taču obligāti atzīmē statusu "provisional" un paskaidro, ka tā nav pārbaudīta tirgus cena. Ja cena ir salīdzināma ar publicēto piedāvājumu, status "web_researched" un norādi avota URL. Atsevišķi labor, material, machine izmaksas katrā rindā, bez dubultskaitīšanas. Aprēķini precīzus apjomus, iekļauj zudumus un transportu, demontāžu, atkritumus, materiālus, darbus, mehānismus, apmales, nepieciešamo grunts sagatavošanu un objekta nodošanu. Sadalījums pa darbu posmiem. Atkritumu konteineru zona atsevišķā nodaļā, bet nedubulto kopējo seguma laukumu. PVN 21%. Neuzdod izdomātas cenas kā veikalu cenas. Atgriez tikai JSON: {"title":"...","summary":"...","geometry":[...],"assumptions":["..."],"clarifications":["..."],"sections":[{"name":"...","items":[{"name":"...","unit":"m2","quantity":1,"labor":0,"material":0,"machine":0,"status":"web_researched|provisional|missing","source_url":"...","technical_spec":"...","quantity_formula":"...","note":"..."}]}],"risks":["..."],"methodology":"..."}. Visi skaitļi EUR bez PVN. Ja avota cenā PVN iekļauts, pārrēķini bez PVN. Neizmanto cenu, ja nav skaidra mērvienība vai specifikācija. Vismaz 15 detalizētas pozīcijas, ja apjoms to prasa.'''
        resp=client.chat.completions.create(model=model,messages=[{'role':'system','content':prompt},{'role':'user','content':json.dumps({'specification':spec,'market_research':evidence},ensure_ascii=False)}],response_format={'type':'json_object'},max_tokens=11000)
        result=_json(resp.choices[0].message.content)
        total=0; missing=0
        for section in result.get('sections',[]):
            for item in section.get('items',[]):
                def numeric(k):
                    try: v=float(item.get(k) or 0); return round(max(0,min(v,1e8)),4)
                    except (TypeError,ValueError):return 0
                for k in ('quantity','labor','material','machine'):item[k]=numeric(k)
                item['subtotal']=round(item['quantity']*(item['labor']+item['material']+item['machine']),2)
                total+=item['subtotal']
                if item.get('status')=='missing':missing+=1
        result['subtotal']=round(total,2);result['vat']=round(total*.21,2);result['total']=round(total*1.21,2)
        result['market_offers']=cleaned;result['research_notes']=evidence.get('research_notes',[])
        result['disclaimer']='Provizoriska tāme: web_search atrastās cenas nav automātiski apstiprināti veikalu piedāvājumi; status provisional nav pārbaudīta tirgus cena. Pirms piedāvājuma apstiprināt specifikācijas, PVN, cenas, piegādi un apjomus.'
        result['created_at']=datetime.now(timezone.utc).isoformat()
        _update(jid,status='done',progress=100,result=result)
    except Exception as e:
        _update(jid,status='failed',error=str(e)[:350],progress=100)

@bp.post('/api/agent/estimate')
def start():
    if not os.getenv('OPENAI_API_KEY'):return jsonify(error='Render vidē nav OPENAI_API_KEY'),503
    body=request.get_json(silent=True) or {}
    description=str(body.get('description',''))[:12000]
    images=body.get('images') or []
    if len(description.strip())<10:return jsonify(error='Nepieciešams darbu apraksts'),400
    if not isinstance(images,list) or len(images)>6:return jsonify(error='Maksimums 6 attēli'),400
    for img in images:
        if not isinstance(img,str) or not re.match(r'^data:image/(jpeg|png|webp);base64,',img) or len(img)>4500000:
            return jsonify(error='Nepareizs foto formāts vai izmērs'),400
    jid=uuid.uuid4().hex
    with _lock:
        if len(_jobs)>150:
            for k in list(_jobs)[:60]:_jobs.pop(k,None)
        _jobs[jid]={'status':'queued','progress':0}
    _pool.submit(_run,jid,description,images)
    return jsonify(job_id=jid),202

@bp.get('/api/agent/estimate/<jid>')
def get_job(jid):
    with _lock:job=_jobs.get(jid)
    return (jsonify(job) if job else (jsonify(error='Uzdevums nav atrasts; serveris iespējams restartējās'),404))

@bp.post('/api/agent/xlsx')
def export_xlsx():
    data=request.get_json(silent=True) or {}; r=data.get('result') or {}; c=data.get('company') or {}
    if not isinstance(r.get('sections'),list):return jsonify(error='Tāme nav pieejama'),400
    wb=Workbook();ws=wb.active;ws.title='Tāme'
    ws.merge_cells('A1:H1');ws['A1']=str(c.get('name') or 'CIVINITY')[:180];ws['A1'].font=Font(size=19,bold=True,color='0A3960')
    ws.merge_cells('A2:H2');ws['A2']=' | '.join(str(c.get(k) or '') for k in ('reg','address','iban','bank'))[:400]
    ws.merge_cells('A4:H4');ws['A4']=str(r.get('title') or 'BŪVDARBU TĀME');ws['A4'].font=Font(size=15,bold=True,color='0A3960')
    ws.merge_cells('A5:H5');obj=data.get('object') or {};ws['A5']=('Objekts: '+str(obj.get('name') or '')+' | Adrese: '+str(obj.get('address') or '')) if isinstance(obj,dict) else str(obj)
    ws.append([]);ws.append(['Nr.','Pozīcija / specifikācija','Mērv.','Daudz.','Darbs €/v.','Materiāli €/v.','Mehānismi €/v.','Kopā bez PVN €'])
    for cell in ws[7]:cell.fill=PatternFill('solid',fgColor='143D61');cell.font=Font(color='FFFFFF',bold=True)
    n=0
    for sec in r.get('sections',[]):
        ws.append(['',str(sec.get('name',''))]);ws.cell(ws.max_row,2).font=Font(bold=True,color='0A3960')
        for i in sec.get('items',[]):
            n+=1; row=ws.max_row+1
            ws.append([n,str(i.get('name',''))+'\n'+str(i.get('technical_spec',''))+'\n'+str(i.get('note','')),i.get('unit'),i.get('quantity'),i.get('labor'),i.get('material'),i.get('machine'),f'=D{row}*(E{row}+F{row}+G{row})'])
            ws.cell(row,2).alignment=Alignment(wrap_text=True,vertical='top');ws.row_dimensions[row].height=43
    last=ws.max_row
    ws.append(['','KOPĀ BEZ PVN','','','','','',f'=SUM(H8:H{last})'])
    ws.append(['','PVN 21%','','','','',f'=H{last+1}*0.21'])
    ws.append(['','KOPĀ AR PVN','','','','',f'=H{last+1}+H{last+2}'])
    ws2=wb.create_sheet('Cenu avoti');ws2.append(['Pozīcija','Piegādātājs','Prece','Cena EUR','Mērvienība','PVN iekļauts','Saite','Pārbaudes statuss'])
    for o in r.get('market_offers',[]):ws2.append([o.get('item'),o.get('supplier'),o.get('product'),o.get('price_eur'),o.get('unit'),o.get('vat_included'),o.get('url'),o.get('verification')])
    ws3=wb.create_sheet('Pieņēmumi un riski')
    for heading,key in [('Ģeometrija','geometry'),('Pieņēmumi','assumptions'),('Jāprecizē','clarifications'),('Riski','risks'),('Izpētes piezīmes','research_notes')]:
        ws3.append([heading]);ws3.cell(ws3.max_row,1).font=Font(bold=True,color='0A3960')
        for v in r.get(key,[]):ws3.append([json.dumps(v,ensure_ascii=False) if isinstance(v,dict) else str(v)])
    ws3.append([r.get('disclaimer','')])
    for sh in wb:
        sh.freeze_panes='C8' if sh==ws else 'A2'
        sh.sheet_view.showGridLines=False
        if sh==ws:
            for col,w in {'A':7,'B':70,'C':12,'D':12,'E':15,'F':17,'G':17,'H':21}.items():sh.column_dimensions[col].width=w
        elif sh==ws2:
            for col in 'ABCDEFGH':sh.column_dimensions[col].width=24 if col!='G' else 75
        else:sh.column_dimensions['A'].width=110
    # User logo is supplied by the existing settings form, not hard-coded.
    logo=c.get('logo','')
    if isinstance(logo,str) and logo.startswith('data:image/'):
        try:
            from openpyxl.drawing.image import Image
            binary=base64.b64decode(logo.split(',',1)[1]); im=Image(io.BytesIO(binary));im.width=min(im.width,145);im.height=min(im.height,58);ws.add_image(im,'G1')
        except Exception:pass
    buf=io.BytesIO();wb.save(buf);buf.seek(0)
    return send_file(buf,mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',as_attachment=True,download_name='CIVINITY_AI_Tame_Agent.xlsx')


@bp.post('/api/agent/document')
def export_agent_document():
    """Create estimate or draft inspection act with selected company branding."""
    from flask import abort
    from xml.sax.saxutils import escape
    body=request.get_json(silent=True) or {}
    result=body.get('result') or {}; company=body.get('company') or {}; obj=body.get('object') or {}; act=body.get('act') or {}
    kind=body.get('kind','estimate');fmt=body.get('format','pdf')
    if kind not in ('estimate','act') or fmt not in ('pdf','docx') or not isinstance(result.get('sections'),list):
        return jsonify(error='Nepareizs dokumenta pieprasījums'),400
    def safe(x):return str(x if x is not None else '')[:2500]
    def num(x):
        try:return float(x or 0)
        except (TypeError,ValueError):return 0.
    title='APSEKOŠANAS AKTA PROJEKTS' if kind=='act' else 'BŪVDARBU TĀME'
    heading=safe(company.get('name') or 'CIVINITY')
    details=' | '.join(filter(None,[safe(company.get(k)) for k in ('reg','address','bank','iban')]))
    objline='Objekts: '+safe(obj.get('name'))+' | Adrese: '+safe(obj.get('address'))
    entries=[]
    if kind=='act':
        entries=[('Konstatētais',safe(act.get('observations'))),('Defekti un riski',safe(act.get('defects'))),('Ieteicamie darbi',safe(act.get('recommendations'))),('Apsekošanas ierobežojumi',safe(act.get('limitations'))),('Apsekotājs',safe(act.get('inspector'))),('Pasūtītājs',safe(act.get('customer')))]
    else:
        for section in result['sections']:
            entries.append(('SECTION',safe(section.get('name'))))
            for i in section.get('items',[]):
                q=num(i.get('quantity')); price=num(i.get('labor'))+num(i.get('material'))+num(i.get('machine'))
                entries.append(('ITEM',safe(i.get('name')),safe(i.get('unit')),q,num(i.get('labor')),num(i.get('material')),num(i.get('machine')),round(q*price,2),safe(i.get('status')),safe(i.get('source_url'))))
    if fmt=='docx':
        from docx import Document
        from docx.shared import Inches,Pt,RGBColor
        doc=Document();sec=doc.sections[0];sec.header_distance=Inches(.35)
        doc.add_heading(heading,0)
        if details:doc.add_paragraph(details)
        doc.add_heading(title,1);doc.add_paragraph(objline)
        doc.add_paragraph('Datums: '+safe(obj.get('date')))
        logo=company.get('logo','')
        if isinstance(logo,str) and logo.startswith('data:image/'):
            try:doc.add_picture(io.BytesIO(base64.b64decode(logo.split(',',1)[1])),width=Inches(1.5))
            except Exception:pass
        if kind=='act':
            for h,t in entries:doc.add_heading(h,2);doc.add_paragraph(t or 'Nav norādīts')
            doc.add_paragraph('Dokuments ir projekta stadijā; nepieciešama atbildīgās personas faktu pārbaude un paraksts.')
        else:
            doc.add_paragraph(safe(result.get('summary')))
            table=doc.add_table(rows=1,cols=7);table.style='Table Grid'
            for c,v in zip(table.rows[0].cells,['Pozīcija','Mērv.','Daudz.','Darbs €/v.','Materiāli €/v.','Mehānismi €/v.','Kopā €']):c.text=v
            for e in entries:
                if e[0]=='SECTION':
                    cells=table.add_row().cells;cells[0].text=e[1];continue
                _,name,unit,q,lab,mat,mach,total,status,url=e
                cells=table.add_row().cells
                for c,v in zip(cells,[name+' ('+status+')',unit,f'{q:g}',f'{lab:.2f}',f'{mat:.2f}',f'{mach:.2f}',f'{total:.2f}']):c.text=v
            for key,label in [('subtotal','Kopā bez PVN'),('vat','PVN 21%'),('total','Kopā ar PVN')]:doc.add_paragraph(label+': '+f'{num(result.get(key)):.2f} EUR')
            doc.add_heading('Cenu avoti',2)
            for o in (result.get('market_offers') or [])[:80]:doc.add_paragraph(safe(o.get('supplier'))+' — '+safe(o.get('product'))+' — '+safe(o.get('url')))
            doc.add_paragraph(safe(result.get('disclaimer')))
        stream=io.BytesIO();doc.save(stream);stream.seek(0)
        return send_file(stream,as_attachment=True,download_name=('CIVINITY_Akts' if kind=='act' else 'CIVINITY_Tame')+'.docx',mimetype='application/vnd.openxmlformats-officedocument.wordprocessingml.document')
    # Unified A4 portrait design for every company. Pricing evidence starts on a new page.
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, LongTable, Table, TableStyle, PageBreak, Image as RLImage
    from reportlab.lib import colors
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    from xml.sax.saxutils import escape as xml_escape
    navy=colors.HexColor('#102F4F');blue=colors.HexColor('#13618D');pale=colors.HexColor('#EAF2F8');gray=colors.HexColor('#CAD7E1')
    regular='/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'
    bold='/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf'
    if 'CivinityRegular' not in pdfmetrics.getRegisteredFontNames():pdfmetrics.registerFont(TTFont('CivinityRegular',regular))
    if 'CivinityBold' not in pdfmetrics.getRegisteredFontNames():pdfmetrics.registerFont(TTFont('CivinityBold',bold))
    body_style=ParagraphStyle('bodyc',fontName='CivinityRegular',fontSize=7.5,leading=11,spaceAfter=5)
    tiny=ParagraphStyle('tinyc',parent=body_style,fontSize=6.4,leading=9,spaceAfter=1)
    white=ParagraphStyle('whitec',parent=tiny,fontName='CivinityBold',textColor=colors.white)
    h1=ParagraphStyle('h1c',parent=body_style,fontName='CivinityBold',fontSize=14,leading=19,textColor=navy,spaceAfter=9)
    h2=ParagraphStyle('h2c',parent=body_style,fontName='CivinityBold',fontSize=9,leading=13,textColor=navy,spaceBefore=9)
    def para(v,style=body_style):return Paragraph(xml_escape(safe(v)).replace('\n','<br/>'),style)
    buffer=io.BytesIO()
    doc=SimpleDocTemplate(buffer,pagesize=A4,leftMargin=29,rightMargin=29,topMargin=31,bottomMargin=35,title=title,author=heading)
    width=A4[0]-58
    def header():
        left=[para(heading,h1),para('Reģ. Nr.: '+safe(company.get('reg')),tiny),para(safe(company.get('address')),tiny),para('Banka: '+safe(company.get('bank'))+'  |  IBAN: '+safe(company.get('iban')),tiny)]
        logo=company.get('logo','');image=None
        if isinstance(logo,str) and logo.startswith('data:image/'):
            try:
                from PIL import Image as PILImage
                raw=base64.b64decode(logo.split(',',1)[1]);im=PILImage.open(io.BytesIO(raw));im.thumbnail((600,180));out=io.BytesIO();im.convert('RGB').save(out,format='PNG');out.seek(0)
                w,h=im.size;scale=min(125/max(w,1),47/max(h,1));image=RLImage(out,width=w*scale,height=h*scale)
            except Exception:pass
        head=Table([[left,image or para('',tiny)]],colWidths=[width-137,137]);head.setStyle(TableStyle([('VALIGN',(0,0),(-1,-1),'TOP'),('BOTTOMPADDING',(0,0),(-1,-1),12),('LINEBELOW',(0,0),(-1,-1),1.5,blue)]))
        return head
    story=[header(),Spacer(1,12),para(title,h1),para(objline),para('Datums: '+safe(obj.get('date') or obj.get('inspectionDate'))),para('Pasūtītājs: '+safe(obj.get('customer'))),Spacer(1,7)]
    if kind=='act':
        for section,text in entries:story.extend([para(section,h2),para(text or 'Nav norādīts')])
        story.append(Spacer(1,12));story.append(para('Dokuments ir apsekošanas akta projekts. Pirms parakstīšanas konstatējumi jāpārbauda klātienē.',tiny))
    else:
        if result.get('summary'):story.append(para(result.get('summary')))
        # 8 columns fit the printable width of A4 portrait (537 pt).
        columns=[21,180,34,39,58,65,64,66]
        assert sum(columns)<=width
        labels=['Nr.','Darbu un materiālu nosaukums','Mērv.','Daudz.','Darbi €/v.','Materiāli €/v.','Mehān. €/v.','Summa €']
        grid=[[para(v,white) for v in labels]]
        row_count=0;section_rows=[]
        for e in entries:
            if e[0]=='SECTION':
                section_rows.append(len(grid));grid.append([para(e[1],h2)]+['']*7)
                continue
            _,name,unit,q,lab,mat,mach,total,status,url=e
            row_count+=1
            grid.append([para(str(row_count),tiny),para(name,tiny),para(unit,tiny),para(f'{q:g}',tiny),para(f'{lab:.2f}',tiny),para(f'{mat:.2f}',tiny),para(f'{mach:.2f}',tiny),para(f'{total:.2f}',tiny)])
        table=LongTable(grid,colWidths=columns,repeatRows=1,hAlign='LEFT')
        commands=[('BACKGROUND',(0,0),(-1,0),navy),('VALIGN',(0,0),(-1,-1),'TOP'),('LINEBELOW',(0,0),(-1,-1),.35,gray),('ROWBACKGROUNDS',(0,1),(-1,-1),[colors.white,colors.HexColor('#F6F9FC')]),('LEFTPADDING',(0,0),(-1,-1),3),('RIGHTPADDING',(0,0),(-1,-1),3),('TOPPADDING',(0,0),(-1,-1),5),('BOTTOMPADDING',(0,0),(-1,-1),5)]
        for i in section_rows:commands.extend([('BACKGROUND',(0,i),(-1,i),pale),('SPAN',(0,i),(-1,i))])
        table.setStyle(TableStyle(commands));story.append(table)
        story.append(Spacer(1,13))
        totals=[('Kopā bez PVN',num(result.get('subtotal'))),('PVN 21%',num(result.get('vat'))),('PAVISAM KOPĀ',num(result.get('total')))]
        summary=Table([[para(label,h2 if n==2 else body_style),para(f'{value:,.2f} EUR',h2 if n==2 else body_style)] for n,(label,value) in enumerate(totals)],colWidths=[width-130,130]);summary.setStyle(TableStyle([('ALIGN',(1,0),(1,-1),'RIGHT'),('BACKGROUND',(0,2),(-1,2),pale),('LINEABOVE',(0,2),(-1,2),1,blue)]));story.append(summary)
        if result.get('disclaimer'):story.append(Spacer(1,10));story.append(para(result['disclaimer'],tiny))
        # Pricing evidence is deliberately NOT part of the estimate's main pages.
        story.append(PageBreak());story.append(header());story.append(Spacer(1,10));story.append(para('PIELIKUMS Nr. 1 — CENU PAMATOJUMS UN PIEŅĒMUMI',h1))
        story.append(para('Šis pielikums ir atsevišķs no tāmes pamatdaļas. Piegādātāju cenas, PVN, pieejamība un specifikācija jāpārbauda pirms pasūtījuma.',tiny))
        offers=result.get('market_offers') or []
        if offers:
            evidence=[[para('Nr.',white),para('Piegādātājs / produkts',white),para('Cena / informācija',white),para('Avots',white)]]
            for n,o in enumerate(offers,1):
                if not isinstance(o,dict):continue
                price=o.get('price_eur',o.get('price',''))
                label=' / '.join(filter(None,[safe(o.get('supplier')),safe(o.get('product') or o.get('title'))]))
                evidence.append([para(str(n),tiny),para(label,tiny),para(safe(price)+' '+safe(o.get('unit')),tiny),para(safe(o.get('url')),tiny)])
            t=LongTable(evidence,colWidths=[23,170,85,width-278],repeatRows=1)
            t.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),navy),('VALIGN',(0,0),(-1,-1),'TOP'),('ROWBACKGROUNDS',(0,1),(-1,-1),[colors.white,pale]),('LINEBELOW',(0,0),(-1,-1),.3,gray),('LEFTPADDING',(0,0),(-1,-1),5),('RIGHTPADDING',(0,0),(-1,-1),5)]));story.append(t)
        else:story.append(para('Pārbaudāmi cenu avoti nav pievienoti. Tāmes cenas uzskatāmas par provizoriskām.'))
        story.append(Spacer(1,12));story.append(para('Cenu un apjomu pieņēmumi',h2))
        if result.get('assumptions'):
            for item in result['assumptions'][:60]:story.append(para('• '+safe(item),tiny))
        else:story.append(para('Pirms darbu uzsākšanas pārbaudīt apjomus, tehnoloģiju, transporta izmaksas un piegādes nosacījumus.',tiny))
    def page_footer(canvas,doc):
        canvas.saveState();canvas.setStrokeColor(gray);canvas.line(29,27,A4[0]-29,27);canvas.setFont('CivinityRegular',7);canvas.setFillColor(colors.HexColor('#64748B'));canvas.drawString(29,16,safe(company.get('name') or 'CIVINITY'));canvas.drawRightString(A4[0]-29,16,f'{doc.page}');canvas.restoreState()
    doc.build(story,onFirstPage=page_footer,onLaterPages=page_footer);buffer.seek(0)
    return send_file(buffer,as_attachment=True,download_name=('CIVINITY_Akts' if kind=='act' else 'CIVINITY_Tame')+'.pdf',mimetype='application/pdf')
