# Winthrop Don't Walk By – SOR preparation app

## Files
- `app.py`
- `templates/index.html`
- `requirements.txt`
- `Dockerfile`

## GitHub repository
Create a separate repository named `winthrop-sor-app`. Do not upload these files to `csk-sor-iphone`.

Upload the project structure exactly as shown above. `index.html` must be inside the `templates` folder.

## Render
Create a new Web Service connected to `winthrop-sor-app`.
- Runtime: Docker
- Branch: main
- Auto-Deploy: On Commit
- Environment variable: `WINTHROP_FORM_URL` = `https://forms.cloud.microsoft/pages/responsepage.aspx?id=dUaehQ5Ly0ucFIpVl4wrX-Kdix2lwfZItDDsyeebhi1UNlFRM1ZUTU9ZSEFLNURCRlhaNDhBRzQwMy4u&route=shorturl`

No additional Start Command is required; the Dockerfile starts Gunicorn.

## Usage
Open the Render URL, enter each real observation, add it to the batch, and tick both verification boxes for every record. Export CSV for review/audit, then use Open Microsoft Forms to enter the verified information into the official form.

This version deliberately does not auto-submit fabricated positive observations. The old 200-example file is not wired into submissions; examples are prompts only and must never be treated as evidence that an event occurred.
