# Resume Tailoring Agent — Handoff Document

**Project:** `jobapply` auto-application bot
**Agent Role:** JD-to-Resume Keyword Optimizer
**Owner:** Tahmeed Hossain
**Stack:** Python (rule engine + HTML→PDF via headless Chrome/selenium) + TypeScript career-ops bot integration + optional local LLM (Ollama) — **no Claude API / no external API calls**

> **Status: IMPLEMENTED.** The pipeline described below exists as real code:
> `agents/tailor_rules.py`, `agents/local_llm.py`, `generators/resume_html.py`,
> `generators/pdf_generator.py`, `orchestrator.py`, `profiles/tahmeed.yaml`, and
> the career-ops hook `career-ops/tahmeed/src/core/resumeTailor.ts`.

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

## PDF Generation (HTML → headless Chrome)

Implemented in `generators/resume_html.py` + `generators/pdf_generator.py`.

- `resume_html.py` renders the ResumePayload to styled HTML. The CSS is copied
  from `career-ops/tahmeed/generate-resume.mjs` — the proven house style — so
  tailored resumes look identical to the hand-built one.
- `pdf_generator.py` prints that HTML to PDF via headless Chrome
  (`Page.printToPDF` over CDP, using selenium — already a project dependency).
  Chromedriver resolution mirrors `main.py`’s `init_browser()`: newest cached
  driver in `~/.cache/selenium`, falling back to webdriver-manager.
- No LibreOffice, no Node docx step. Both the resume and cover letter PDFs are
  produced this way (RULE_4).

```python
from generators.pdf_generator import generate_resume_pdf, generate_cover_letter_pdf

resume_pdf = generate_resume_pdf(payload, output_dir)        # <base>.pdf
cl_pdf = generate_cover_letter_pdf(payload, output_dir)      # <base>_CoverLetter.pdf
```

---

## Orchestrator (main entry point)

Implemented in `orchestrator.py`. Every run generates a **new resume** and
stores it (plus cover letter and payload JSON) in `Claude_Resumes/`, so the
corpus grows with each application.

```bash
python orchestrator.py <jd_file> "<Company>" "<Role>" [--output-dir DIR] [--no-cover-letter] [--no-llm]
```

Pipeline: JD → `tailor_rules.tailor_resume()` → optional
`local_llm.polish_with_local_llm()` (auto-skipped when Ollama is absent) →
payload JSON + resume PDF + cover letter PDF in `Claude_Resumes/`.

The **last stdout line** is a machine-readable trailer so callers can parse
the generated paths reliably:

```
RESULT_JSON:{"resume": "...pdf", "cover_letter": "...pdf", "payload_json": "...json"}
```

---

## Integration with the career-ops Playwright Bot (IMPLEMENTED)

The career-ops bot now attaches the tailored resume automatically.
`career-ops/tahmeed/src/core/resumeTailor.ts` spawns the orchestrator and
parses the `RESULT_JSON:` trailer; `applicationFlow.ts` calls it per job with
the JD text already scraped from the posting page, then overrides
`profile.resumePath` so `universalFiller.ts` uploads the tailored PDF instead
of the static `data/resume.pdf`:

```ts
// src/flows/applicationFlow.ts (inside run(), before platform.apply)
let profileForJob = this.profile;
try {
  const tailoredResume = await generateTailoredResume(job, pageText, this.logger);
  if (tailoredResume) {
    profileForJob = { ...this.profile, resumePath: tailoredResume };
  }
} catch (error) {
  this.logger.warn(`Resume tailoring failed, using static resume: ...`);
}
const result = await platform.apply(page, job, profileForJob, this.dryRun);
```

Failure handling: if `orchestrator.py` is missing, the JD is too short
(< 200 chars), the spawn fails, or the PDF doesn’t materialise, the bot logs a
warning and falls back to the static resume — an application is never blocked
by tailoring.

---

## File Structure

```
JobAutoApply/
├── agents/
│   ├── tailor_rules.py        # Rule engine: keywords, titles, bullet bank
│   └── local_llm.py           # Optional Ollama polish + corpus tooling
├── generators/
│   ├── resume_html.py         # Payload → styled HTML (house CSS)
│   └── pdf_generator.py       # HTML → PDF via headless Chrome
├── orchestrator.py            # Main pipeline entry point (CLI)
├── profiles/
│   └── tahmeed.yaml           # Base profile (contact, certs, fixed role bullets)
├── Claude_Resumes/            # ALL generated resumes/cover letters/payloads land here
│                              # + reference/training corpus for the local LLM (gitignored)
├── RESUME_TAILOR_AGENT.md     # This document
└── career-ops/tahmeed/src/
    ├── core/resumeTailor.ts   # Spawns orchestrator, parses RESULT_JSON
    └── flows/applicationFlow.ts  # Per-job resumePath override (wired)
```

---

## Quick Start

```bash
# Dependencies are already in requirements.txt (selenium, webdriver-manager,
# PyYAML). Optional extras:
pip install pypdf python-docx        # only needed for local-LLM corpus extraction
# Optional local LLM polish: install Ollama, then: ollama pull llama3.1

# Tailor and generate for a single JD file
python orchestrator.py ./jds/jetbrains_qa.txt "JetBrains" "QA Engineer"

# Output (all in Claude_Resumes/):
# Claude_Resumes/TahmeedHossain_JetBrains_QAEngineer.pdf
# Claude_Resumes/TahmeedHossain_JetBrains_QAEngineer_CoverLetter.pdf
# Claude_Resumes/TahmeedHossain_JetBrains_QAEngineer_payload.json

# The career-ops bot picks it up automatically — run it as usual:
cd career-ops/tahmeed && node --loader ts-node/esm src/index.ts --headed
```

---

## Notes

- **No Claude API / no external API.** Tailoring is fully rule-based (`tailor_rules.py`); the only LLM step is the optional local Ollama polish, and the pipeline works without it
- The Encorp/Onevest rewrites are the only generated content — grow `ENCORP_BULLETS` / `ONEVEST_BULLETS` and `TECH_KEYWORDS` over time to improve tailoring quality
- RULE_6 check: after building the payload, assert every extracted JD keyword appears in the serialized payload; log any that were dropped
- `Claude_Resumes/` is both the output folder and the local-LLM corpus — every new application makes retrieval/fine-tuning better; run `export_finetune_jsonl()` periodically to refresh the training dataset
- The payload JSON is the single source of truth — it is saved alongside each resume so you can regenerate PDFs without re-running the rules
- PDFs are rendered by headless Chrome (`Page.printToPDF`) — the same engine the career-ops `generate-resume.mjs` uses, so output matches the house style exactly
- The cover letter paragraphs are template-driven (opening, why-this-company, core-skills-with-JD-keywords, closing) — 4 paragraphs, keywords injected the same way as bullets
