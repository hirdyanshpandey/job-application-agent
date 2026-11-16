"""Local job application tracker, résumé generator, and opt-in Gmail sender."""
import argparse
import hashlib
import json
import os
import smtplib
import sqlite3
import ssl
from datetime import datetime, timedelta, timezone
from email.message import EmailMessage
from email.utils import formatdate, make_msgid, parseaddr
from pathlib import Path
from urllib.parse import urlparse
from xml.sax.saxutils import escape

PRIVATE = Path(__file__).resolve().parent / "private"


def terms(text):
    import re
    return set(re.findall(r"[a-z0-9+#.]+", text.lower()))


def load(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def resume(profile, description, path):
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.platypus import Paragraph, SimpleDocTemplate

    styles = getSampleStyleSheet()
    keywords = terms(description)
    content = []

    def add(value, style="BodyText"):
        content.append(Paragraph(escape(value), styles[style]))

    add(profile["name"], "Title")
    add(profile["contact"])
    add("Technical skills", "Heading2")
    skills = sorted(profile["skills"], key=lambda item: -len(terms(item) & keywords))
    add(", ".join(skills))
    add("Experience", "Heading2")
    for role in profile["experience"]:
        add(role["title"] + " | " + role["company"] + " | " + role["dates"], "Heading3")
        ordered = sorted(role["bullets"], key=lambda item: -len(terms(item) & keywords))
        for bullet in ordered:
            add(bullet)
    if profile.get("education"):
        add("Education", "Heading2")
        for item in profile["education"]:
            add(item)
    SimpleDocTemplate(str(path), leftMargin=42, rightMargin=42).build(content)


def send(to, subject, body, attachment=None, original=None):
    sender = os.environ["GMAIL_ADDRESS"]
    if parseaddr(to)[1] != to or "@" not in to:
        raise ValueError("Enter the exact published recruiting email.")
    message = EmailMessage()
    message["From"], message["To"], message["Subject"] = sender, to, subject
    message["Date"], message["Message-ID"] = formatdate(usegmt=True), make_msgid()
    if original:
        message["In-Reply-To"] = original
        message["References"] = original
    message.set_content(body)
    if attachment:
        message.add_attachment(attachment.read_bytes(), maintype="application",
                               subtype="pdf", filename="Resume.pdf")
    with smtplib.SMTP_SSL("smtp.gmail.com", 465, context=ssl.create_default_context(), timeout=25) as smtp:
        smtp.login(sender, os.environ["GMAIL_APP_PASSWORD"])
        smtp.send_message(message)
    return message["Message-ID"]


def now():
    return datetime.now(timezone.utc)


def main():
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    prepare = sub.add_parser("prepare")
    prepare.add_argument("job")
    prepare.add_argument("--profile", default=str(PRIVATE / "profile.json"))
    for command in ("apply", "follow-up", "close"):
        sub.add_parser(command).add_argument("id")
    sub.add_parser("status")
    args = parser.parse_args()
    PRIVATE.mkdir(mode=0o700, exist_ok=True)
    with sqlite3.connect(PRIVATE / "applications.db") as db:
        db.execute("""CREATE TABLE IF NOT EXISTS jobs (
            id TEXT PRIMARY KEY, data TEXT NOT NULL, status TEXT NOT NULL,
            sent TEXT, message_id TEXT
        )""")
        if args.command == "prepare":
            job, profile = load(args.job), load(args.profile)
            url = urlparse(job["url"])
            if url.scheme != "https" or not url.hostname:
                raise ValueError("Provide the official HTTPS application URL.")
            job["candidate"] = profile["name"]
            job["pitch"] = profile["pitch"]
            job_id = hashlib.sha256(job["url"].encode()).hexdigest()[:12]
            db.execute("BEGIN IMMEDIATE")
            existing = db.execute("SELECT status FROM jobs WHERE id=?", (job_id,)).fetchone()
            if existing and existing[0] != "prepared":
                raise SystemExit(f"{job_id} already tracked as {existing[0]}")
            resume(profile, job["description"], PRIVATE / f"{job_id}.pdf")
            db.execute("INSERT INTO jobs VALUES (?, ?, 'prepared', NULL, NULL) "
                       "ON CONFLICT(id) DO UPDATE SET data=excluded.data", (job_id, json.dumps(job)))
            print(job_id, PRIVATE / f"{job_id}.pdf", job["url"])
            return
        if args.command == "status":
            for job_id, data, state, sent in db.execute("SELECT id,data,status,sent FROM jobs"):
                job = json.loads(data)
                due = state == "sent" and now() - datetime.fromisoformat(sent) >= timedelta(days=7)
                print(job_id, job["company"], job["title"], state, "follow-up due" if due else "")
            return
        db.execute("BEGIN IMMEDIATE")
        row = db.execute("SELECT data,status,sent,message_id FROM jobs WHERE id=?", (args.id,)).fetchone()
        if not row:
            raise SystemExit("Unknown application ID")
        job, state, sent_at, original = json.loads(row[0]), *row[1:]
        if args.command == "close":
            db.execute("UPDATE jobs SET status='closed' WHERE id=?", (args.id,))
            return
        if args.command == "apply" and state == "prepared":
            if not job.get("email"):
                print("Complete the employer form and any verification here:", job["url"])
                return
            body = (f"Hi {job['company']} recruiting team,\n\n"
                    f"I’m applying for {job['title']}. {job['pitch']} "
                    "My résumé is attached.\n\n"
                    f"Best,\n{job['candidate']}")
            send_state, final_state = "sending", "sent"
            attachment = PRIVATE / f"{args.id}.pdf"
        elif args.command == "follow-up" and state == "sent":
            if now() - datetime.fromisoformat(sent_at) < timedelta(days=7):
                raise SystemExit("The follow-up is due seven days after sending.")
            body = (f"Hi {job['company']} recruiting team,\n\n"
                    f"I’m following up on my application for {job['title']}. "
                    "Please let me know if I can provide any additional details.\n\n"
                    f"Best,\n{job['candidate']}")
            send_state, final_state = "following-up", "followed-up"
            attachment = None
        else:
            raise SystemExit(f"Action unavailable for status {state}")
        if not os.environ.get("GMAIL_ADDRESS") or not os.environ.get("GMAIL_APP_PASSWORD"):
            raise SystemExit("Set the Gmail environment variables before sending.")
        db.execute("UPDATE jobs SET status=? WHERE id=?", (send_state, args.id))
        db.commit()
        subject = f"Application for {job['title']} | {job['candidate']}"
        try:
            message_id = send(job["email"], ("Re: " if original else "") + subject,
                              body, attachment, original)
        except Exception as exc:
            raise SystemExit(f"Delivery could not be confirmed. Check Gmail Sent before retrying. {exc}") from exc
        db.execute("UPDATE jobs SET status=?,sent=?,message_id=? WHERE id=?",
                   (final_state, now().isoformat(), message_id, args.id))
        print(final_state, job["company"], job["title"])


if __name__ == "__main__":
    main()
