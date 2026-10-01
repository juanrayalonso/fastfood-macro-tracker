import csv
import glob
import os

from flask import Flask, jsonify, render_template

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
NUM_FIELDS = ["kcal", "proteina_g", "carbs_g", "grasa_g", "azucar_g", "fibra_g", "sodio_mg", "precio_mxn"]

app = Flask(__name__)


def to_number(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def load_items():
    items = []
    for path in sorted(glob.glob(os.path.join(BASE_DIR, "*.csv"))):
        with open(path, encoding="utf-8-sig", newline="") as f:
            reader = csv.DictReader(f)
            # chipotle_builder.csv tiene otro formato; sus componentes ya están en chipotle.csv
            if "restaurante" not in (reader.fieldnames or []):
                continue
            for row in reader:
                if not row.get("producto"):
                    continue
                item = {
                    "restaurante": row["restaurante"].strip(),
                    "categoria": (row.get("categoria") or "").strip(),
                    "producto": row["producto"].strip(),
                    "porcion": (row.get("porcion") or "").strip(),
                }
                for field in NUM_FIELDS:
                    item[field] = to_number(row.get(field))
                items.append(item)
    for i, item in enumerate(items):
        item["id"] = i
    return items


ITEMS = load_items()


@app.route("/")
def index():
    restaurantes = sorted({item["restaurante"] for item in ITEMS})
    return render_template("index.html", restaurantes=restaurantes)


@app.route("/api/items")
def api_items():
    return jsonify(ITEMS)


if __name__ == "__main__":
    app.run(debug=True)
