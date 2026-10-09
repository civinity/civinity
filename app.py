import json
import logging
import os
from flask import Flask, jsonify, request
from flask_cors import CORS
from openai import OpenAI

app = Flask(__name__)
CORS(app, resources={r'/api/*': {'origins': os.getenv('FRONTEND_URL', 'https://civiniai.onrender.com')}})

@app.get('/')
def home():
    return jsonify(status='online', service='CIVINITY AI BuvTame API', version='2.0')

@app.post('/api/estimate')
def estimate():
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return jsonify(error='Invalid JSON request'), 400
    description = str(payload.get('description') or '').strip()
    if not description:
        return jsonify(error='Description is required'), 400
    key = os.getenv('OPENAI_API_KEY')
    if not key:
        return jsonify(error='OpenAI API key is not configured'), 503
    company = str(payload.get('company') or 'solutions')[:40]
    prompt = f'''Tu esi Latvijas būvdarbu tāmētājs un apsekošanas aktu sastādītājs.
Objekta dati un lietotāja apraksts:\n{description[:12000]}\n
Sagatavo vienlaikus provizorisku tāmi un APSEKOŠANAS AKTA PROJEKTU latviešu valodā.
Atgriez TIKAI derīgu JSON objektu ar šādām atslēgām:
{{"summary":"īss apraksts", "rows":[{{"name":"darbs", "unit":"m²", "qty":0, "labor":0, "material":0, "machine":0, "category":"darbi"}}], "act":{{"inspection_date":"", "observations":"konstatētais pēc sniegtā apraksta", "defects":"defekti", "recommendations":"ieteikumi", "limitations":"kas nav pārbaudīts"}}, "assumptions":["pieņēmums"], "missing_data":["nezināmais"]}}
'rows' katra cena ir provizoriska VIENĪBAS cena EUR bez PVN; labor, material, machine atsevišķi; qty tikai ja zināms vai skaidri pieņemts, citādi 0. Nav atļauts apgalvot, ka ir pārbaudītas tirgus cenas. Neizdomā apsekošanas faktus, fotogrāfiju saturu vai datumu; akts ir projekts, kam nepieciešama apsekošanas apstiprināšana. PVN aprēķinās programma. Nepiešķir nezināmu defektu kā apstiprinātu faktu. Uzņēmuma izvēle: {company}.'''
    try:
        client = OpenAI(api_key=key, timeout=90)
        response = client.chat.completions.create(
            model=os.getenv('OPENAI_MODEL', 'gpt-4.1-mini'),
            messages=[{'role': 'system', 'content': 'Atbildi tikai ar derīgu JSON. Latviešu valoda.'}, {'role': 'user', 'content': prompt}],
            response_format={'type': 'json_object'}, temperature=0.2)
        parsed = json.loads(response.choices[0].message.content)
        if not isinstance(parsed.get('rows'), list) or not isinstance(parsed.get('act'), dict):
            raise ValueError('Unexpected AI JSON structure')
        rows = []
        for r in parsed['rows'][:100]:
            if not isinstance(r, dict):
                continue
            def number(k):
                try:
                    return max(0, min(float(r.get(k) or 0), 100000000))
                except (TypeError, ValueError):
                    return 0
            rows.append({'name': str(r.get('name') or '')[:300], 'unit': str(r.get('unit') or 'gab.')[:20], 'qty': number('qty'), 'labor': number('labor'), 'material': number('material'), 'machine': number('machine'), 'category': str(r.get('category') or 'darbi')[:30]})
        return jsonify(success=True, estimate=parsed.get('summary', ''), rows=rows, act=parsed['act'], assumptions=parsed.get('assumptions', []), missing_data=parsed.get('missing_data', []))
    except Exception:
        app.logger.exception('AI estimate request failed')
        return jsonify(error='AI estimate generation failed. Check API logs.'), 502

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.getenv('PORT', '10000')))
