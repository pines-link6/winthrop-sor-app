# Winthrop Don't Walk By – Microsoft Forms SOR Batch App

This is a separate application for the Winthrop Microsoft Forms SOR destination.

## Files
- `app.py` – Flask app and Playwright Microsoft Forms automation
- `templates/index.html` – batch preparation/review UI
- `requirements.txt`
- `Dockerfile`

## What it does
- Lets the user prepare 10–40 separate observation records, with a separate one-record test option for initial verification.
- Randomly pre-fills each description from a 225-phrase positive prompt bank covering housekeeping, PPE, access, lifting and safe working (English and Romanian), with a per-record regenerate button.
- Uses the Microsoft Forms fields recorded from the supplied form screenshots:
  - Your name
  - Company
  - Date
  - Location
  - Nature of Observation Positive or Negative
  - Nature of Observation
  - Observation Description
  - Intervention matrix (Action Taken / Feedback Given / Manager Informed)
  - Details of intervention
  - Type of Observation
- Randomly preselects Anonymous, anonymous or Anon when the page opens; the selected format is visible, editable, and used consistently throughout the batch.
- Defaults each observation location to External.
- Pre-fills Details of intervention with a varied N/A entry; the user can replace it with actual intervention details.
- Uses one batch-level confirmation checkbox after all records have been reviewed.
- Submits records sequentially to the official Microsoft Form.
- Counts a submission only when a Microsoft Forms confirmation message is visible.
- Stops on an uncertain result rather than blindly retrying and potentially duplicating an SOR.

**The app supplies randomly selected positive wording prompts, but these are not evidence of events.** The user must verify, edit and submit only descriptions that match genuine events personally witnessed or independently verified. Do not submit generic example text as if it were an event that occurred.

## GitHub / Render deployment
1. Use the separate GitHub repository `winthrop-sor-app`.
2. Replace the repository files with this package, keeping `index.html` inside `templates/`.
3. In Render, use the existing Winthrop Web Service connected to this repository.
4. Runtime: Docker. Branch: `main`. Auto-Deploy: On Commit.
5. Ensure this environment variable exists:
   `WINTHROP_FORM_URL=https://forms.cloud.microsoft/pages/responsepage.aspx?id=dUaehQ5Ly0ucFIpVl4wrX-Kdix2lwfZItDDsyeebhi1UNlFRM1ZUTU9ZSEFLNURCRlhaNDhBRzQwMy4u&route=shorturl`
6. Deploy and check `/health`.

## Important first test
The Microsoft Forms page is rendered dynamically and its internal markup can change. The automation is based on the saved screenshots and accessible question labels, but it must be tested with ONE genuine observation first. Verify that the entry appears in the form owner's response results before running a larger batch. If the app stops on a field locator or confirmation check, send the exact status/error text and we can adjust the selectors. Do not run a large batch until the one-record test has been confirmed.

## Security / operation
- Keep the Render service private to intended users; anyone with the app URL may otherwise be able to submit reports.
- Use a strong `SECRET_KEY` environment variable.
- The in-memory job status is not persistent; a Render restart clears current progress.
- Browser automation runs on the Render server, not in the user's browser.
