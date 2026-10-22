
import os
import io
import base64
import sqlite3
import requests
import qrcode

from flask import Flask, render_template, request, jsonify
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)

DATABASE = "businesses.db"
OLLAMA_URL = "http://localhost:11434/api/generate"
OLLAMA_MODEL = "llama3.2"

GOOGLE_REVIEW_URL = (
    "https://www.google.com/search?"
    "client=safari&hs=QKrq&sca_esv=1de6a5064e96f472"
    "&hl=en-in&cs=1&output=search"
    "&kgmid=%2Fg%2F11zjcm5r13"
    "&q=The+Classic+Crown+Restaurant"
    "&shem=aiose2,epsd1,ltae,rimspwouoe"
    "&shndl=30&source=sh%2Fx%2Floc%2Fact%2Fm4%2F3"
    "&utm_source=chatgpt.com"
    "#lrd=0x3a19af4fff4150eb:0xd48ea355e420d359,3,,,,"
)


def get_connection():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with get_connection() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS businesses (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                slug TEXT UNIQUE NOT NULL,
                google_review_url TEXT
            )
        """)

        # Add the restaurant without deleting existing businesses.
        conn.execute("""
            INSERT OR IGNORE INTO businesses
                (name, slug, google_review_url)
            VALUES (?, ?, ?)
        """, (
            "The Classic Crown Restaurant",
            "classic-crown",
            GOOGLE_REVIEW_URL
        ))

        # Update the restaurant's link if its record already exists.
        conn.execute("""
            UPDATE businesses
            SET name = ?, google_review_url = ?
            WHERE slug = ?
        """, (
            "The Classic Crown Restaurant",
            GOOGLE_REVIEW_URL,
            "classic-crown"
        ))


def get_business(slug):
    with get_connection() as conn:
        return conn.execute(
            "SELECT * FROM businesses WHERE slug = ?",
            (slug,)
        ).fetchone()


def get_all_businesses():
    with get_connection() as conn:
        return conn.execute(
            "SELECT * FROM businesses ORDER BY name"
        ).fetchall()


@app.route("/")
def home():
    return render_template(
        "index.html",
        businesses=get_all_businesses()
    )


@app.route("/review/<slug>")
def review_page(slug):
    business = get_business(slug)

    if business is None:
        return "Business not found", 404

    return render_template(
        "review.html",
        business=business
    )


@app.route("/api/generate-review", methods=["POST"])
def generate_review():
    data = request.get_json(silent=True) or {}

    slug = data.get("slug", "classic-crown")
    feedback = (data.get("feedback") or "").strip()

    try:
        rating = int(data.get("rating", 0))
    except (ValueError, TypeError):
        return jsonify({"error": "Please select a valid star rating."}), 400

    if rating < 1 or rating > 5:
        return jsonify({"error": "Please select between 1 and 5 stars."}), 400

    if not feedback:
        return jsonify({
            "error": "Please describe your real experience before generating a review."
        }), 400

    if len(feedback) > 1000:
        return jsonify({"error": "Feedback must be 1000 characters or fewer."}), 400

    business = get_business(slug)

    if business is None:
        return jsonify({"error": "Business not found."}), 404

    prompt = f"""
You help customers write honest review drafts based on their own experiences.

Business: {business['name']}
Customer-selected rating: {rating}/5
Customer's actual feedback: {feedback}

Write one natural review draft of around 30 to 60 words.
Use only facts and experiences explicitly supplied by the customer.
Do not invent food, staff, service, events, products, or other details.
Preserve the customer's actual opinion and criticism.
Do not add claims the customer did not make.
Return only the review draft.
"""

    try:
        response = requests.post(
            OLLAMA_URL,
            json={
                "model": OLLAMA_MODEL,
                "prompt": prompt,
                "stream": False
            },
            timeout=120
        )

        response.raise_for_status()
        result = response.json()
        review = result.get("response", "").strip()

        if not review:
            return jsonify({
                "error": "The AI returned an empty draft. Please try again."
            }), 502

        return jsonify({
            "review": review,
            "google_review_url": business["google_review_url"] or ""
        })

    except requests.exceptions.ConnectionError:
        app.logger.exception("Could not connect to Ollama")
        return jsonify({
            "error": "Ollama is not running. Open a terminal and run: ollama run llama3.2"
        }), 503

    except requests.exceptions.Timeout:
        return jsonify({
            "error": "AI generation took too long. Please try again."
        }), 504

    except (requests.exceptions.RequestException, ValueError):
        app.logger.exception("Review generation failed")
        return jsonify({
            "error": "Could not generate a review draft. Please try again."
        }), 502


@app.route("/api/qr/<slug>")
def generate_qr(slug):
    business = get_business(slug)

    if business is None:
        return jsonify({"error": "Business not found."}), 404

    base_url = os.getenv(
        "PUBLIC_BASE_URL",
        request.url_root.rstrip("/")
    )

    review_url = f"{base_url}/review/{slug}"

    qr_image = qrcode.make(review_url)
    image_buffer = io.BytesIO()
    qr_image.save(image_buffer, format="PNG")

    encoded_image = base64.b64encode(
        image_buffer.getvalue()
    ).decode("utf-8")

    return jsonify({
        "business": business["name"],
        "review_url": review_url,
        "qr_image": encoded_image
    })


init_db()

if __name__ == "__main__":
    app.run(debug=True)
