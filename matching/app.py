import json
import random
import uuid
from pathlib import Path
from flask import Flask, render_template, request, jsonify

app = Flask(__name__)

# ─── Load morphs & clusters from JSON ──────────────────────────────────────────
DATA_PATH = Path(__file__).parent / "data.json"
# ─── Load fixed list of pairs from JSON ────────────────────────────────────────
with DATA_PATH.open(encoding="utf-8") as f:
    data = json.load(f)

# data["pairs"] should be a list of [leftWord, rightWord]
all_pairs = [
    {"left": left, "right": right}
    for left, right in data["pairs"]
]

def make_pairs(n, exclude_words=None):
    """
    Return up to n pairs whose left & right words
    are not in exclude_words, and also unique within themselves.
    """
    exclude = set(exclude_words or [])
    candidates = all_pairs.copy()
    selected = []
    used = set(exclude)

    while len(selected) < n and candidates:
        # filter out any pair touching a used word
        avail = [p for p in candidates
                 if p["left"] not in used and p["right"] not in used]
        if not avail:
            break
        p = random.choice(avail)
        selected.append(p)
        # mark both words as used
        used.add(p["left"])
        used.add(p["right"])
        # drop any candidate that now conflicts
        candidates = [q for q in candidates
                      if q["left"] not in used and q["right"] not in used]

    # wrap with IDs
    out = []
    for p in selected:
        out.append({
            "id": str(uuid.uuid4()),
            "left": p["left"],
            "right": p["right"]
        })
    return out

@app.route("/")
def index():
    # our template is just the 8 empty slots
    return render_template("game.html")

@app.route("/new_pairs", methods=["GET","POST"])
def new_pairs():
    if request.method == "POST":
        data = request.get_json() or {}
        n = int(data.get("n", 2))
        exclude = data.get("exclude", [])
    else:
        n = int(request.args.get("n", 2))
        exclude = []
    pairs = make_pairs(n, exclude)
    return jsonify(pairs=pairs)

if __name__ == "__main__":
    app.run(debug=True)
