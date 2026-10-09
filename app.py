import base64
import io
import json
import logging
import os
from datetime import datetime
from xml.sax.saxutils import escape
from flask import Flask, jsonify, request, send_file
from flask_cors import CORS
from openai import OpenAI

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 18 * 1024 * 1024
CORS(app, resources={r'/api/*': {'origins': os.getenv('FRONTEND_URL', 'https://civiniai.onrender.com')}})

@app.get('/')
def home():
    return jsonify(status='online', service='CIVINITY AI BuvTame API', version='3.0')

@app.post('/api/estimate')
def estimate():
    data = request.get_json(silent=True)
    if not isinstance(data, dict) or not str(data.get('description', '')).strip():
        return jsonify(error='Ievadiet darba aprakstu.'), 400
    key = os.getenv('OPENAI_API_KEY')
    if not key:
        return jsonify(error='OPENAI_API_KEY nav konfigurēts Render Environment.'), 503
    description = str(data['description'])[:12000]
    images = data.get('images') or []
    if not isinstance(images, list):
        images = []
    content = [{'type':'text', 'text':description}]
    for img in images[:3]:
        if isinstance(img, str) and img.startswith(('data:image/jpeg;base64,', 'data:image/png;base64,', 'data:image/webp;base64,')) and len(img)<6_000_000:
            content.append({'type':'image_url', 'image_url':{'url':img, 'detail':'low'}})
    instructions = '''Tu esi profesionāls Latvijas būvdarbu tāmētājs. Atbildi latviski tikai JSON formātā.
Sagatavo DETALIZĒTU, pārbaudāmu provizorisku tāmi un atsevišķu apsekošanas akta PROJEKTU.
KRITISKI: nedrīkst vienā rindā rakstīt "Durvju nomaiņa". Katru procesu un materiālu nodali atsevišķās rindās. Durvju nomaiņai apsver: esošo durvju vērtnes demontāžu, kārbas demontāžu (ja nepieciešams), būvgružu izvešanu, ailas sagatavošanu un labošanas darbus, jaunu durvju bloku/vērtni, kārbu, eņģes, slēdzeni, rokturus, blīvējumu, stiprinājumus, montāžas putas, uzstādīšanas darbu, regulēšanu, apdari, transportu. Iekļauj tikai attiecināmos darbus, neizdomā prasības. Līdzīgi detalizē citus darbu veidus. Mērķis: vismaz 8–15 atsevišķas pozīcijas vienkāršai durvju nomaiņai, ja tās ir attiecināmas.
Ja ir foto: analizē redzamos elementus, bet neapgalvo neredzamus defektus un NEIZSECINI precīzus izmērus no foto. Atšķir redzēto no pieņēmumiem. Ja durvju izmēri nav zināmi, uzskaiti vienību skaitu kā pieņēmumu (piem. 1 gab.), bet izmērus norādi pie precizējamiem datiem.
Cenas labor/material/machine ir atsevišķas VIENĪBAS provizoriskas cenas EUR bez PVN. Darba pozīcijās pārsvarā labor, materiālu pozīcijās pārsvarā material. Vienu izmaksu nedrīkst ieskaitīt divreiz. Neapgalvo, ka cenas ir pārbaudītas tirgū. Ja cenu nevar pamatoti novērtēt, ievadi 0 un norādi precizējumu. qty=0 tikai tad, ja pat provizorisks apjoms nav iespējams. Neizdomā apsekošanas datumu vai faktu, ka apsekošana ir veikta.
Atgriez JSON ar struktūru: {"summary":"...", "rows":[{"name":"...", "unit":"gab.", "qty":1, "labor":0, "material":0, "machine":0, "category":"darbi vai materiali vai mehanismi"}], "act":{"observations":"...", "defects":"...", "recommendations":"...", "limitations":"..."}, "assumptions":["..."], "missing_data":["..."]}. Atgriez pēc iespējas konkrētas pozīcijas un materiālus; PVN 21% rēķina programma.'''
    try:
        client = OpenAI(api_key=key, timeout=110)
        res = client.chat.completions.create(model=os.getenv('OPENAI_MODEL', 'gpt-4.1-mini'), messages=[{'role':'system','content':instructions},{'role':'user','content':content}], response_format={'type':'json_object'},temperature=0.15)
        obj = json.loads(res.choices[0].message.content)
        if not isinstance(obj.get('rows'), list) or not isinstance(obj.get('act'), dict):
            raise ValueError('AI returned unexpected structure')
        rows=[]
        for r in obj['rows'][:100]:
            if not isinstance(r, dict): continue
            def num(k):
                try:return max(0,min(float(r.get(k) or 0),1e8))
                except (ValueError,TypeError):return 0
            rows.append(dict(name=str(r.get('name') or '')[:300],unit=str(r.get('unit') or 'gab.')[:20],qty=num('qty'),labor=num('labor'),material=num('material'),machine=num('machine'),category=str(r.get('category') or 'darbi')[:30]))
        return jsonify(success=True,estimate=obj.get('summary',''),rows=rows,act=obj['act'],assumptions=obj.get('assumptions',[]),missing_data=obj.get('missing_data',[]))
    except Exception:
        app.logger.exception('AI estimate failed')
        return jsonify(error='AI ģenerēšana neizdevās. Pārbaudiet Render Logs.'),502

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
    story += [p(co.get('name'),heading),p('Reģ. Nr.: '+safe(co.get('reg'))+'   '+safe(co.get('address')),sm),p('Banka: '+safe(co.get('bank'))+'   IBAN: '+safe(co.get('iban')),sm),Spacer(1,10),p('APSEKOŠANAS AKTS — PROJEKTS' if kind=='act' else 'BŪVDARBU TĀME',title),p('Objekts: '+safe(obj.get('name'))),p('Adrese: '+safe(obj.get('address'))),p('Būves veids: '+safe(obj.get('type')))]
    if kind=='act':
        story.append(p('Apsekošanas datums: '+safe(obj.get('inspectionDate'))+'     Apsekotājs: '+safe(obj.get('inspector'))))
        for label,key in [('Sniegtā informācija','description'),('Konstatētais (pēc sniegtās informācijas)','observations'),('Defekti / bojājumi','defects'),('Ieteicamie pasākumi','recommendations'),('Apsekošanas ierobežojumi','limitations')]:story.extend([p(label,heading),p(obj.get(key) or 'Nav norādīts')])
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
    doc.build(story);output.seek(0);return output

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
