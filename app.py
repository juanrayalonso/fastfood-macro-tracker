import csv
import glob
import os
import re

from flask import Flask, jsonify, render_template

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
NUM_FIELDS = ["kcal", "proteina_g", "carbs_g", "grasa_g", "azucar_g", "fibra_g", "sodio_mg", "precio_mxn"]

# Tipo de restaurante -> restaurantes, en el orden en que se muestran
TIPOS = {
    "Hamburguesas": ["McDonald's", "Carl's Jr."],
    "Mexicana": ["Chipotle", "Taco Palenque", "Doña Tota"],
    "Pizza e italiana": ["Domino's Pizza", "Napoli"],
    "Pollo y alitas": ["KFC", "Las Aliadas"],
    "Sándwiches": ["Subway"],
    "Postres y helados": ["Dairy Queen"],
    "Cafeterías": ["Starbucks", "Tim Hortons"],
}

# Clase de cada platillo: comida, bebida, salsa (salsas, condimentos y extras) o ingrediente
# (piezas sueltas de un armado, como las proteínas de Chipotle). Solo "comida" entra a los
# rankings, para que una salsa o un topping no infle "más proteína por caloría".
CAT_BEBIDA = re.compile(r"bebida|mccaf|cerveza|caguama|coctel|cubeta|whisky|shots?$|en tarros", re.I)
CAT_SALSA = re.compile(r"salsa|condimento|extras|toppings", re.I)
CAT_INGREDIENTE = {("Chipotle", "Proteínas"), ("Chipotle", "Formatos"), ("Chipotle", "Arroz y frijoles"),
                   ("Chipotle", "Toppings"), ("Tim Hortons", "Ensaladas (componentes)")}
PROD_SALSA = re.compile(r"^(salsa|aderezo|guacamole(\s+solo)?$|crema$|queso (blanco|extra)|ketchup|mayonesa|mostaza)|"
                        r"\(salsa\)|^extra[: ]|^cup ranch|\bsauce\b", re.I)
PROD_BEBIDA = re.compile(r"cerveza|caguam|bebidas|cubeta|refresco|\bcoffee\b|\bjugo\b|\bshake\b|malteada|"
                         r"frappuccino|limonada|lemonade|refresher|smoothie", re.I)
PROD_COMIDA = re.compile(r"\bkilo\b|alitas", re.I)
# Platillos a los que les sugerimos salsa (opcional)
CON_SALSA = re.compile(r"hamburguesa|burger|boneless|aliadas \d|alitas|nugget|tender|chicken|pollo|mccrispy|"
                       r"papas|fries|muslo|ribs|costilla|s[aá]ndwich|wrap|filet|aros de cebolla|dedos de queso|"
                       r"onion rings|k-tiras|crispy", re.I)
ES_SALSA = re.compile(r"salsa|sauce|aderezo|ranch|ketchup|mayo|mostaza|mustard|honey|bbq|chil+i\b|blue cheese|"
                      r"jalape|guacamole|chipotle|b[uú]falo", re.I)

NO_ES_SALSA = re.compile(r"helado|pollo|costilla|boneless|tocino|jam[oó]n", re.I)


def clase_de(item):
    rest, cat, prod = item["restaurante"], item["categoria"], item["producto"]
    if CAT_BEBIDA.search(cat):
        return "bebida"
    if (rest, cat) in CAT_INGREDIENTE:
        return "salsa" if PROD_SALSA.search(prod) else "ingrediente"
    if CAT_SALSA.search(cat) or PROD_SALSA.search(prod):
        return "salsa"
    if PROD_BEBIDA.search(prod) and not PROD_COMIDA.search(prod):
        return "bebida"
    return "comida"

app = Flask(__name__)


def to_number(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def datos_posibles(item):
    # Proteína + carbos + grasa no pueden pesar más que la porción (p. ej. 190 g de proteína en 130 g)
    m = re.fullmatch(r"(\d+(?:\.\d+)?)\s*g", item["porcion"].strip())
    if not m:
        return True
    return item["proteina_g"] + item["carbs_g"] + item["grasa_g"] <= float(m.group(1)) * 1.05


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
            if not datos_posibles(item):
                app.logger.warning("Datos imposibles, se omite: %s %s", item["restaurante"], item["producto"])
                continue
            item["key"] = item["restaurante"] + "|" + item["producto"] + "|" + item["porcion"]
            item["clase"] = clase_de(item)
            items.append(item)
    con_salsas = {i["restaurante"] for i in items if i["clase"] == "salsa" and ES_SALSA.search(i["producto"])}
    for item in items:
        item["es_salsa"] = item["clase"] == "salsa" and bool(ES_SALSA.search(item["producto"])) \
            and not NO_ES_SALSA.search(item["producto"])
        item["sugiere_salsa"] = item["clase"] == "comida" and item["restaurante"] in con_salsas \
            and bool(CON_SALSA.search(item["producto"] + " " + item["categoria"]))
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
