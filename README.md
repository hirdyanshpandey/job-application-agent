# Job Agent

Local CLI for tailoring factual résumé PDFs, tracking applications, sending a résumé through Gmail, and sending one follow-up after seven days. Résumé tailoring scores skills and experience bullets against the job description and reorders them within each section.

## Setup

Use Python 3.11 or later. Install with `python -m pip install -r requirements.txt`. Copy `profile.example.json` to `private/profile.json` and fill it with verified facts. Keep candidate data and generated PDFs in `private/`.

Create a job JSON from `job.example.json`. Use the employer's official application link and leave email empty for form-only roles. Check remote geography or relocation and sponsorship eligibility before applying.

- `python agent.py prepare job.json` creates a role-specific PDF and prints the application ID.
- `python agent.py apply ID` sends to the supplied recruiting email or prints the official portal URL for manual submission and verification.
- `python agent.py status` shows application states and due follow-ups.
- `python agent.py follow-up ID` sends one threaded email after seven days. Check Gmail for a reply first.
- `python agent.py close ID` closes a tracked application.

Email requires `GMAIL_ADDRESS` and `GMAIL_APP_PASSWORD` in the environment. App password availability depends on account settings. If delivery is uncertain, check Gmail Sent. The tracker keeps the in-progress state to prevent an accidental duplicate.

Portal discovery, portal submission, inbox reply detection, and automatic scheduling require additional integrations.

## Browser dashboard

On Windows, install Python 3.11+ and double-click `start-windows.bat`.
On other platforms, install requirements and run
`python -m streamlit run dashboard.py --server.address 127.0.0.1`.
Save your candidate profile, paste the official job details, and generate the PDF.
The application list displays job IDs for sending and follow-up.
