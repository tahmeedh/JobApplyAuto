"""Rule-based resume tailoring engine — no external API calls.

Implements the rules from RESUME_TAILOR_AGENT.md:
  RULE_1: never list Spanish fluency
  RULE_2: rewrite Encorp and Onevest titles/bullets per JD
  RULE_3: all other roles keep original content
  RULE_6: every relevant JD keyword must land in the resume
"""
import os
import re

import yaml

PROFILE_PATH = os.path.join(os.path.dirname(__file__), "..", "profiles", "tahmeed.yaml")

# ---------------------------------------------------------------
# 1. KEYWORD EXTRACTION
# ---------------------------------------------------------------
# Canonical keyword -> aliases as they may appear in a JD.
TECH_KEYWORDS = {
    "Playwright": ["playwright"],
    "Selenium": ["selenium", "webdriver "],
    "WebdriverIO": ["webdriverio", "wdio"],
    "Cypress": ["cypress"],
    "Appium": ["appium"],
    "TypeScript": ["typescript"],
    "JavaScript": ["javascript", "node.js", "nodejs"],
    "Python": ["python", "pytest"],
    "Java": ["java ", "junit", "testng"],
    "C#": ["c#", ".net", "dotnet", "nunit"],
    "SQL": ["sql", "mssql", "postgres", "postgresql", "mysql"],
    "REST APIs": ["rest api", "restful", "api testing", "postman", "rest assured"],
    "GraphQL": ["graphql"],
    "CI/CD": ["ci/cd", "continuous integration", "continuous delivery", "build pipeline"],
    "Jenkins": ["jenkins"],
    "GitHub Actions": ["github actions"],
    "GitLab CI": ["gitlab"],
    "Docker": ["docker", "container"],
    "Kubernetes": ["kubernetes", "k8s"],
    "AWS": ["aws", "amazon web services", "sagemaker", " ec2", " s3 "],
    "GCP": ["gcp", "google cloud"],
    "Azure": ["azure"],
    "Grafana": ["grafana"],
    "Allure": ["allure"],
    "JIRA": ["jira", "zephyr"],
    "TestRail": ["testrail"],
    "Agile/Scrum": ["agile", "scrum", "kanban", "sprint"],
    "Performance Testing": ["performance testing", "load testing", "jmeter", "k6", "locust"],
    "Security Testing": ["security testing", "penetration", "owasp"],
    "Accessibility Testing": ["accessibility", "wcag"],
    "Computer Vision": ["computer vision", "yolo", "opencv"],
    "Machine Learning": ["machine learning", "pytorch", "tensorflow", "ml model", " ai "],
    "OCR": ["ocr"],
    "Regression Testing": ["regression"],
    "E2E Testing": ["e2e", "end-to-end", "end to end"],
    "Mobile Testing": ["mobile testing", "ios testing", "android testing"],
    "Test Automation": ["test automation", "automated testing", "automation framework",
                        "automated test"],
    "Manual Testing": ["manual testing", "exploratory testing", "test case"],
    "Unit Testing": ["unit testing", "unit test"],
    "Integration Testing": ["integration testing", "integration test"],
    "Linux": ["linux", "unix", "bash", "shell script"],
    "Git": ["git ", "version control"],
    "Test Planning": ["test plan", "test strategy", "quality strategy"],
    "Debugging": ["debugging", "root cause", "troubleshoot"],
    "Cross-browser Testing": ["cross-browser", "cross browser"],
    "Microservices": ["microservice"],
    "Kafka": ["kafka"],
    "Terraform": ["terraform"],
    "Ansible": ["ansible"],
}

# CamelCase heuristic stoplist — common JD words that look like tool names
_HEURISTIC_STOPWORDS = {
    "JavaScript", "TypeScript", "GitHub", "GitLab", "LinkedIn", "PowerPoint",
    "MacBook", "YouTube", "WhatsApp", "FullStack", "FrontEnd", "BackEnd",
}


def extract_keywords(jd: str) -> "list[str]":
    """Return every canonical keyword whose alias appears in the JD,
    ordered by first appearance (JD priority order)."""
    jd_lower = jd.lower()
    padded = f" {jd_lower} "  # so padded aliases (e.g. " ai ") can match at the edges
    found = []
    for canonical, aliases in TECH_KEYWORDS.items():
        hits = []
        for a in aliases:
            # aliases with surrounding spaces must match exactly (avoids substring noise)
            p = padded.find(a) if a != a.strip() else jd_lower.find(a)
            if p >= 0:
                hits.append(p)
        if hits:
            found.append((min(hits), canonical))

    known = {kw for _, kw in found}
    # Heuristic: capture CamelCase tool names not in the dictionary
    # (e.g. "TestRail", "DataDog") so nothing relevant is missed.
    for m in re.finditer(r"\b([A-Z][a-z]+[A-Z][A-Za-z]+)\b", jd):
        token = m.group(1)
        if token not in known and token not in _HEURISTIC_STOPWORDS:
            known.add(token)
            found.append((m.start(), token))

    found.sort()
    return [kw for _, kw in found]


# ---------------------------------------------------------------
# 2. ROLE FAMILY DETECTION + TITLE TEMPLATES (Encorp / Onevest)
# ---------------------------------------------------------------
ROLE_FAMILIES = {
    "sdet": ["sdet", "software engineer in test", "test automation", "automation engineer"],
    "qa": ["qa", "quality assurance", "quality engineer", "test engineer", "tester"],
    "devops": ["devops", "sre", "site reliability", "platform engineer", "cloud engineer"],
    "data": ["data engineer", "data analyst", "machine learning", "ml engineer", "ai engineer"],
    "swe": ["software engineer", "software developer", "full stack", "fullstack",
            "backend", "frontend"],
}


def detect_role_family(role_title: str, jd: str) -> str:
    text = f"{role_title} {jd}".lower()
    scores = {fam: sum(text.count(t) for t in terms) for fam, terms in ROLE_FAMILIES.items()}
    # Role title match outweighs JD body mentions
    for fam, terms in ROLE_FAMILIES.items():
        if any(t in role_title.lower() for t in terms):
            scores[fam] += 10
    best = max(scores, key=lambda f: scores[f])
    return best if scores[best] > 0 else "qa"


ENCORP_TITLES = {
    "sdet": "Senior SDET — AI Platform, Automation & CI/CD",
    "qa": "Senior QA Engineer — Complex Systems & Integration",
    "devops": "QA / DevOps Engineer — Cloud Benchmarking & CI/CD Pipelines",
    "data": "AI/ML Quality Engineer — Computer Vision & Data Pipelines",
    "swe": "Software Engineer — AI Platform & Automation Tooling",
}

ONEVEST_TITLES = {
    "sdet": "SDET — API Automation & Release Validation",
    "qa": "QA Engineer — Integration, API & Release Validation",
    "devops": "QA Engineer — CI/CD Migration & Release Tooling",
    "data": "QA Engineer — Data Integrity & API Validation",
    "swe": "Software Engineer — Test Tooling & Platform Security",
}


# ---------------------------------------------------------------
# 3. BULLET BANK + KEYWORD INJECTION (Encorp / Onevest)
# ---------------------------------------------------------------
# Each bullet is grounded in a real achievement, tagged with the keywords it
# supports, and may contain a {kw} slot filled with exact JD phrasing.
ENCORP_BULLETS = [
    {"tags": ["Computer Vision", "Machine Learning", "Python", "Test Planning"],
     "text": "Built a YOLOv8/PyTorch computer vision model achieving 90%+ accuracy across "
             "4,000+ containers within 3 months, owning the end-to-end validation strategy "
             "for the AI platform."},
    {"tags": ["Test Automation", "Python", "Debugging"],
     "text": "Replaced five-figure third-party annotation tools with automated Python "
             "pipelines, cutting labelling cost and turnaround while improving {kw} coverage."},
    {"tags": ["AWS", "GCP", "CI/CD", "Performance Testing"],
     "text": "Benchmarked AWS SageMaker, GCP, and RunPod on cost, performance, and "
             "scalability to select the production stack for {kw} workloads."},
    {"tags": ["OCR", "Regression Testing", "Test Automation"],
     "text": "Built an OCR regression testing pipeline guarding release quality across "
             "every model iteration."},
    {"tags": ["CI/CD", "Allure", "Grafana", "JIRA"],
     "text": "Created Allure test reporting and Grafana dashboards giving the team "
             "real-time visibility into automation health and {kw} metrics."},
    {"tags": ["Linux", "E2E Testing", "Integration Testing"],
     "text": "Tested and validated deployments on Nvidia Jetson Nano and RTX 3900 edge "
             "hardware, covering {kw} scenarios end-to-end."},
    {"tags": ["GitHub Actions", "CI/CD", "Git"],
     "text": "Integrated GitHub Actions CI/CD pipelines so every merge triggered "
             "automated build, test, and reporting stages."},
]

ONEVEST_BULLETS = [
    {"tags": ["CI/CD", "GitHub Actions", "Allure", "JIRA", "Git"],
     "text": "Led the GitHub Actions CI/CD migration and built an Allure/Zephyr/Slack "
             "reporting tool that pushed {kw} results to the whole team automatically."},
    {"tags": ["GraphQL", "REST APIs", "Test Automation", "Integration Testing"],
     "text": "Implemented GraphQL entitlements and permissions testing, validating {kw} "
             "access rules across user roles on a client-server enterprise platform."},
    {"tags": ["Security Testing", "Debugging"],
     "text": "Built an IP whitelist security feature for the enterprise API, hardening "
             "access control for enterprise clients."},
    {"tags": ["JavaScript", "Python", "Test Automation", "Regression Testing"],
     "text": "Wrote JavaScript and Python automation scripts covering API and UI "
             "regression scenarios for release validation."},
]


def pick_bullets(bank: "list[dict]", jd_keywords: "list[str]", minimum: int = 4) -> "list[str]":
    """Score bullets by tag overlap with JD keywords; inject the top JD keyword
    each bullet supports into its {kw} slot. Pads with the strongest remaining
    bullets so each role always has at least `minimum` bullets."""
    kwset = set(jd_keywords)
    ranked = sorted(bank, key=lambda b: -len(kwset & set(b["tags"])))
    chosen = [b for b in ranked if kwset & set(b["tags"])]
    for b in ranked:
        if len(chosen) >= minimum:
            break
        if b not in chosen:
            chosen.append(b)

    out = []
    for b in chosen:
        # tag order encodes which keyword reads most naturally in the {kw} slot
        matched = [t for t in b["tags"] if t in kwset]
        kw = matched[0] if matched else b["tags"][0]
        out.append(b["text"].replace("{kw}", kw))
    return out


# ---------------------------------------------------------------
# 4. SKILLS SECTION — ALL relevant JD keywords must land (RULE_6)
# ---------------------------------------------------------------
SKILL_ROWS = {
    "Testing & Automation": ["Playwright", "Selenium", "WebdriverIO", "Cypress", "Appium",
                             "Test Automation", "E2E Testing", "Regression Testing",
                             "Integration Testing", "Unit Testing", "Manual Testing",
                             "Performance Testing", "Mobile Testing", "Security Testing",
                             "Accessibility Testing", "Cross-browser Testing", "Allure",
                             "TestRail", "Test Planning"],
    "Languages": ["TypeScript", "JavaScript", "Python", "Java", "C#", "SQL"],
    "APIs & Platforms": ["REST APIs", "GraphQL", "Microservices", "Kafka", "Linux", "Git",
                         "Debugging"],
    "CI/CD & Cloud": ["CI/CD", "Jenkins", "GitHub Actions", "GitLab CI", "Docker",
                      "Kubernetes", "Terraform", "Ansible", "AWS", "GCP", "Azure", "Grafana"],
    "AI/ML": ["Computer Vision", "Machine Learning", "OCR"],
    "Process": ["Agile/Scrum", "JIRA"],
}

# Defaults used to pad rows when the JD matches few keywords in that row
_ROW_DEFAULTS = {
    "Testing & Automation": ["Playwright", "Selenium", "Test Automation", "E2E Testing"],
    "Languages": ["TypeScript", "Python", "JavaScript", "SQL"],
    "APIs & Platforms": ["REST APIs", "GraphQL", "Linux", "Git"],
    "CI/CD & Cloud": ["CI/CD", "Jenkins", "GitHub Actions", "Docker", "AWS"],
    "AI/ML": [],
    "Process": ["Agile/Scrum", "JIRA"],
}


def build_skills(jd_keywords: "list[str]") -> "list[dict]":
    """Front-load JD keywords in each row; append any JD keyword that fits no
    row into a final 'Also Working With' row so nothing from the JD is dropped."""
    rows, placed = [], set()
    for label, members in SKILL_ROWS.items():
        hits = [k for k in jd_keywords if k in members]
        pad = [m for m in _ROW_DEFAULTS[label] if m not in hits]
        values = hits + pad[: max(0, 4 - len(hits))]
        if values:
            rows.append({"label": label, "value": ", ".join(values)})
            placed.update(hits)
    leftovers = [k for k in jd_keywords if k not in placed]
    if leftovers:
        rows.append({"label": "Also Working With", "value": ", ".join(leftovers)})
    return rows


# ---------------------------------------------------------------
# 5. SUMMARY + COVER LETTER TEMPLATES
# ---------------------------------------------------------------
_FAMILY_HEADLINE = {
    "sdet": "Senior SDET",
    "qa": "Senior QA Engineer",
    "devops": "QA / DevOps Engineer",
    "data": "AI/ML Quality Engineer",
    "swe": "Software Engineer",
}


def build_summary(role: str, family: str, jd_keywords: "list[str]") -> str:
    top = ", ".join(jd_keywords[:5]) if jd_keywords else "test automation, CI/CD, and APIs"
    return (f"{_FAMILY_HEADLINE[family]} with 5+ years across QA automation, backend "
            f"development, and AI systems, specialising in {top}. Proven record shipping "
            f"reliable releases for products serving 100K+ users, and building automation "
            f"frameworks and CI/CD pipelines that cut QA runtime by 75%.")


def build_cover_letter(company: str, role: str, jd_keywords: "list[str]",
                       notes: str = "") -> dict:
    top3 = ", ".join(jd_keywords[:3]) if jd_keywords else "test automation and CI/CD"
    paragraphs = [
        (f"I am writing to apply for the {role} position at {company}. With 5+ years "
         f"spanning QA automation, backend development, and AI systems, I bring exactly "
         f"the hands-on {top3} experience this role calls for."),
        (f"What draws me to {company} is the chance to apply my experience at scale. "
         f"At Global Relay I automated E2E and integration testing for a platform "
         f"serving 100K+ users, migrating a legacy Selenium suite to Playwright with "
         f"300+ automated cases and cutting CI runtime by 75%."),
        (f"Most recently at Encorp I owned quality for a computer-vision AI platform, "
         f"building regression pipelines, Allure/Grafana reporting, and GitHub Actions "
         f"CI/CD — the same {top3} skills highlighted in your posting."
         + (f" {notes}" if notes else "")),
        (f"I would welcome the opportunity to discuss how I can contribute to "
         f"{company}'s quality and engineering goals. Thank you for your consideration."),
    ]
    return {"paragraphs": paragraphs}


# ---------------------------------------------------------------
# 6. ENTRY POINT
# ---------------------------------------------------------------
def load_base_profile() -> dict:
    with open(os.path.abspath(PROFILE_PATH), encoding="utf-8") as f:
        return yaml.safe_load(f)


def verify_keywords_landed(payload: dict, jd_keywords: "list[str]") -> "list[str]":
    """RULE_6 check — return any JD keyword that failed to land in the payload."""
    import json
    blob = json.dumps(payload).lower()
    return [k for k in jd_keywords if k.lower() not in blob]


def tailor_resume(job_description: str, company: str, role: str,
                  filename_base: str, generate_cover_letter: bool = True,
                  cover_letter_notes: str = "") -> dict:
    jd_keywords = extract_keywords(job_description)
    # The company name itself is not a skill — drop it if the heuristic caught it
    jd_keywords = [k for k in jd_keywords
                   if k.lower() not in company.lower().replace(" ", "")]
    family = detect_role_family(role, job_description)

    payload = load_base_profile()
    payload["meta"] = {
        "company": company,
        "role": role,
        "filename_base": filename_base,
        "subtitle": (f"{role} — {', '.join(jd_keywords[:3])}" if jd_keywords else role),
    }
    payload["summary"] = build_summary(role, family, jd_keywords)
    payload["skills"] = build_skills(jd_keywords)

    for job in payload["experience"]:
        if job["company"] == "Encorp":  # RULE_2
            job["title"] = ENCORP_TITLES[family]
            job["bullets"] = pick_bullets(ENCORP_BULLETS, jd_keywords, minimum=5)
        elif job["company"] == "Onevest":  # RULE_2
            job["title"] = ONEVEST_TITLES[family]
            job["bullets"] = pick_bullets(ONEVEST_BULLETS, jd_keywords, minimum=3)
        # all other companies untouched — RULE_3

    if generate_cover_letter:
        payload["cover_letter"] = build_cover_letter(company, role, jd_keywords,
                                                     cover_letter_notes)

    missed = verify_keywords_landed(payload, jd_keywords)
    if missed:
        # Guarantee RULE_6 even for heuristic keywords that fit no skill row
        payload["skills"].append({"label": "Additional Keywords", "value": ", ".join(missed)})
    return payload
