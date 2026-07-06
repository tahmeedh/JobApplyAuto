"""Resume tailoring pipeline entry point.

JD -> rule engine -> (optional local LLM polish) -> resume PDF + cover letter
PDF + payload JSON, all stored in Claude_Resumes/ (RULE_7 — the folder is both
the archive and the local-LLM corpus).

Usage:
    python orchestrator.py <jd_file> <company> <role> [--output-dir DIR]
                           [--no-cover-letter] [--no-llm]

The last stdout line is `RESULT_JSON:{...}` so callers (e.g. the career-ops
bot) can parse the generated file paths reliably.
"""
import argparse
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from agents.tailor_rules import tailor_resume, extract_keywords
from agents.local_llm import polish_with_local_llm
from generators.pdf_generator import (generate_resume_pdf, generate_cover_letter_pdf,
                                      close_driver)

OUTPUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "Claude_Resumes")


def _sanitize(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]", "", value.replace(" ", ""))


def run(job_description: str, company: str, role: str,
        output_dir: str = OUTPUT_DIR, generate_cover_letter: bool = True,
        use_local_llm: bool = True) -> dict:
    """Full pipeline. Returns {"resume": path, "cover_letter": path|None, "payload": dict}."""
    os.makedirs(output_dir, exist_ok=True)
    filename_base = f"TahmeedHossain_{_sanitize(company)}_{_sanitize(role)}"

    print(f"[1/4] Extracting JD keywords and applying tailoring rules "
          f"for {role} at {company}...")
    payload = tailor_resume(
        job_description=job_description,
        company=company,
        role=role,
        filename_base=filename_base,
        generate_cover_letter=generate_cover_letter,
    )

    if use_local_llm:
        print("[2/4] Local LLM polish (skipped automatically if Ollama absent)...")
        payload = polish_with_local_llm(payload, extract_keywords(job_description))
    else:
        print("[2/4] Local LLM polish disabled (--no-llm).")

    # Payload JSON is the single source of truth — saved next to the PDFs
    payload_path = os.path.join(output_dir, f"{filename_base}_payload.json")
    with open(payload_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)

    print("[3/4] Generating resume PDF...")
    resume_pdf = generate_resume_pdf(payload, output_dir)
    print(f"  -> {resume_pdf}")

    cl_pdf = None
    if generate_cover_letter:
        print("[4/4] Generating cover letter PDF...")
        cl_pdf = generate_cover_letter_pdf(payload, output_dir)
        print(f"  -> {cl_pdf}")
    else:
        print("[4/4] Cover letter skipped.")

    close_driver()
    return {"resume": resume_pdf, "cover_letter": cl_pdf, "payload_json": payload_path,
            "payload": payload}


def main():
    parser = argparse.ArgumentParser(description="Tailor a resume for a job description.")
    parser.add_argument("jd_file", help="Path to a text file containing the job description")
    parser.add_argument("company")
    parser.add_argument("role")
    parser.add_argument("--output-dir", default=OUTPUT_DIR)
    parser.add_argument("--no-cover-letter", action="store_true")
    parser.add_argument("--no-llm", action="store_true",
                        help="Skip the optional local Ollama polish pass")
    args = parser.parse_args()

    with open(args.jd_file, encoding="utf-8", errors="replace") as f:
        jd = f.read()

    result = run(jd, args.company, args.role, output_dir=args.output_dir,
                 generate_cover_letter=not args.no_cover_letter,
                 use_local_llm=not args.no_llm)

    # Machine-readable trailer for callers (career-ops bot parses this line)
    print("RESULT_JSON:" + json.dumps({
        "resume": result["resume"],
        "cover_letter": result["cover_letter"],
        "payload_json": result["payload_json"],
    }))


if __name__ == "__main__":
    main()
