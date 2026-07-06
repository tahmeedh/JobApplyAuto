# Resume Tailoring Agent — Handoff Document

**Project:** `jobapply` auto-application bot
**Agent Role:** JD-to-Resume Keyword Optimizer
**Owner:** Tahmeed Hossain
**Stack:** Python (rule engine + PDF generation via ReportLab) + Node.js (docx generation via docx.js) + optional local LLM (Ollama) — **no Claude API / no external API calls**

---

## Agent Overview

This agent takes a raw job description and a base resume YAML profile, then:

1. Extracts high-value keywords and role-specific framing from the JD using a **deterministic rule engine** (no API calls)
2. Rewrites Encorp and Onevest job titles and bullet points to match the JD via **title templates and a tagged bullet bank**
3. Injects **all relevant keywords from the JD** into the skills section and rewritten bullets
4. Keeps all other roles (Global Relay, Alstar, OMMATY, Agronome) with original content
5. Outputs a structured JSON payload that the PDF/DOCX generation pipeline consumes
6. **Generates a new resume for every JD and stores it in `Claude_Resumes/`**, which doubles as the reference/training corpus for the optional local LLM polish layer
7. Optionally generates a companion cover letter JSON payload

---

## Permanent Rules (Never Override)

```
RULE_1: Never list Spanish fluency on any resume
RULE_2: Always rewrite Encorp and Onevest job titles and bullet points per JD
RULE_3: All other roles keep original titles and bullets unless explicitly requested
RULE_4: Output both resume PDF and cover letter PDF for every job application
RULE_5: One .docx file per deliverable — never output both .docx and PDF unless explicitly asked
RULE_6: Every relevant keyword found in the JD must appear somewhere in the resume
        (skills section first, rewritten Encorp/Onevest bullets second)
RULE_7: All generated resumes, cover letters, and payload JSONs are saved to
        Claude_Resumes/ — this folder is the single archive AND the local-LLM
        reference/training corpus
RULE_8: No external API calls — tailoring is rule-based; any LLM step runs
        locally (Ollama) and is optional
```

---

## Agent Input Schema

```python
class TailorRequest(TypedDict):
    job_description: str          # Raw JD text (scraped or pasted)
    company_name: str             # e.g. "JetBrains"
    role_title: str               # e.g. "QA Engineer"
    output_filename_base: str     # e.g. "TahmeedHossain_JetBrains_QA"
    generate_cover_letter: bool   # Whether to also produce cover letter JSON
    cover_letter_notes: str       # Optional: hiring manager name, specific angle
```

---

## Agent Output Schema

The agent returns a `ResumePayload` JSON object consumed by both the Python PDF pipeline and Node.js DOCX pipeline.

```json
{
  "meta": {
    "company": "JetBrains",
    "role": "QA Engineer",
    "filename_base": "TahmeedHossain_JetBrains_QA",
    "subtitle": "QA Engineer — Desktop, Client-Server & Integration Systems"
  },
  "contact": {
    "name": "Tahmeed Hossain",
    "phone": "604-818-5738",
    "email": "tahmeedhossain@gmail.com",
    "linkedin": "linkedin.com/in/tahmeedhossain",
    "website": "tahmeedhossain.com",
    "location": "Vancouver, BC"
  },
  "summary": "Senior QA Engineer with 5+ years...",
  "skills": [
    { "label": "Testing Methodology", "value": "Risk-based testing, exploratory..." },
    { "label": "Platforms & Systems", "value": "macOS, Windows, Linux..." }
  ],
  "experience": [
    {
      "company": "Encorp",
      "title": "Senior QA Engineer — Complex Systems & Integration",
      "dates": "Jan 2024 – Jun 2025",
      "bullets": [
        "Owned quality strategy across a multi-component AI platform...",
        "Participated in release acceptance decisions..."
      ]
    },
    {
      "company": "Global Relay",
      "title": "Intermediate Software Engineer in Test",
      "dates": "Jan 2022 – Oct 2024",
      "bullets": [
        "Automated E2E and integration testing with WebdriverIO, Selenium...",
        "Migrated legacy Selenium suite to Playwright..."
      ]
    },
    {
      "company": "Onevest",
      "title": "QA Engineer — Integration, API & Release Validation",
      "dates": "Jun 2021 – Nov 2021",
      "bullets": [
        "Owned quality for a client-server enterprise platform...",
        "Investigated and localised complex defects..."
      ]
    },
    {
      "company": "Alstar Brokerage Solutions",
      "title": "FullStack Engineer (Part-time)",
      "dates": "Jan 2021 – Jun 2021",
      "bullets": [
        "Developed user-defined stored procedures...",
        "Built backend services for multiple features in .NET framework...",
        "Spearheaded UI testing and successful MVP deployment..."
      ]
    },
    {
      "company": "OMMATY",
      "title": "Backend Software Engineer / QA Intern",
      "dates": "Jan 2020 – Sep 2020",
      "bullets": [
        "Developing an iOS/Android application using Flutter...",
        "Designed and implemented backend CRUD operations...",
        "Developed comprehensive unit tests using Jest...",
        "Built backend services for offer features..."
      ]
    },
    {
      "company": "Agronome",
      "title": "Backend Developer Intern",
      "dates": "May 2019 – Aug 2019",
      "bullets": [
        "Configured Docker Compose...",
        "Implemented elastic search by parsing CSV files...",
        "Built data pipelines and development environments...",
        "Used Google Maps API to store farm location..."
      ]
    }
  ],
  "education": {
    "institution": "University of British Columbia",
    "degree": "B.Sc. in Computer Science",
    "gpa": "3.9",
    "coursework": "Software Engineering, Data Structures & Algorithms..."
  },
  "certifications": "ISTQB Agile Tester | AWS Cloud Practitioner | Google CyberSecurity Certificate | CompTIA+ CyberSecurity | DeepLearning.ai",
  "awards": "New Ventures BC — 5th of 300 (2024) | UBC Dean's List (2020–2021) | UBC Hackathon 3rd Place (2020)",
  "cover_letter": {
    "paragraphs": [
      "Opening paragraph...",
      "Why this company paragraph...",
      "Core skills paragraph...",
      "Closing paragraph..."
    ]
  }
}
```

---

## Rule-Based Tailoring Engine (replaces the Claude API call)

Tailoring is deterministic. Three rule groups do what the API prompt used to do:

1. **Keyword extraction** — scan the JD against a tech dictionary + heuristics; the result is an ordered keyword list
2. **Title rewriting** — Encorp and Onevest titles come from templates keyed by detected role family
3. **Bullet selection & keyword injection** — Encorp/Onevest bullets are picked from a tagged bullet bank scored against the JD keywords, then exact JD phrasing is injected

```python
# agents/tailor_rules.py
import re

# ---------------------------------------------------------------
# 1. KEYWORD EXTRACTION
# ---------------------------------------------------------------
# Canonical keyword -> aliases as they may appear in a JD.
# Extend this dictionary over time; it is the ATS-matching backbone.
TECH_KEYWORDS = {
    "Playwright":        ["playwright"],
    "Selenium":          ["selenium", "webdriver"],
    "WebdriverIO":       ["webdriverio", "wdio"],
    "Cypress":           ["cypress"],
    "TypeScript":        ["typescript", "ts"],
    "JavaScript":        ["javascript", "js", "node.js", "nodejs"],
    "Python":            ["python", "pytest"],
    "Java":              ["java", "junit", "testng"],
    "C#":                ["c#", ".net", "dotnet", "nunit"],
    "SQL":               ["sql", "mssql", "postgres", "postgresql", "mysql"],
    "REST APIs":         ["rest", "restful", "api testing", "postman"],
    "GraphQL":           ["graphql"],
    "CI/CD":             ["ci/cd", "continuous integration", "continuous delivery"],
    "Jenkins":           ["jenkins"],
    "GitHub Actions":    ["github actions"],
    "Docker":            ["docker", "container", "docker compose"],
    "Kubernetes":        ["kubernetes", "k8s"],
    "AWS":               ["aws", "amazon web services", "sagemaker", "ec2", "s3"],
    "GCP":               ["gcp", "google cloud"],
    "Azure":             ["azure"],
    "Grafana":           ["grafana"],
    "Allure":            ["allure"],
    "JIRA":              ["jira", "zephyr"],
    "Agile/Scrum":       ["agile", "scrum", "kanban", "sprint"],
    "Performance Testing": ["performance testing", "load testing", "jmeter", "k6"],
    "Security Testing":  ["security testing", "penetration", "owasp"],
    "Computer Vision":   ["computer vision", "yolo", "opencv"],
    "Machine Learning":  ["machine learning", "ml", "pytorch", "tensorflow", "ai"],
    "OCR":               ["ocr"],
    "Regression Testing": ["regression"],
    "E2E Testing":       ["e2e", "end-to-end", "end to end"],
    "Mobile Testing":    ["mobile testing", "appium", "ios testing", "android testing"],
    "Test Automation":   ["test automation", "automated testing", "automation framework"],
    "Manual Testing":    ["manual testing", "exploratory testing"],
    "Linux":             ["linux", "unix", "bash", "shell"],
}

def extract_keywords(jd: str) -> list[str]:
    """Return every canonical keyword whose alias appears in the JD,
    ordered by first appearance (JD priority order)."""
    jd_lower = jd.lower()
    found = []
    for canonical, aliases in TECH_KEYWORDS.items():
        positions = [jd_lower.find(a) for a in aliases if a in jd_lower]
        positions = [p for p in positions if p >= 0]
        if positions:
            found.append((min(positions), canonical))
    # Heuristic: also capture Capitalized/CamelCase tool names not in the
    # dictionary (e.g. "TestRail", "Datadog") so nothing relevant is missed.
    for m in re.finditer(r"\b([A-Z][a-z]+[A-Z][A-Za-z]+|[A-Z]{2,}[a-z]*)\b", jd):
        token = m.group(1)
        if token not in dict(found).values() \
           and token not in {"QA", "THE", "AND"} and len(token) > 2:
            found.append((m.start(), token))
    found.sort()
    seen, ordered = set(), []
    for _, kw in found:
        if kw not in seen:
            seen.add(kw)
            ordered.append(kw)
    return ordered


# ---------------------------------------------------------------
# 2. ROLE FAMILY DETECTION + TITLE TEMPLATES (Encorp / Onevest)
# ---------------------------------------------------------------
ROLE_FAMILIES = {
    "sdet":    ["sdet", "software engineer in test", "test automation", "automation engineer"],
    "qa":      ["qa", "quality assurance", "quality engineer", "test engineer", "tester"],
    "devops":  ["devops", "sre", "site reliability", "platform engineer", "cloud engineer"],
    "data":    ["data engineer", "data analyst", "machine learning", "ml engineer", "ai engineer"],
    "swe":     ["software engineer", "software developer", "full stack", "fullstack", "backend", "frontend"],
}

def detect_role_family(role_title: str, jd: str) -> str:
    text = f"{role_title} {jd}".lower()
    scores = {fam: sum(text.count(t) for t in terms) for fam, terms in ROLE_FAMILIES.items()}
    # Role title match outweighs JD body mentions
    for fam, terms in ROLE_FAMILIES.items():
        if any(t in role_title.lower() for t in terms):
            scores[fam] += 10
    return max(scores, key=scores.get) or "qa"

ENCORP_TITLES = {
    "sdet":   "Senior SDET — AI Platform, Automation & CI/CD",
    "qa":     "Senior QA Engineer — Complex Systems & Integration",
    "devops": "QA / DevOps Engineer — Cloud Benchmarking & CI/CD Pipelines",
    "data":   "AI/ML Quality Engineer — Computer Vision & Data Pipelines",
    "swe":    "Software Engineer — AI Platform & Automation Tooling",
}

ONEVEST_TITLES = {
    "sdet":   "SDET — API Automation & Release Validation",
    "qa":     "QA Engineer — Integration, API & Release Validation",
    "devops": "QA Engineer — CI/CD Migration & Release Tooling",
    "data":   "QA Engineer — Data Integrity & API Validation",
    "swe":    "Software Engineer — Test Tooling & Platform Security",
}


# ---------------------------------------------------------------
# 3. BULLET BANK + KEYWORD INJECTION (Encorp / Onevest)
# ---------------------------------------------------------------
# Each bullet is grounded in a real achievement, tagged with the keywords it
# supports, and may contain {kw} slots filled with exact JD phrasing.
ENCORP_BULLETS = [
    {"tags": ["Computer Vision", "Machine Learning", "Python"],
     "text": "Built a YOLOv8/PyTorch computer vision model achieving 90%+ accuracy across 4,000+ containers within 3 months, owning the full {kw} validation strategy."},
    {"tags": ["Python", "Test Automation"],
     "text": "Replaced five-figure third-party annotation tools with automated Python pipelines, cutting labelling cost and turnaround while improving {kw} coverage."},
    {"tags": ["AWS", "GCP", "CI/CD", "Performance Testing"],
     "text": "Benchmarked AWS SageMaker, GCP, and RunPod for cost and performance to select the production training stack ({kw})."},
    {"tags": ["OCR", "Regression Testing", "Test Automation"],
     "text": "Built an OCR regression testing pipeline guarding release quality across every model iteration."},
    {"tags": ["Allure", "Grafana", "CI/CD"],
     "text": "Created Allure test reporting and Grafana dashboards giving the team real-time visibility into automation health."},
    {"tags": ["Linux", "E2E Testing"],
     "text": "Tested and validated deployments on Nvidia Jetson Nano and RTX 3900 edge hardware, covering {kw} scenarios end-to-end."},
    {"tags": ["GitHub Actions", "CI/CD"],
     "text": "Integrated GitHub Actions CI/CD pipelines so every merge triggered automated build, test, and reporting stages."},
]

ONEVEST_BULLETS = [
    {"tags": ["GitHub Actions", "CI/CD", "Allure", "JIRA"],
     "text": "Led the GitHub Actions CI/CD migration and built an Allure/Zephyr/Slack reporting tool that pushed {kw} results to the whole team automatically."},
    {"tags": ["GraphQL", "REST APIs", "Test Automation"],
     "text": "Implemented GraphQL entitlements and permissions testing, validating {kw} access rules across user roles."},
    {"tags": ["Security Testing"],
     "text": "Built an IP whitelist security feature and validated it against {kw} requirements."},
    {"tags": ["JavaScript", "Python", "Test Automation"],
     "text": "Wrote JavaScript and Python automation scripts covering {kw} regression scenarios for the client-server platform."},
]

def pick_bullets(bank: list[dict], jd_keywords: list[str], minimum: int = 4) -> list[str]:
    """Score bullets by tag overlap with JD keywords; inject the top JD
    keyword each bullet supports into its {kw} slot."""
    kwset = set(jd_keywords)
    scored = sorted(bank, key=lambda b: -len(kwset & set(b["tags"])))
    out = []
    for b in scored[:max(minimum, sum(1 for b in scored if kwset & set(b["tags"])))]:
        matched = [k for k in jd_keywords if k in b["tags"]]
        kw = matched[0] if matched else (b["tags"][0] if b["tags"] else "")
        out.append(b["text"].replace("{kw}", kw))
    return out


# ---------------------------------------------------------------
# 4. SKILLS SECTION — ALL relevant JD keywords must land (RULE_6)
# ---------------------------------------------------------------
SKILL_ROWS = {
    "Testing & Automation": ["Playwright", "Selenium", "WebdriverIO", "Cypress",
                             "Test Automation", "E2E Testing", "Regression Testing",
                             "Manual Testing", "Performance Testing", "Mobile Testing",
                             "Security Testing", "Allure"],
    "Languages":            ["TypeScript", "JavaScript", "Python", "Java", "C#", "SQL"],
    "APIs & Platforms":     ["REST APIs", "GraphQL", "Linux"],
    "CI/CD & Cloud":        ["CI/CD", "Jenkins", "GitHub Actions", "Docker",
                             "Kubernetes", "AWS", "GCP", "Azure", "Grafana"],
    "AI/ML":                ["Computer Vision", "Machine Learning", "OCR"],
    "Process":              ["Agile/Scrum", "JIRA"],
}

def build_skills(jd_keywords: list[str]) -> list[dict]:
    """Front-load JD keywords in each row; append any JD keyword that fits no
    row into a final 'Also Working With' row so nothing from the JD is dropped."""
    rows, placed = [], set()
    for label, members in SKILL_ROWS.items():
        hits = [k for k in jd_keywords if k in members]          # JD keywords first
        rest = [m for m in members if m not in hits][:4]         # pad with strongest defaults
        if hits or rest:
            rows.append({"label": label, "value": ", ".join(hits + rest)})
            placed.update(hits)
    leftovers = [k for k in jd_keywords if k not in placed]
    if leftovers:
        rows.append({"label": "Also Working With", "value": ", ".join(leftovers)})
    return rows


# ---------------------------------------------------------------
# 5. ENTRY POINT — same signature the orchestrator already uses
# ---------------------------------------------------------------
def tailor_resume(job_description: str, company: str, role: str,
                  filename_base: str, generate_cover_letter: bool = True) -> dict:
    jd_keywords = extract_keywords(job_description)
    family = detect_role_family(role, job_description)

    payload = load_base_profile()                 # contact/education/certs/fixed roles from profiles/tahmeed.yaml
    payload["meta"] = {
        "company": company, "role": role, "filename_base": filename_base,
        "subtitle": f"{role} — {', '.join(jd_keywords[:3])}",
    }
    payload["summary"] = (
        f"{role} with 5+ years across QA automation, backend, and AI systems, "
        f"specialising in {', '.join(jd_keywords[:5])}."
    )
    payload["skills"] = build_skills(jd_keywords)

    for job in payload["experience"]:
        if job["company"] == "Encorp":            # RULE_2
            job["title"] = ENCORP_TITLES[family]
            job["bullets"] = pick_bullets(ENCORP_BULLETS, jd_keywords)
        elif job["company"] == "Onevest":         # RULE_2
            job["title"] = ONEVEST_TITLES[family]
            job["bullets"] = pick_bullets(ONEVEST_BULLETS, jd_keywords)
        # all other companies untouched — RULE_3

    if generate_cover_letter:
        payload["cover_letter"] = build_cover_letter(company, role, jd_keywords)
    return payload
```

The fixed role content (Global Relay, Alstar, OMMATY, Agronome) lives in `profiles/tahmeed.yaml` verbatim and is never rewritten — same bullets as listed in the Output Schema example above.

---

## Local LLM Layer (optional) — `Claude_Resumes/` as reference & training corpus

The rule engine alone produces a valid, ATS-optimized resume. An **optional** local LLM pass (Ollama, e.g. `llama3.1` — no external API) can smooth the injected phrasing. `Claude_Resumes/` plays two roles:

1. **Reference corpus (few-shot):** the 40+ previously tailored resumes in `Claude_Resumes/` are indexed; the 2–3 most similar past resumes (by keyword overlap with the current JD) are included in the local prompt as style examples
2. **Training data (fine-tuning):** exportable as JSONL pairs (`JD keywords → final resume text`) to fine-tune a local model as the corpus grows

```python
# agents/local_llm.py
import os, json, subprocess
from pypdf import PdfReader
from docx import Document as Docx

CORPUS_DIR = "./Claude_Resumes"

def build_corpus() -> list[dict]:
    """Extract text from every PDF/DOCX in Claude_Resumes/ -> [{file, text}]."""
    corpus = []
    for f in os.listdir(CORPUS_DIR):
        path = os.path.join(CORPUS_DIR, f)
        try:
            if f.endswith(".pdf"):
                text = "\n".join(p.extract_text() or "" for p in PdfReader(path).pages)
            elif f.endswith(".docx"):
                text = "\n".join(p.text for p in Docx(path).paragraphs)
            else:
                continue
            corpus.append({"file": f, "text": text})
        except Exception:
            continue
    return corpus

def most_similar(jd_keywords: list[str], corpus: list[dict], n: int = 3) -> list[dict]:
    """Rank past resumes by JD-keyword overlap — cheap, deterministic retrieval."""
    def score(doc):
        return sum(1 for k in jd_keywords if k.lower() in doc["text"].lower())
    return sorted(corpus, key=score, reverse=True)[:n]

def polish_with_local_llm(payload: dict, jd_keywords: list[str]) -> dict:
    """OPTIONAL: rewrite only summary + Encorp/Onevest bullets via local Ollama,
    using the most similar past resumes as few-shot style examples.
    If Ollama is not installed/running, return payload unchanged (rules-only)."""
    examples = most_similar(jd_keywords, build_corpus())
    prompt = (
        "Rewrite these resume bullets to flow naturally. Keep every keyword. "
        "Match the style of the example resumes.\n\n"
        + "\n---\n".join(e["text"][:2000] for e in examples)
        + "\n\nBullets:\n" + json.dumps({
            "summary": payload["summary"],
            "encorp": next(j["bullets"] for j in payload["experience"] if j["company"] == "Encorp"),
            "onevest": next(j["bullets"] for j in payload["experience"] if j["company"] == "Onevest"),
        })
    )
    try:
        result = subprocess.run(["ollama", "run", "llama3.1", prompt],
                                capture_output=True, text=True, timeout=120, check=True)
        polished = json.loads(result.stdout.strip())
        payload["summary"] = polished.get("summary", payload["summary"])
        for j in payload["experience"]:
            if j["company"] == "Encorp" and polished.get("encorp"):
                j["bullets"] = polished["encorp"]
            if j["company"] == "Onevest" and polished.get("onevest"):
                j["bullets"] = polished["onevest"]
    except Exception:
        pass  # rules-only output is already valid — LLM polish is best-effort
    return payload

def export_finetune_jsonl(out_path: str = "./Claude_Resumes/finetune_dataset.jsonl"):
    """Dump (keywords -> resume text) pairs for future local fine-tuning."""
    with open(out_path, "w", encoding="utf-8") as f:
        for doc in build_corpus():
            f.write(json.dumps({"input": doc["file"], "output": doc["text"]}) + "\n")
```

---

## Node.js DOCX Generation (docx.js)

The Node.js pipeline receives the JSON payload and renders it using `docx` npm package, identical to the pattern used in this session.

```javascript
// resume-generator.js
const { Document, Packer, Paragraph, TextRun, AlignmentType, BorderStyle, LevelFormat } = require('docx');
const fs = require('fs');

async function generateDocx(payload, outputPath) {
  const { meta, contact, summary, skills, experience, 
          education, certifications, awards } = payload;

  // Build sections using the same pattern as established in this session
  const children = [];

  // Header
  children.push(nameHeader(contact.name));
  children.push(subtitleLine(meta.subtitle));
  children.push(contactLine(contact));

  // Summary
  children.push(sectionHeader('Professional Summary'));
  children.push(para(summary));

  // Skills
  children.push(sectionHeader('Technical Skills'));
  skills.forEach(s => children.push(skillRow(s.label, s.value)));

  // Experience
  children.push(sectionHeader('Work Experience'));
  experience.forEach(job => {
    children.push(jobHeader(job.title, job.company, job.dates));
    job.bullets.forEach(b => children.push(bullet(b)));
  });

  // Education
  children.push(sectionHeader('Education'));
  children.push(educationBlock(education));

  // Certs
  children.push(sectionHeader('Certifications & Recognition'));
  children.push(para(certifications));
  children.push(para(awards));

  const doc = new Document({
    numbering: { config: [bulletConfig()] },
    sections: [{ properties: pageProps(), children }]
  });

  const buffer = await Packer.toBuffer(doc);
  fs.writeFileSync(outputPath, buffer);
}

module.exports = { generateDocx };
```

---

## Python PDF Generation (ReportLab)

```python
# pdf_generator.py
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.units import inch
from reportlab.lib import colors
import subprocess
import os

def generate_pdf_via_docx(payload: dict, output_dir: str) -> str:
    """
    Strategy: Generate DOCX via Node.js subprocess, then convert to PDF via LibreOffice.
    This matches the proven pattern from this session.
    """
    filename_base = payload['meta']['filename_base']
    docx_path = os.path.join(output_dir, f"{filename_base}.docx")
    pdf_path = os.path.join(output_dir, f"{filename_base}.pdf")
    
    # Write payload to temp JSON for Node.js to consume
    import json, tempfile
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        json.dump(payload, f)
        payload_path = f.name
    
    # Call Node.js generator
    subprocess.run([
        'node', 'resume-generator.js', payload_path, docx_path
    ], check=True)
    
    # Convert DOCX → PDF via LibreOffice (same as this session)
    subprocess.run([
        'soffice', '--headless', '--convert-to', 'pdf',
        '--outdir', output_dir, docx_path
    ], check=True)
    
    return pdf_path


def generate_cover_letter_pdf(payload: dict, output_dir: str) -> str:
    """Generate cover letter PDF from payload cover_letter paragraphs."""
    filename_base = payload['meta']['filename_base']
    cl_path = os.path.join(output_dir, f"{filename_base}_CoverLetter.pdf")
    
    doc = SimpleDocTemplate(cl_path, pagesize=letter,
                            leftMargin=inch, rightMargin=inch,
                            topMargin=inch, bottomMargin=inch)
    
    styles = getSampleStyleSheet()
    body_style = ParagraphStyle('body', fontName='Helvetica', fontSize=11,
                                leading=16, spaceAfter=12)
    
    story = []
    contact = payload['contact']
    meta = payload['meta']
    
    # Header
    story.append(Paragraph(f"<b>{contact['name']}</b>", styles['Title']))
    story.append(Paragraph(
        f"{contact['email']} | {contact['phone']} | {contact['location']}",
        styles['Normal']))
    story.append(Spacer(1, 0.3*inch))
    story.append(Paragraph(f"Re: {meta['role']} — {meta['company']}", body_style))
    story.append(Spacer(1, 0.2*inch))
    
    for para_text in payload.get('cover_letter', {}).get('paragraphs', []):
        story.append(Paragraph(para_text, body_style))
    
    story.append(Spacer(1, 0.3*inch))
    story.append(Paragraph(f"Sincerely,<br/>{contact['name']}", body_style))
    
    doc.build(story)
    return cl_path
```

---

## Orchestrator (main entry point)

Every run generates a **new resume** and stores it (plus cover letter and payload JSON) in `Claude_Resumes/`, so the corpus grows with each application.

```python
# orchestrator.py
import sys
import json
from agents.tailor_rules import tailor_resume, extract_keywords
from agents.local_llm import polish_with_local_llm
from pdf_generator import generate_pdf_via_docx, generate_cover_letter_pdf

OUTPUT_DIR = "./Claude_Resumes"   # archive + local-LLM corpus (RULE_7)

def run(job_description: str, company: str, role: str, output_dir: str = OUTPUT_DIR):
    """Full pipeline: JD → rules → (optional local LLM polish) → DOCX + PDF + Cover Letter"""

    filename_base = f"TahmeedHossain_{company.replace(' ', '')}_{role.replace(' ', '')}"

    print(f"[1/4] Extracting JD keywords and applying tailoring rules for {role} at {company}...")
    payload = tailor_resume(
        job_description=job_description,
        company=company,
        role=role,
        filename_base=filename_base,
        generate_cover_letter=True
    )

    print("[2/4] Optional local LLM polish (skipped automatically if Ollama absent)...")
    payload = polish_with_local_llm(payload, extract_keywords(job_description))

    # Save JSON payload next to the resume — same folder feeds the corpus
    with open(f"{output_dir}/{filename_base}_payload.json", "w") as f:
        json.dump(payload, f, indent=2)

    print("[3/4] Generating resume PDF...")
    resume_pdf = generate_pdf_via_docx(payload, output_dir)
    print(f"  → {resume_pdf}")

    print("[4/4] Generating cover letter PDF...")
    cl_pdf = generate_cover_letter_pdf(payload, output_dir)
    print(f"  → {cl_pdf}")

    return {"resume": resume_pdf, "cover_letter": cl_pdf, "payload": payload}


if __name__ == "__main__":
    # Example usage
    jd = open(sys.argv[1]).read()
    company = sys.argv[2]
    role = sys.argv[3]
    result = run(jd, company, role)
    print(json.dumps(result, indent=2))
```

---

## Integration with jobapply Playwright Bot

In your existing `jobapply` bot, add a pre-fill step before the Playwright ATS interaction:

```python
# In your jobapply bot flow
from orchestrator import run as tailor_and_generate

async def apply_to_job(job_url: str, job_description: str, company: str, role: str):
    
    # Step 1: Tailor resume via rules and generate PDFs into Claude_Resumes/
    result = tailor_and_generate(job_description, company, role)
    resume_pdf_path = result["resume"]
    cover_letter_pdf_path = result["cover_letter"]
    
    # Step 2: Human review checkpoint (your existing pattern)
    print(f"\n=== HUMAN REVIEW REQUIRED ===")
    print(f"Resume: {resume_pdf_path}")
    print(f"Cover Letter: {cover_letter_pdf_path}")
    input("Press Enter to proceed with submission, or Ctrl+C to abort...")
    
    # Step 3: Playwright ATS submission (your existing bot)
    async with async_playwright() as p:
        browser = await p.chromium.connect_over_cdp("http://localhost:9222")
        # ... existing Playwright logic to upload PDFs and fill ATS fields
        await upload_file(page, resume_pdf_path, selector="#resume-upload")
        await upload_file(page, cover_letter_pdf_path, selector="#cover-letter-upload")
```

---

## File Structure

```
jobapply/
├── agents/
│   ├── tailor_rules.py        # Rule engine: keywords, titles, bullet bank
│   ├── local_llm.py           # Optional Ollama polish + corpus tooling
│   └── RESUME_TAILOR_AGENT.md # This document
├── generators/
│   ├── resume-generator.js    # Node.js DOCX builder
│   └── pdf_generator.py       # Python PDF/cover letter builder
├── orchestrator.py            # Main pipeline entry point
├── bot/
│   └── apply.py               # Existing Playwright ATS bot
├── profiles/
│   └── tahmeed.yaml           # Base profile YAML (contact, certs, fixed role bullets)
├── Claude_Resumes/            # ALL generated resumes/cover letters/payloads land here
│                              # + reference/training corpus for the local LLM
└── jds/                       # Scraped job descriptions
```

---

## Quick Start

```bash
# Install dependencies (no anthropic SDK — no API keys needed)
pip install reportlab pypdf python-docx
npm install docx
# Optional local LLM polish:
#   install Ollama from https://ollama.com, then: ollama pull llama3.1

# Tailor and generate for a single JD file
python orchestrator.py ./jds/jetbrains_qa.txt "JetBrains" "QA Engineer"

# Output (all in Claude_Resumes/):
# ./Claude_Resumes/TahmeedHossain_JetBrains_QAEngineer.pdf
# ./Claude_Resumes/TahmeedHossain_JetBrains_QAEngineer_CoverLetter.pdf
# ./Claude_Resumes/TahmeedHossain_JetBrains_QAEngineer_payload.json
```

---

## Notes

- **No Claude API / no external API.** Tailoring is fully rule-based (`tailor_rules.py`); the only LLM step is the optional local Ollama polish, and the pipeline works without it
- The Encorp/Onevest rewrites are the only generated content — grow `ENCORP_BULLETS` / `ONEVEST_BULLETS` and `TECH_KEYWORDS` over time to improve tailoring quality
- RULE_6 check: after building the payload, assert every extracted JD keyword appears in the serialized payload; log any that were dropped
- `Claude_Resumes/` is both the output folder and the local-LLM corpus — every new application makes retrieval/fine-tuning better; run `export_finetune_jsonl()` periodically to refresh the training dataset
- The payload JSON is the single source of truth — it is saved alongside each resume so you can regenerate PDFs without re-running the rules
- For the DOCX → PDF conversion, LibreOffice (`soffice --headless`) is the proven converter from this session
- The cover letter paragraphs are template-driven (opening, why-this-company, core-skills-with-JD-keywords, closing) — 4 paragraphs, keywords injected the same way as bullets
