import csv
import glob
import os

from flask import Flask, jsonify, render_template

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
NUM_FIELDS = ["kcal", "proteina_g", "carbs_g", "grasa_g", "azucar_g", "fibra_g", "sodio_mg", "precio_mxn"]

# Tipo de restaurante -> restaurantes, en el orden en que se muestran
TIPOS = {
    "Hamburguesas": ["McDonald's", "Carl's Jr.", "Jack In The Box"],
    "Mexicana": ["Chipotle", "Taco Palenque", "Doña Tota"],
    "Pizza e italiana": ["Domino's Pizza", "Napoli"],
    "Pollo y alitas": ["KFC", "Las Aliadas"],
    "Sándwiches": ["Subway"],
    "Postres y helados": ["Dairy Queen"],
}

app = Flask(__name__)


def to_number(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def read_csv(path):
    with open(path, encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def load_items():
    items = []
    for path in sorted(glob.glob(os.path.join(BASE_DIR, "*.csv"))):
        for row in read_csv(path):
            # chipotle_builder.csv tiene otro formato; se carga aparte en load_builder()
            if not row.get("restaurante") or not row.get("producto"):
                continue
            item = {
                "restaurante": row["restaurante"].strip(),
                "categoria": (row.get("categoria") or "").strip(),
                "producto": row["producto"].strip(),
                "porcion": (row.get("porcion") or "").strip(),
            }
            for field in NUM_FIELDS:
                item[field] = to_number(row.get(field))
            item["key"] = item["restaurante"] + "|" + item["producto"]
            items.append(item)
    return items


def load_builder():
    path = os.path.join(BASE_DIR, "chipotle_builder.csv")
    if not os.path.exists(path):
        return []
    parts = []
    for row in read_csv(path):
        part = {"id": row["id"], "grupo": row["grupo"], "componente": row["componente"]}
        for field in NUM_FIELDS:
            part[field] = to_number(row.get(field))
        parts.append(part)
    return parts


ITEMS = load_items()
BUILDER = load_builder()


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/data")
def api_data():
    presentes = {item["restaurante"] for item in ITEMS}
    tipos = [
        {"tipo": tipo, "restaurantes": [r for r in restaurantes if r in presentes]}
        for tipo, restaurantes in TIPOS.items()
    ]
    return jsonify({"tipos": [t for t in tipos if t["restaurantes"]], "items": ITEMS, "chipotle": BUILDER})


if __name__ == "__main__":
    app.run(debug=True)
