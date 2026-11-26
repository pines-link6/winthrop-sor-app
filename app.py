import csv
import io
import os
import uuid
from datetime import date
from flask import Flask, render_template, request, jsonify, send_file
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "change-this-for-production")
FORM_URL = os.environ.get("WINTHROP_FORM_URL", "").strip()

# The app is an observation preparation and audit tool. It does not fabricate
# events or automatically submit unverified records to Microsoft Forms.

@app.get("/")
def index():
    return render_template("index.html", today=date.today().isoformat(),
                           form_url=FORM_URL)

@app.post("/api/export")
def export():
    payload = request.get_json(silent=True) or {}
    records = payload.get("records", [])
    if not records:
        return jsonify(error="No observations supplied."), 400

    required = ["name", "company", "date", "location", "nature",
                "further_nature", "description", "action_taken",
                "feedback_given", "manager_informed", "intervention_details",
                "type"]
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=required)
    writer.writeheader()

    for i, record in enumerate(records, 1):
        if not record.get("witnessed") or not record.get("reviewed"):
            return jsonify(error=f"Observation {i} must be confirmed as genuine and reviewed."), 400
        missing = [field for field in required if not str(record.get(field, "")).strip()]
        if missing:
            return jsonify(error=f"Observation {i} is missing: {', '.join(missing)}"), 400
        writer.writerow({field: record.get(field, "") for field in required})

    mem = io.BytesIO(output.getvalue().encode("utf-8-sig"))
    mem.seek(0)
    return send_file(mem, mimetype="text/csv", as_attachment=True,
                     download_name="winthrop_sor_records.csv")

@app.get("/health")
def health():
    return jsonify(status="ok", app="winthrop-sor-preparation")

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "10000")))
