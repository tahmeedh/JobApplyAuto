"""Optional local-LLM polish layer + Claude_Resumes corpus tooling.

No external API calls (RULE_8). The rule-engine output is already valid —
everything in this module is best-effort:
  - build_corpus():      extract text from every PDF/DOCX in Claude_Resumes/
  - most_similar():      keyword-overlap retrieval of past resumes (few-shot)
  - polish_with_local_llm(): rewrite summary + Encorp/Onevest bullets via a
                             local Ollama model; no-op if Ollama is absent
  - export_finetune_jsonl(): dump the corpus as JSONL for local fine-tuning
"""
import json
import os
import subprocess

CORPUS_DIR = os.path.join(os.path.dirname(__file__), "..", "Claude_Resumes")
OLLAMA_MODEL = os.environ.get("TAILOR_OLLAMA_MODEL", "llama3.1")


def build_corpus(corpus_dir: str = None) -> "list[dict]":
    """Extract text from every PDF/DOCX in Claude_Resumes/ -> [{file, text}]."""
    corpus_dir = os.path.abspath(corpus_dir or CORPUS_DIR)
    if not os.path.isdir(corpus_dir):
        return []
    corpus = []
    for name in os.listdir(corpus_dir):
        path = os.path.join(corpus_dir, name)
        try:
            if name.lower().endswith(".pdf"):
                from pypdf import PdfReader
                text = "\n".join(p.extract_text() or "" for p in PdfReader(path).pages)
            elif name.lower().endswith(".docx"):
                from docx import Document
                text = "\n".join(p.text for p in Document(path).paragraphs)
            else:
                continue
            if text.strip():
                corpus.append({"file": name, "text": text})
        except Exception:
            continue  # unreadable/missing-dependency files just drop out
    return corpus


def most_similar(jd_keywords: "list[str]", corpus: "list[dict]", n: int = 3) -> "list[dict]":
    """Rank past resumes by JD-keyword overlap — cheap, deterministic retrieval."""
    def score(doc):
        text = doc["text"].lower()
        return sum(1 for k in jd_keywords if k.lower() in text)
    return sorted(corpus, key=score, reverse=True)[:n]


def _ollama_available() -> bool:
    try:
        subprocess.run(["ollama", "--version"], capture_output=True, timeout=10)
        return True
    except Exception:
        return False


def polish_with_local_llm(payload: dict, jd_keywords: "list[str]") -> dict:
    """OPTIONAL: rewrite only summary + Encorp/Onevest bullets via local Ollama,
    using the most similar past resumes as few-shot style examples.
    Returns the payload unchanged if Ollama is not installed or anything fails."""
    if not _ollama_available():
        return payload

    examples = most_similar(jd_keywords, build_corpus())
    encorp = next((j for j in payload["experience"] if j["company"] == "Encorp"), None)
    onevest = next((j for j in payload["experience"] if j["company"] == "Onevest"), None)

    prompt = (
        "You are polishing resume text. Rewrite the summary and bullets below so they "
        "flow naturally. Keep every technical keyword exactly as written. Do not invent "
        "achievements. Return ONLY valid JSON with keys: summary, encorp, onevest "
        "(encorp/onevest are arrays of bullet strings).\n\n"
        "Style examples from past resumes:\n"
        + "\n---\n".join(e["text"][:1500] for e in examples)
        + "\n\nText to polish:\n"
        + json.dumps({
            "summary": payload.get("summary", ""),
            "encorp": encorp["bullets"] if encorp else [],
            "onevest": onevest["bullets"] if onevest else [],
        })
    )
    try:
        result = subprocess.run(["ollama", "run", OLLAMA_MODEL, prompt],
                                capture_output=True, text=True, timeout=180, check=True,
                                encoding="utf-8", errors="replace")
        raw = result.stdout.strip()
        start, end = raw.find("{"), raw.rfind("}")
        polished = json.loads(raw[start:end + 1])
        if isinstance(polished.get("summary"), str) and polished["summary"]:
            payload["summary"] = polished["summary"]
        if encorp and isinstance(polished.get("encorp"), list) and polished["encorp"]:
            encorp["bullets"] = [str(b) for b in polished["encorp"]]
        if onevest and isinstance(polished.get("onevest"), list) and polished["onevest"]:
            onevest["bullets"] = [str(b) for b in polished["onevest"]]
    except Exception:
        pass  # rules-only output is already valid — LLM polish is best-effort
    return payload


def export_finetune_jsonl(out_path: str = None) -> str:
    """Dump (filename -> resume text) pairs for future local fine-tuning."""
    out_path = out_path or os.path.join(CORPUS_DIR, "finetune_dataset.jsonl")
    with open(out_path, "w", encoding="utf-8") as f:
        for doc in build_corpus():
            f.write(json.dumps({"input": doc["file"], "output": doc["text"]}) + "\n")
    return out_path
