"""Local browser interface for the job agent."""
import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path

import streamlit as st

from agent import PRIVATE

st.set_page_config(page_title="Job Agent", page_icon="📄")
st.title("Job Agent")
PRIVATE.mkdir(mode=0o700, exist_ok=True)
profile = PRIVATE / "profile.json"
example = Path(__file__).with_name("profile.example.json")


def run(*args):
    result = subprocess.run(
        [sys.executable, str(Path(__file__).with_name("agent.py")), *args],
        capture_output=True, text=True, timeout=45,
    )
    if result.returncode:
        st.error(result.stderr.strip() or result.stdout.strip())
    return result.stdout.strip() if result.returncode == 0 else ""


with st.expander("Candidate profile", expanded=not profile.exists()):
    raw = st.text_area("Profile JSON", (profile if profile.exists() else example).read_text(encoding="utf-8"), height=225)
    if st.button("Save profile"):
        try:
            data = json.loads(raw)
            if not isinstance(data, dict) or not {"name", "contact", "pitch", "skills", "experience"} <= data.keys():
                raise ValueError("Include name, contact, pitch, skills and experience.")
            profile.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
            st.success("Profile saved locally.")
        except ValueError as exc:
            st.error(str(exc))

with st.form("job"):
    st.subheader("Prepare an application")
    company = st.text_input("Employer")
    title = st.text_input("Role")
    url = st.text_input("Official job URL")
    email = st.text_input("Published recruiting email (optional)")
    description = st.text_area("Job description")
    if st.form_submit_button("Generate résumé"):
        if not profile.exists() or not all(x.strip() for x in (company, title, url, description)):
            st.error("Save your profile and enter the employer, role, URL, and description.")
        else:
            job = dict(company=company.strip(), title=title.strip(), url=url.strip(),
                       email=email.strip(), description=description.strip())
            with tempfile.TemporaryDirectory() as folder:
                source = Path(folder) / "job.json"
                source.write_text(json.dumps(job), encoding="utf-8")
                output = run("prepare", str(source))
            if output:
                st.session_state["last_id"] = output.split()[0]

if job_id := st.session_state.get("last_id"):
    st.download_button("Download tailored résumé", (PRIVATE / f"{job_id}.pdf").read_bytes(),
                       file_name=f"Resume-{job_id}.pdf", mime="application/pdf")

st.subheader("Applications")
status = run("status")
st.code(status or "No applications yet.", language=None)
application = st.text_input("Application ID", value=st.session_state.get("last_id", ""))
apply, follow, close = st.columns(3)
action = None
if apply.button("Apply"):
    action = "apply"
if follow.button("Send follow-up"):
    action = "follow-up"
if close.button("Close application"):
    action = "close"
if action:
    if not re.fullmatch(r"[a-f0-9]{12}", application):
        st.error("Enter a valid application ID.")
    else:
        output = run(action, application)
        if output:
            st.info(output)
