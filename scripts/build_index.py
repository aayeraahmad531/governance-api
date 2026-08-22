import os
import re
import argparse
import json
import urllib.request
from typing import List, Dict, Any
import numpy as np

import torch
from bs4 import BeautifulSoup
from sentence_transformers import SentenceTransformer
from transformers import AutoTokenizer, AutoModel

MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"
SOURCE_VERSION = "02024R1689-20260727"
RETRIEVAL_DATE = "2026-08-21"


def chunk_text(text: str, chunk_size: int = 1200, overlap: int = 150) -> List[str]:
    """Splits text into chunks snapped strictly to sentence boundaries."""
    clean_text = re.sub(r"\s+", " ", text).strip()
    if not clean_text:
        return []
    if len(clean_text) <= chunk_size:
        return [clean_text]

    sentences = re.split(r"(?<=[.!?])\s+", clean_text)
    chunks = []
    current_chunk = []
    current_len = 0

    for sentence in sentences:
        s = sentence.strip()
        if not s:
            continue

        if current_len + len(s) > chunk_size and current_chunk:
            chunks.append(" ".join(current_chunk))
            overlap_chunk = []
            overlap_len = 0
            for prev_s in reversed(current_chunk):
                if overlap_len + len(prev_s) <= overlap:
                    overlap_chunk.insert(0, prev_s)
                    overlap_len += len(prev_s) + 1
                else:
                    break
            current_chunk = overlap_chunk
            current_len = overlap_len

        current_chunk.append(s)
        current_len += len(s) + 1

    if current_chunk:
        chunks.append(" ".join(current_chunk))

    return chunks


def parse_eu_ai_act_html(html_path: str) -> tuple[List[str], List[Dict[str, Any]], int]:
    with open(html_path, "r", encoding="utf-8") as f:
        html = f.read()

    soup = BeautifulSoup(html, "html.parser")
    divs = soup.find_all("div", class_="eli-subdivision")

    parsed_chunks = []
    metadata = []
    dropped_count = 0

    articles_count = 0
    annexes_count = 0

    for div in divs:
        div_text = div.get_text(separator="\n").strip()
        lines = [l.strip() for l in div_text.split("\n") if l.strip()]
        if not lines:
            continue
        
        m_art = re.match(r"^Article\s+(\d+)\b", lines[0], re.IGNORECASE)
        if m_art:
            art_num = int(m_art.group(1))
            title = lines[1] if len(lines) > 1 else f"Article {art_num}"
            
            full_art_text = " ".join(lines)
            sub_chunks = chunk_text(full_art_text)
            
            for c in sub_chunks:
                parsed_chunks.append(c)
                metadata.append({
                    "article": art_num,
                    "title": title,
                    "source_version": SOURCE_VERSION
                })
            articles_count += 1

    annex_paragraphs = soup.find_all(["p", "div", "h1", "h2", "h3"], class_=re.compile("title-annex", re.IGNORECASE))
    for p in annex_paragraphs:
        p_text = p.get_text().strip()
        m_annex = re.match(r"^ANNEX\s+([I|V|X\d]+)\b(.*)", p_text, re.IGNORECASE)
        if m_annex:
            annex_id = f"Annex {m_annex.group(1)}"
            annex_lines = [p_text]
            curr = p.next_sibling
            while curr and not (hasattr(curr, "get") and curr.get("class") and "title-annex" in str(curr.get("class"))):
                if hasattr(curr, "get_text"):
                    t = curr.get_text().strip()
                    if t:
                        annex_lines.append(t)
                curr = curr.next_sibling
            
            annex_title = annex_lines[1] if len(annex_lines) > 1 else annex_id
            full_annex_text = " ".join(annex_lines)
            sub_chunks = chunk_text(full_annex_text)
            
            for c in sub_chunks:
                parsed_chunks.append(c)
                metadata.append({
                    "article": annex_id,
                    "title": annex_title,
                    "source_version": SOURCE_VERSION
                })
            annexes_count += 1

    print(f"=== EU AI Act Parsing Summary ===")
    print(f"Articles parsed: {articles_count} (Articles 1-113)")
    print(f"Annexes parsed: {annexes_count} (Annexes I-XIV)")
    print(f"Recitals: EXCLUDED (0 recital chunks indexed)")
    print(f"Total chunks created: {len(parsed_chunks)}")

    return parsed_chunks, metadata, dropped_count


def get_refined_bias_lexicon() -> tuple[List[str], List[Dict[str, Any]]]:
    """
    Generates realistic job posting bias entries.
    Feminine-coded entries and standard professional qualifiers have severity 'info'
    and do NOT count toward overall_bias_score.
    """
    entries = [
        # Masculine-coded (High/Medium/Low severity)
        {"term": "ninja", "category": "gender", "severity": "medium", "replacement": "expert engineer", "context": "seeking a coding ninja to build scalable systems."},
        {"term": "rockstar", "category": "gender", "severity": "medium", "replacement": "high-performing specialist", "context": "looking for a rockstar developer who delivers under pressure."},
        {"term": "hungry", "category": "gender", "severity": "low", "replacement": "highly motivated", "context": "we need hungry sales professionals to drive growth."},
        {"term": "aggressive", "category": "gender", "severity": "high", "replacement": "ambitious", "context": "seeking an aggressive leader to conquer market share."},
        {"term": "dominant", "category": "gender", "severity": "high", "replacement": "established market leader", "context": "dominant force in enterprise software."},
        {"term": "crush", "category": "gender", "severity": "medium", "replacement": "exceed targets", "context": "looking for someone ready to crush quarterly quotas."},
        {"term": "competitive", "category": "gender", "severity": "low", "replacement": "goal-oriented", "context": "thrives in a competitive sales environment."},
        {"term": "fearless", "category": "gender", "severity": "medium", "replacement": "resilient", "context": "seeking a fearless innovator to spearhead new initiatives."},
        {"term": "work hard play hard", "category": "gender", "severity": "medium", "replacement": "high-energy team culture", "context": "intense work hard play hard culture."},
        {"term": "killer", "category": "gender", "severity": "high", "replacement": "exceptional feature", "context": "looking for a killer instinct in deal closing."},
        {"term": "alpha", "category": "gender", "severity": "high", "replacement": "top performer", "context": "seeking alpha personalities for executive roles."},
        {"term": "hard-charging", "category": "gender", "severity": "medium", "replacement": "proactive", "context": "hard-charging team of account managers."},
        {"term": "guru", "category": "gender", "severity": "medium", "replacement": "domain authority", "context": "hiring a cloud architecture guru."},
        {"term": "hacker", "category": "gender", "severity": "medium", "replacement": "creative developer", "context": "growth hacker wanted for fast-moving team."},
        {"term": "ruthless", "category": "gender", "severity": "high", "replacement": "decisive", "context": "ruthless prioritization of customer needs."},

        # Feminine-coded / Inclusive Phrasing (Severity: 'inclusive' — observation only, excluded from score calculation)
        {"term": "nurturing", "category": "gender", "severity": "inclusive", "replacement": "supportive leadership", "context": "nurturing team environment encouraging growth."},
        {"term": "supportive", "category": "gender", "severity": "inclusive", "replacement": "collaborative", "context": "seeking a supportive colleague for client relations."},
        {"term": "collaborative", "category": "gender", "severity": "inclusive", "replacement": "cross-functional alignment", "context": "collaborative mindset across engineering units."},
        {"term": "empathetic", "category": "gender", "severity": "inclusive", "replacement": "user-centric", "context": "empathetic communicator for customer success."},
        {"term": "warm", "category": "gender", "severity": "inclusive", "replacement": "welcoming", "context": "warm and friendly office environment."},
        {"term": "helpful", "category": "gender", "severity": "inclusive", "replacement": "service-oriented", "context": "helpful demeanor in resolving support tickets."},
        {"term": "caring", "category": "gender", "severity": "inclusive", "replacement": "attentive", "context": "caring approach to employee well-being."},
        {"term": "soft-spoken", "category": "gender", "severity": "inclusive", "replacement": "thoughtful communicator", "context": "soft-spoken professional for sensitive accounts."},
        {"term": "sensitive", "category": "gender", "severity": "inclusive", "replacement": "attuned to user feedback", "context": "sensitive to client requirements and deadlines."},
        {"term": "relationship-builder", "category": "gender", "severity": "inclusive", "replacement": "account manager", "context": "strong relationship-builder with enterprise buyers."},
        {"term": "compassionate", "category": "gender", "severity": "inclusive", "replacement": "considerate", "context": "compassionate leader in healthcare administration."},
        {"term": "team player", "category": "gender", "severity": "inclusive", "replacement": "collaborator", "context": "essential team player in product design."},
        {"term": "team-oriented", "category": "gender", "severity": "inclusive", "replacement": "collaborative", "context": "team-oriented work environment."},
        {"term": "intuitive", "category": "gender", "severity": "inclusive", "replacement": "insightful", "context": "intuitive grasp of UX research."},
        {"term": "peacemaker", "category": "gender", "severity": "inclusive", "replacement": "conflict mediator", "context": "peacemaker during high-stakes client negotiations."},
        {"term": "consensus-builder", "category": "gender", "severity": "inclusive", "replacement": "cross-functional coordinator", "context": "proven consensus-builder among department heads."},
        {"term": "approachable", "category": "gender", "severity": "inclusive", "replacement": "accessible", "context": "approachable leader with open-door policy."},

        # Standard / Ambiguous Qualifiers (Severity: 'neutral' — observation only, excluded from score calculation)
        {"term": "fast-paced", "category": "age", "severity": "neutral", "replacement": "dynamic environment", "context": "fast-paced agile environment."},
        {"term": "experienced", "category": "age", "severity": "neutral", "replacement": "skilled", "context": "experienced software engineer."},
        {"term": "senior", "category": "age", "severity": "neutral", "replacement": "lead", "context": "senior software engineer."},
        {"term": "communication skills", "category": "gender", "severity": "neutral", "replacement": "interpersonal articulation", "context": "strong verbal and written communication skills."},
        {"term": "detail-oriented", "category": "gender", "severity": "neutral", "replacement": "meticulous", "context": "detail-oriented auditor for financial reports."},
        {"term": "dependable", "category": "gender", "severity": "neutral", "replacement": "reliable", "context": "dependable asset to our operations team."},
        {"term": "interpersonal skills", "category": "gender", "severity": "neutral", "replacement": "communication capabilities", "context": "exceptional interpersonal skills required."},


        # Gendered Titles & Common Pronouns (High/Medium/Low severity)
        {"term": "guys", "category": "gender", "severity": "medium", "replacement": "team / everyone", "context": "looking for guys who want to build cool products."},
        {"term": "he/she", "category": "gender", "severity": "low", "replacement": "they", "context": "the ideal candidate, he/she will be responsible for client calls."},
        {"term": "he/his", "category": "gender", "severity": "high", "replacement": "they/them", "context": "the applicant must demonstrate his coding skills."},
        {"term": "salesman", "category": "gender", "severity": "high", "replacement": "sales representative", "context": "seeking an experienced salesman for regional accounts."},
        {"term": "chairman", "category": "gender", "severity": "high", "replacement": "chairperson", "context": "reports directly to the board chairman."},
        {"term": "manpower", "category": "gender", "severity": "high", "replacement": "workforce / staffing", "context": "sufficient manpower to complete project milestones."},
        {"term": "man-hours", "category": "gender", "severity": "high", "replacement": "person-hours / labor hours", "context": "estimated at 500 man-hours of engineering."},
        {"term": "waiter/waitress", "category": "gender", "severity": "medium", "replacement": "server", "context": "hiring event waiter/waitress staff."},
        {"term": "right-hand man", "category": "gender", "severity": "medium", "replacement": "chief deputy / primary assistant", "context": "seeking a right-hand man for the CEO."},
        {"term": "middleman", "category": "gender", "severity": "medium", "replacement": "intermediary", "context": "cutting out the middleman in logistics."},
        {"term": "handyman", "category": "gender", "severity": "high", "replacement": "maintenance technician", "context": "facility handyman for office repairs."},
        {"term": "spokesman", "category": "gender", "severity": "high", "replacement": "spokesperson", "context": "media spokesman for corporate communications."},
        {"term": "tradesman", "category": "gender", "severity": "high", "replacement": "skilled trade professional", "context": "licensed tradesman for electrical work."},
        {"term": "cameraman", "category": "gender", "severity": "high", "replacement": "camera operator", "context": "seeking broadcast cameraman for live events."},
        {"term": "fireman", "category": "gender", "severity": "high", "replacement": "firefighter", "context": "industrial safety fireman on shift."},
        {"term": "mailman", "category": "gender", "severity": "high", "replacement": "mail carrier", "context": "courier mailman for internal delivery."},

        # Age Proxies (High/Medium/Low severity)
        {"term": "young", "category": "age", "severity": "high", "replacement": "motivated candidate", "context": "looking for young, energetic candidates."},
        {"term": "energetic", "category": "age", "severity": "medium", "replacement": "dynamic", "context": "energetic environment for fast learners."},
        {"term": "digital native", "category": "age", "severity": "high", "replacement": "tech-proficient", "context": "must be a digital native fluent in social media."},
        {"term": "recent graduate", "category": "age", "severity": "medium", "replacement": "entry-level candidate", "context": "position designed for a recent graduate."},
        {"term": "fresh", "category": "age", "severity": "medium", "replacement": "new perspective", "context": "seeking fresh talent straight out of school."},
        {"term": "high-energy", "category": "age", "severity": "medium", "replacement": "proactive", "context": "high-energy workplace culture."},
        {"term": "mature", "category": "age", "severity": "high", "replacement": "experienced", "context": "seeking mature judgment for executive role."},
        {"term": "overqualified", "category": "age", "severity": "high", "replacement": "highly experienced", "context": "candidates with >20 yrs may be overqualified."},
        {"term": "10+ years", "category": "age", "severity": "medium", "replacement": "relevant track record", "context": "requires 10+ years of consecutive industry experience."},
        {"term": "15+ years", "category": "age", "severity": "high", "replacement": "demonstrated expertise", "context": "minimum 15+ years post-qualification experience."},
        {"term": "fast-paced youth environment", "category": "age", "severity": "high", "replacement": "agile workplace", "context": "thrive in a fast-paced youth environment."},
        {"term": "youthful culture", "category": "age", "severity": "high", "replacement": "innovative culture", "context": "vibrant company with a youthful culture."},
        {"term": "vibrant young team", "category": "age", "severity": "high", "replacement": "dynamic team", "context": "join our vibrant young team of developers."},

        # Cultural / Exclusionary Phrasing (High/Medium/Low severity)
        {"term": "cultural fit", "category": "cultural", "severity": "high", "replacement": "value alignment", "context": "hiring based on strict cultural fit."},
        {"term": "native speaker", "category": "cultural", "severity": "high", "replacement": "professional fluency", "context": "must be a native speaker of English."},
        {"term": "Western", "category": "cultural", "severity": "high", "replacement": "international", "context": "experience in Western markets preferred."},
        {"term": "no accent", "category": "cultural", "severity": "high", "replacement": "clear communication", "context": "must speak with no accent on phone calls."},
        {"term": "must be local", "category": "cultural", "severity": "medium", "replacement": "relocation assistance available", "context": "applicant must be local to the metro area."},
        {"term": "US-born", "category": "cultural", "severity": "high", "replacement": "authorized to work in US", "context": "preference for US-born candidates."},
        {"term": "Ivy League only", "category": "cultural", "severity": "high", "replacement": "accredited university degree", "context": "recruiting from Ivy League only institutions."},
        {"term": "traditional background", "category": "cultural", "severity": "medium", "replacement": "relevant professional experience", "context": "prefer candidates from a traditional background."},
        {"term": "native English", "category": "cultural", "severity": "high", "replacement": "fluent English", "context": "native English writing skills required."},
        {"term": "foreign accent", "category": "cultural", "severity": "high", "replacement": "effective communication", "context": "role not suitable for applicants with foreign accent."}
    ]

    chunks = []
    meta = []
    for e in entries:
        chunk = f"Biased term: '{e['term']}' (Category: {e['category']}, Severity: {e['severity']}). Suggested replacement: '{e['replacement']}'. Example context: {e['context']}"
        chunks.append(chunk)
        meta.append(e)

    return chunks, meta


def fetch_wikipedia_facts() -> tuple[List[str], List[Dict[str, Any]]]:
    """
    Fetches REAL full Wikipedia article extracts via Wikipedia REST API.
    Every chunk carries source_url and retrieved_date metadata.
    """
    topics_map = {
        "Discovery of Radium": "Radium",
        "The Apollo 11 mission": "Apollo_11",
        "The EU AI Act": "Artificial_Intelligence_Act",
        "Photosynthesis": "Photosynthesis",
        "The Indian Space Research Organisation": "Indian_Space_Research_Organisation"
    }

    chunks = []
    metadata = []

    print("=== Fetching Real Wikipedia Articles via Wikipedia REST API ===")
    for topic, page_title in topics_map.items():
        source_url = f"https://en.wikipedia.org/wiki/{page_title}"
        api_url = f"https://en.wikipedia.org/api/rest_v1/page/html/{page_title}"
        req = urllib.request.Request(api_url, headers={"User-Agent": "GovernanceAPI/1.0 (dev@governance-api.com)"})

        try:
            with urllib.request.urlopen(req) as response:
                html = response.read().decode("utf-8")
                soup = BeautifulSoup(html, "html.parser")
                text = soup.get_text(separator=" ").strip()
                
                # Split text into sentence-aligned chunks
                topic_chunks = chunk_text(text, chunk_size=1000, overlap=150)
                
                # Limit to top 20 substantive chunks per topic (~100 total facts chunks)
                substantive_chunks = [c for c in topic_chunks if len(c) > 200][:20]
                
                print(f"Topic: '{topic}' -> Fetched {len(text)} chars, created {len(substantive_chunks)} real Wikipedia chunks")
                
                for c in substantive_chunks:
                    chunks.append(c)
                    metadata.append({
                        "topic": topic,
                        "source_url": source_url,
                        "retrieved_date": RETRIEVAL_DATE
                    })
        except Exception as e:
            print(f"Error fetching Wikipedia page for '{topic}' ({page_title}): {e}")

    return chunks, metadata


def export_onnx_model(output_dir: str):
    """Exports all-MiniLM-L6-v2 model and tokenizer for server runtime ONNX inference."""
    onnx_path = os.path.join(output_dir, "model.onnx")
    tokenizer_dir = os.path.join(output_dir, "tokenizer")
    os.makedirs(output_dir, exist_ok=True)

    print(f"Exporting ONNX model to '{onnx_path}'...")
    tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME)
    model = AutoModel.from_pretrained(MODEL_NAME)
    model.eval()

    tokenizer.save_pretrained(tokenizer_dir)

    dummy_text = "automated decision without human review"
    inputs = tokenizer(dummy_text, return_tensors="pt", padding=True, truncation=True)

    input_names = ["input_ids", "attention_mask", "token_type_ids"]
    output_names = ["last_hidden_state"]

    dynamic_axes = {
        "input_ids": {0: "batch", 1: "sequence"},
        "attention_mask": {0: "batch", 1: "sequence"},
        "token_type_ids": {0: "batch", 1: "sequence"},
        "last_hidden_state": {0: "batch", 1: "sequence"}
    }

    torch.onnx.export(
        model,
        (inputs["input_ids"], inputs["attention_mask"], inputs["token_type_ids"]),
        onnx_path,
        input_names=input_names,
        output_names=output_names,
        dynamic_axes=dynamic_axes,
        opset_version=18
    )
    print(f"Exported ONNX model successfully ({os.path.getsize(onnx_path)} bytes)")


def build_and_save_index(name: str, chunks: List[str], meta: List[Dict[str, Any]], model: SentenceTransformer, output_dir: str):
    os.makedirs(output_dir, exist_ok=True)
    out_path = os.path.join(output_dir, f"{name}.npz")

    print(f"Embedding {len(chunks)} chunks for index '{name}'...")
    embeddings = model.encode(chunks, convert_to_numpy=True, show_progress_bar=False)
    
    norms = np.linalg.norm(embeddings, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    vecs = (embeddings / norms).astype(np.float32)

    meta_json_strs = [json.dumps(m) for m in meta]
    np.savez_compressed(out_path, vecs=vecs, chunks=np.array(chunks), meta=np.array(meta_json_strs))
    print(f"Saved {out_path} ({os.path.getsize(out_path)} bytes, {len(chunks)} chunks)")


def main():
    parser = argparse.ArgumentParser(description="Precompute .npz search indexes")
    parser.add_argument("--source", type=str, help="Path to raw source file or folder")
    parser.add_argument("--name", type=str, help="Index name (eu_ai_act | bias_lexicon | facts | all)")
    args = parser.parse_args()

    output_dir = "data"
    export_onnx_model(output_dir)

    print(f"Loading embedding model '{MODEL_NAME}'...")
    model = SentenceTransformer(MODEL_NAME)

    name = args.name or "all"

    if name in ["eu_ai_act", "all"]:
        source_file = args.source or r"data\raw\eu_ai_act\Consolidated TEXT_ 32024R1689 — EN — 27.07.2026.html"
        if os.path.isdir(source_file):
            files = [os.path.join(source_file, f) for f in os.listdir(source_file) if f.endswith(".html")]
            if files:
                source_file = files[0]

        chunks, meta, dropped = parse_eu_ai_act_html(source_file)
        build_and_save_index("eu_ai_act", chunks, meta, model, output_dir)

    if name in ["bias_lexicon", "all"]:
        chunks, meta = get_refined_bias_lexicon()
        build_and_save_index("bias_lexicon", chunks, meta, model, output_dir)

    if name in ["facts", "all"]:
        chunks, meta = fetch_wikipedia_facts()
        build_and_save_index("facts", chunks, meta, model, output_dir)

    print("\n=== FINAL CORPUS INDEX SUMMARY ===")
    for idx_file in ["eu_ai_act.npz", "bias_lexicon.npz", "facts.npz"]:
        p = os.path.join(output_dir, idx_file)
        if os.path.exists(p):
            d = np.load(p, allow_pickle=True)
            print(f"Index '{idx_file}': {len(d['chunks'])} chunks")

    print("\nIndex build complete!")


if __name__ == "__main__":
    main()
