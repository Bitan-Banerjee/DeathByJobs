"""Derive a clean base_resume.md from a candidate's resume.docx.

Uses python-docx for extraction and the configured LLM to reformat the raw
text into structured Markdown (Summary, Experience, Skills, Education).
"""

import os
import time
from pathlib import Path

from .config_loader import get_resume_paths
from .llm_client import generate_text, LLMError


BASE_DIR = Path(__file__).resolve().parent.parent.parent


def _extract_text_from_docx(docx_path: Path) -> str:
    """Extract raw text from a .docx file, preserving basic paragraph breaks."""
    try:
        from docx import Document
    except ImportError as e:
        raise ImportError("python-docx is required to parse resume.docx") from e

    doc = Document(str(docx_path))
    paragraphs = [p.text.strip() for p in doc.paragraphs if p.text.strip()]
    return "\n\n".join(paragraphs)


def _build_reformat_prompt(raw_text: str) -> str:
    return f"""You are an expert resume formatter. Convert the following raw resume text into clean, professional Markdown.

STRICT RULES:
1. Do NOT invent, add, or hallucinate any experience, skills, education, or metrics that are not present in the original text.
2. Preserve all company names, job titles, employment dates, and education details exactly.
3. Do NOT wrap the output in ```markdown or any code fences.
4. Use only these sections: ## Professional Summary, ## Experience, ## Skills, ## Education, ## Certifications (if any).
5. Keep the content concise and ATS-friendly.
6. Maintain the candidate's original voice and claims.

RAW RESUME TEXT:
'''
{raw_text[:6000]}
'''

OUTPUT ONLY THE REFORMATTED MARKDOWN:"""


def derive_base_resume(force: bool = False) -> Path | None:
    """Create base_resume.md from resume.docx if missing or forced.

    Returns:
        Path to the generated base_resume.md, or None if no resume.docx exists.
    """
    docx_path, md_path = get_resume_paths()

    if not docx_path.exists():
        print(f"❌ Resume not found at: {docx_path}")
        return None

    if md_path.exists() and not force:
        print(f"✅ base_resume.md already exists at: {md_path}")
        return md_path

    print("📄 Extracting text from resume.docx...")
    raw_text = _extract_text_from_docx(docx_path)

    print("🧠 Asking LLM to reformat resume into Markdown...")
    try:
        markdown = generate_text(_build_reformat_prompt(raw_text), temperature=0.1)
    except LLMError as e:
        print(f"⚠️ LLM reformatting failed: {e}. Falling back to plain-text extraction.")
        markdown = f"## Raw Resume\n\n{raw_text}"

    md_path.parent.mkdir(parents=True, exist_ok=True)
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(markdown.strip() + "\n")

    print(f"✅ Derived base_resume.md saved to: {md_path}")
    return md_path


def ensure_base_resume() -> Path | None:
    """Ensure base_resume.md exists, deriving it if needed."""
    _, md_path = get_resume_paths()
    if md_path.exists():
        return md_path
    return derive_base_resume()


if __name__ == "__main__":
    derive_base_resume(force=True)
