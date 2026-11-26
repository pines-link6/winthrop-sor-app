import os
import re
import threading
import time
import uuid
from datetime import date, datetime
from flask import Flask, render_template, request, jsonify
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "replace-this-secret")
FORM_URL = os.environ.get(
    "WINTHROP_FORM_URL",
    "https://forms.cloud.microsoft/pages/responsepage.aspx?id=dUaehQ5Ly0ucFIpVl4wrX-Kdix2lwfZItDDsyeebhi1UNlFRM1ZUTU9ZSEFLNURCRlhaNDhBRzQwMy4u&route=shorturl"
).strip()

MIN_BATCH = 10
MAX_BATCH = 40
JOBS = {}
JOBS_LOCK = threading.Lock()

COMPANIES = ["Winthrop", "Sundstrom", "TCK", "RENTA", "GLENT", "Constlog",
             "Nordec", "CSK", "Crown", "Cramo", "Wingate", "Other"]
LOCATIONS = ["External", "First Floor", "Second Floor", "Roof", "Admin", "Third Floor"]
NATURES = ["Positive Observation", "Negative Observation"]
FURTHER_NATURES = ["At Risk Observation", "Near Miss", "Positive Observation"]
OBSERVATION_TYPES = [
    "HRA (High Risk Activity) + Significant Exposure",
    "MRA (Medium Risk Activity) (cutting, access, hand placement, Material Storage/Housekeeping)",
    "General Category"
]

def set_job(job_id, **updates):
    with JOBS_LOCK:
        if job_id in JOBS:
            JOBS[job_id].update(updates)
            JOBS[job_id]["updated"] = time.time()

def get_question(page, title):
    # Microsoft Forms currently exposes each question as a questionItem.
    q = page.locator('[data-automation-id="questionItem"]').filter(has_text=title).first
    if q.count() == 0:
        raise RuntimeError(f"Could not find the Microsoft Forms question: {title}")
    return q

def fill_text_question(page, title, value, date_field=False):
    q = get_question(page, title)
    controls = q.locator('input:not([type="radio"]):not([type="checkbox"]), textarea')
    if controls.count() == 0:
        raise RuntimeError(f"No text input found for question: {title}")
    control = controls.first
    if date_field:
        # Forms date questions may render as a native date input or a localized text input.
        input_type = (control.get_attribute("type") or "").lower()
        date_value = datetime.strptime(value, "%Y-%m-%d")
        control.fill(date_value.strftime("%Y-%m-%d") if input_type == "date"
                     else date_value.strftime("%d/%m/%Y"))
    else:
        control.fill(str(value))

def choose_radio(page, question_title, option):
    q = get_question(page, question_title)
    # Prefer the accessible radio name; this avoids depending on generated IDs.
    radio = q.get_by_role("radio", name=option, exact=True)
    if radio.count():
        radio.first.check(force=True)
        return
    label = q.get_by_text(option, exact=True)
    if label.count():
        label.first.click()
        return
    raise RuntimeError(f"Could not select '{option}' for question: {question_title}")

def choose_company(page, company):
    q = get_question(page, "Company")
    radio = q.get_by_role("radio", name=company, exact=True)
    if radio.count():
        radio.first.check(force=True)
        return
    if company == "Other":
        raise RuntimeError("Company 'Other' requires a separately supplied employer name; this app currently supports the listed companies only.")
    label = q.get_by_text(company, exact=True)
    if label.count():
        label.first.click()
        return
    raise RuntimeError(f"Company option not found: {company}")

def fill_intervention_matrix(page, record):
    q = get_question(page, "Intervention")
    # The Microsoft Forms matrix presents three rows and two columns (Yes/No).
    # Radio controls are ordered row-wise: Action Taken, Feedback Given, Manager Informed.
    radios = q.get_by_role("radio")
    if radios.count() < 6:
        raise RuntimeError("The Intervention matrix did not expose the expected six Yes/No radio buttons.")
    values = [
        record["action_taken"],
        record["feedback_given"],
        record["manager_informed"],
    ]
    for row, value in enumerate(values):
        index = row * 2 + (0 if value == "Yes" else 1)
        radios.nth(index).check(force=True)

def wait_for_form(page):
    page.goto(FORM_URL, wait_until="domcontentloaded", timeout=90000)
    page.wait_for_selector('[data-automation-id="questionItem"]', timeout=60000)
    # Wait for the first required question to become interactable.
    get_question(page, "Your name")

def submit_one(page, record):
    fill_text_question(page, "Your name", record["name"])
    choose_company(page, record["company"])
    fill_text_question(page, "Date", record["date"], date_field=True)
    choose_radio(page, "Location", record["location"])
    choose_radio(page, "Nature of Observation Positive or Negative", record["nature"])
    choose_radio(page, "Nature of Observation", record["further_nature"])
    fill_text_question(page, "Observation Description", record["description"])
    fill_intervention_matrix(page, record)
    fill_text_question(page, "Details of intervention", record["intervention_details"])
    choose_radio(page, "Type of Observation", record["type"])

    submit = page.get_by_role("button", name=re.compile(r"^Submit$", re.I))
    if not submit.count():
        submit = page.get_by_text("Submit", exact=True)
    submit.first.click()

    # Count a record as successful only after Microsoft Forms displays its
    # response confirmation. If the page does not confirm, stop to avoid
    # blindly retrying and creating duplicate reports.
    try:
        page.get_by_text(re.compile(r"Your response was submitted", re.I)).wait_for(timeout=30000)
    except PlaywrightTimeoutError:
        try:
            page.get_by_text(re.compile(r"Thank you", re.I)).wait_for(timeout=5000)
        except PlaywrightTimeoutError:
            raise RuntimeError("Microsoft Forms did not show a submission confirmation. The result is uncertain; automation stopped to avoid duplicates.")

def run_batch(job_id, records):
    browser = None
    try:
        if not FORM_URL.startswith("https://"):
            raise RuntimeError("WINTHROP_FORM_URL is missing or invalid.")
        set_job(job_id, status="running", message="Starting Microsoft Forms session…", current=0, total=len(records))
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True, args=["--no-sandbox", "--disable-dev-shm-usage"])
            context = browser.new_context(viewport={"width": 1440, "height": 1100})
            page = context.new_page()
            page.set_default_timeout(20000)

            for index, record in enumerate(records, start=1):
                set_job(job_id, message=f"{index}/{len(records)} — opening the form…", current=index-1)
                wait_for_form(page)
                set_job(job_id, message=f"{index}/{len(records)} — completing verified observation…", current=index-1)
                submit_one(page, record)
                set_job(job_id, current=index, message=f"{index}/{len(records)} — Microsoft Forms confirmed submission.")
                if index < len(records):
                    time.sleep(1.5)

            set_job(job_id, status="complete", message=f"Completed: {len(records)} of {len(records)} observations confirmed by Microsoft Forms.", current=len(records))
            context.close()
    except Exception as exc:
        with JOBS_LOCK:
            job = JOBS.get(job_id, {})
            current = job.get("current", 0)
        set_job(job_id, status="error", message=f"Stopped after {current} confirmed submissions: {type(exc).__name__}: {exc}", current=current)
    finally:
        if browser:
            try:
                browser.close()
            except Exception:
                pass

@app.get("/")
def index():
    return render_template("index.html", today=date.today().isoformat(),
                           companies=COMPANIES, locations=LOCATIONS,
                           natures=NATURES, further_natures=FURTHER_NATURES,
                           observation_types=OBSERVATION_TYPES,
                           min_batch=MIN_BATCH, max_batch=MAX_BATCH)

@app.post("/api/start")
def start():
    payload = request.get_json(silent=True) or {}
    records = payload.get("records")
    if not isinstance(records, list) or not 1 <= len(records) <= MAX_BATCH:
        return jsonify(error=f"Submit one test record or a batch of up to {MAX_BATCH} real observations."), 400

    required = ["name", "company", "date", "location", "nature", "further_nature",
                "description", "action_taken", "feedback_given", "manager_informed",
                "intervention_details", "type"]
    cleaned = []
    for i, rec in enumerate(records, 1):
        if not isinstance(rec, dict):
            return jsonify(error=f"Observation {i} is invalid."), 400
        if not rec.get("witnessed") or not rec.get("reviewed"):
            return jsonify(error=f"Observation {i} must be confirmed as genuine and reviewed."), 400
        missing = [k for k in required if not str(rec.get(k, "")).strip()]
        if missing:
            return jsonify(error=f"Observation {i} is missing: {', '.join(missing)}."), 400
        if rec["company"] not in COMPANIES or rec["location"] not in LOCATIONS:
            return jsonify(error=f"Observation {i} has an invalid company or location."), 400
        if rec["nature"] not in NATURES or rec["further_nature"] not in FURTHER_NATURES:
            return jsonify(error=f"Observation {i} has an invalid observation classification."), 400
        if rec["type"] not in OBSERVATION_TYPES:
            return jsonify(error=f"Observation {i} has an invalid type."), 400
        for field in ("action_taken", "feedback_given", "manager_informed"):
            if rec[field] not in ("Yes", "No"):
                return jsonify(error=f"Observation {i}: {field} must be Yes or No."), 400
        try:
            datetime.strptime(rec["date"], "%Y-%m-%d")
        except ValueError:
            return jsonify(error=f"Observation {i} has an invalid date."), 400
        cleaned.append({k: str(rec[k]).strip() for k in required} | {
            "witnessed": True, "reviewed": True
        })

    job_id = str(uuid.uuid4())
    with JOBS_LOCK:
        JOBS[job_id] = {"id": job_id, "status": "queued", "message": "Queued…",
                        "current": 0, "total": len(cleaned), "updated": time.time()}
    thread = threading.Thread(target=run_batch, args=(job_id, cleaned), daemon=True)
    thread.start()
    return jsonify(job_id=job_id), 202

@app.get("/api/status/<job_id>")
def status(job_id):
    with JOBS_LOCK:
        job = JOBS.get(job_id)
        if not job:
            return jsonify(error="Submission job not found. The server may have restarted."), 404
        return jsonify(job)

@app.get("/health")
def health():
    return jsonify(status="ok", app="winthrop-microsoft-forms-sor")

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "10000")))
