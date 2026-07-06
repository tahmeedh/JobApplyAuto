"""Render a ResumePayload dict to styled HTML (resume + cover letter).

The CSS mirrors career-ops/tahmeed/generate-resume.mjs — the proven house
style — so tailored resumes look identical to the hand-built one.
"""
from html import escape

_CSS = """
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body {
    font-family: 'Helvetica Neue', Arial, sans-serif;
    font-size: 10.5pt;
    line-height: 1.45;
    color: #1a1a1a;
    padding: 28px 36px;
    max-width: 820px;
    margin: 0 auto;
  }
  h1 { font-size: 20pt; font-weight: 700; letter-spacing: 0.5px; margin-bottom: 2px; }
  .subtitle { font-size: 11pt; color: #444; margin-bottom: 4px; }
  .contact { font-size: 9.5pt; color: #333; margin-bottom: 14px; }
  .contact a { color: #1a6fb5; text-decoration: none; }
  h2 {
    font-size: 11pt; font-weight: 700; text-transform: uppercase;
    letter-spacing: 1px; color: #1a6fb5; border-bottom: 1.5px solid #1a6fb5;
    padding-bottom: 2px; margin: 14px 0 7px;
  }
  .role-line { display: flex; justify-content: space-between; align-items: baseline; }
  .company { font-weight: 700; }
  .dates { font-size: 9.5pt; color: #555; white-space: nowrap; }
  .jobtitle { font-style: italic; color: #444; font-size: 10pt; margin-bottom: 4px; }
  ul { padding-left: 16px; margin-top: 3px; }
  li { margin-bottom: 2px; font-size: 10pt; }
  .skills-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 4px 20px; }
  .skill-row strong { color: #1a1a1a; font-size: 10pt; }
  .skill-row span { color: #333; font-size: 10pt; }
  .cert-list { font-size: 10pt; color: #333; }
  .summary { font-size: 10pt; color: #222; }
  .cl-body p { margin-bottom: 12px; font-size: 11pt; }
"""


def _contact_line(contact: dict) -> str:
    parts = [
        escape(contact.get("location", "")),
        escape(contact.get("phone", "")),
        f'<a href="mailto:{escape(contact.get("email", ""))}">{escape(contact.get("email", ""))}</a>',
        f'<a href="https://{escape(contact.get("linkedin", ""))}">LinkedIn</a>',
        f'<a href="https://{escape(contact.get("website", ""))}">{escape(contact.get("website", ""))}</a>',
    ]
    return " &nbsp;|&nbsp; ".join(p for p in parts if p)


def render_resume_html(payload: dict) -> str:
    contact = payload["contact"]
    meta = payload["meta"]

    skills_html = "".join(
        f'<div class="skill-row"><strong>{escape(s["label"])}</strong><br>'
        f'<span>{escape(s["value"])}</span></div>'
        for s in payload["skills"]
    )

    experience_html = ""
    for job in payload["experience"]:
        bullets = "".join(f"<li>{escape(b)}</li>" for b in job["bullets"])
        experience_html += f"""
<div class="role-line" style="margin-top:8px">
  <span class="company">{escape(job["company"])}</span>
  <span class="dates">{escape(job["dates"])}</span>
</div>
<div class="jobtitle">{escape(job["title"])}</div>
<ul>{bullets}</ul>"""

    edu = payload["education"]

    return f"""<!DOCTYPE html>
<html lang="en">
<head><meta charset="UTF-8"><style>{_CSS}</style></head>
<body>

<h1>{escape(contact["name"])}</h1>
<div class="subtitle">{escape(meta["subtitle"])}</div>
<div class="contact">{_contact_line(contact)}</div>

<h2>Professional Summary</h2>
<div class="summary">{escape(payload["summary"])}</div>

<h2>Technical Skills</h2>
<div class="skills-grid">{skills_html}</div>

<h2>Professional Experience</h2>
{experience_html}

<h2>Education</h2>
<div class="role-line">
  <span><strong>{escape(edu["institution"])}</strong> — {escape(edu["degree"])}, {escape(edu["gpa"])} GPA</span>
</div>
<div style="font-size:9.5pt;color:#555;margin-top:2px">{escape(edu["coursework"])}</div>

<h2>Certifications &amp; Recognition</h2>
<div class="cert-list">{escape(payload["certifications"])}</div>
<div class="cert-list" style="margin-top:3px">{escape(payload["awards"])}</div>

</body>
</html>"""


def render_cover_letter_html(payload: dict) -> str:
    contact = payload["contact"]
    meta = payload["meta"]
    paragraphs = payload.get("cover_letter", {}).get("paragraphs", [])
    body = "".join(f"<p>{escape(p)}</p>" for p in paragraphs)

    return f"""<!DOCTYPE html>
<html lang="en">
<head><meta charset="UTF-8"><style>{_CSS}</style></head>
<body>

<h1>{escape(contact["name"])}</h1>
<div class="contact">{_contact_line(contact)}</div>

<h2>Re: {escape(meta["role"])} — {escape(meta["company"])}</h2>
<div class="cl-body" style="margin-top:12px">
{body}
<p>Sincerely,<br>{escape(contact["name"])}</p>
</div>

</body>
</html>"""
