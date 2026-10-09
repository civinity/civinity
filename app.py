import os
from flask import Flask, request, jsonify
from flask_cors import CORS
from openai import OpenAI

app = Flask(__name__)

CORS(app, resources={
    r"/api/*": {
        "origins": os.getenv(
            "FRONTEND_URL",
            "https://civiniai.onrender.com"
        )
    }
})

@app.get("/")
def home():
    return jsonify({
        "status": "online",
        "service": "CIVINITY AI BuvTame API"
    })


@app.post("/api/estimate")
def create_estimate():
    api_key = os.getenv("OPENAI_API_KEY")

    if not api_key:
        return jsonify({
            "error": "OpenAI API key is not configured"
        }), 500

    data = request.get_json(silent=True)

    if not isinstance(data, dict):
        return jsonify({
            "error": "Invalid JSON request"
        }), 400

    description = str(data.get("description", "")).strip()

    if not description:
        return jsonify({
            "error": "Description is required"
        }), 400

    try:
        client = OpenAI(api_key=api_key)

        prompt = f"""
        Tu esi profesionāls būvdarbu tāmētājs Latvijā.

        Sagatavo provizorisku būvdarbu tāmi latviešu valodā.

        Darbu apraksts:
        {description}

        Iekļauj:
        1. Darbu nosaukumus
        2. Mērvienības
        3. Provizoriskos apjomus
        4. Materiālu sarakstu
        5. Nenoteiktos apjomus
        6. Izmaksu pieņēmumus
        7. PVN 21%

        Neizdomā pārbaudītas veikalu cenas.
        Skaidri norādi, ka cenas ir provizoriskas.
        """

        response = client.responses.create(
            model="gpt-4.1-mini",
            instructions="Tu esi profesionāls būvdarbu tāmētājs Latvijā. Atbildi latviešu valodā.",
            input=prompt
        )

        return jsonify({
            "success": True,
            "estimate": response.output_text
        })

    except Exception:
        app.logger.exception("Gemini request failed")
        return jsonify({
            "error": "AI estimate generation failed"
        }), 502


if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=int(os.getenv("PORT", "10000"))
    )
