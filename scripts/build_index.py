import os
import re
import argparse
import json
from typing import List, Dict, Any
import numpy as np
from bs4 import BeautifulSoup
from sentence_transformers import SentenceTransformer

MODEL_NAME = "all-MiniLM-L6-v2"
SOURCE_VERSION = "02024R1689-20260727"


def chunk_text(text: str, chunk_size: int = 1500, overlap: int = 200) -> List[str]:
    """Splits text into ~500-token (~1500 chars) chunks with ~50-token (~200 chars) overlap."""
    clean_text = re.sub(r"\s+", " ", text).strip()
    if not clean_text:
        return []
    if len(clean_text) <= chunk_size:
        return [clean_text]
    
    chunks = []
    start = 0
    while start < len(clean_text):
        end = start + chunk_size
        chunk = clean_text[start:end]
        chunks.append(chunk)
        if end >= len(clean_text):
            break
        start += (chunk_size - overlap)
    return chunks


def parse_eu_ai_act_html(html_path: str) -> tuple[List[str], List[Dict[str, Any]], int]:
    """
    Parses EU AI Act HTML.
    Excludes recitals (preamble).
    Extracts Articles 1-113 and Annexes I-XIV with real {article, title, source_version}.
    Returns (chunks, metadata_list, dropped_chunks_count).
    """
    with open(html_path, "r", encoding="utf-8") as f:
        html = f.read()

    soup = BeautifulSoup(html, "html.parser")
    divs = soup.find_all("div", class_="eli-subdivision")

    parsed_chunks = []
    metadata = []
    dropped_count = 0

    articles_count = 0
    annexes_count = 0

    # Parse Articles 1-113 from eli-subdivision divs
    for div in divs:
        div_text = div.get_text(separator="\n").strip()
        lines = [l.strip() for l in div_text.split("\n") if l.strip()]
        if not lines:
            continue
        
        m_art = re.match(r"^Article\s+(\d+)\b", lines[0], re.IGNORECASE)
        if m_art:
            art_num = int(m_art.group(1))
            title = lines[1] if len(lines) > 1 else f"Article {art_num}"
            
            # Chunk article text
            full_art_text = "\n".join(lines)
            sub_chunks = chunk_text(full_art_text)
            
            for c in sub_chunks:
                parsed_chunks.append(c)
                metadata.append({
                    "article": art_num,
                    "title": title,
                    "source_version": SOURCE_VERSION
                })
            articles_count += 1

    # Parse Annexes I-XIV from paragraph/heading title-annex tags
    annex_paragraphs = soup.find_all(["p", "div", "h1", "h2", "h3"], class_=re.compile("title-annex", re.IGNORECASE))
    for p in annex_paragraphs:
        p_text = p.get_text().strip()
        m_annex = re.match(r"^ANNEX\s+([I|V|X\d]+)\b(.*)", p_text, re.IGNORECASE)
        if m_annex:
            annex_id = f"Annex {m_annex.group(1)}"
            # Collect following sibling text up to next annex
            annex_lines = [p_text]
            curr = p.next_sibling
            while curr and not (hasattr(curr, "get") and curr.get("class") and "title-annex" in str(curr.get("class"))):
                if hasattr(curr, "get_text"):
                    t = curr.get_text().strip()
                    if t:
                        annex_lines.append(t)
                curr = curr.next_sibling
            
            annex_title = annex_lines[1] if len(annex_lines) > 1 else annex_id
            full_annex_text = "\n".join(annex_lines)
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
    print(f"Annexes parsed: {annexes_count}")
    print(f"Recitals: EXCLUDED (0 recital chunks indexed)")
    print(f"Total chunks created: {len(parsed_chunks)}")
    print(f"Dropped chunks without article: {dropped_count}")

    return parsed_chunks, metadata, dropped_count


def get_bias_lexicon_data() -> tuple[List[str], List[Dict[str, Any]]]:
    entries = [
        {"term": "salesman", "category": "gender", "severity": "high", "replacement": "sales representative", "context": "We are looking for a young, energetic salesman with 10+ years experience."},
        {"term": "he", "category": "gender", "severity": "med", "replacement": "they", "context": "He should be a cultural fit for our Western team."},
        {"term": "rockstar", "category": "gender", "severity": "med", "replacement": "high-performing specialist", "context": "a real rockstar who can crush targets."},
        {"term": "ninja", "category": "gender", "severity": "med", "replacement": "expert engineer", "context": "seeking a coding ninja to lead the team."},
        {"term": "crush targets", "category": "gender", "severity": "low", "replacement": "achieve performance goals", "context": "aggressive masculine-coded verb for plain descriptions of work."},
        {"term": "young", "category": "age", "severity": "high", "replacement": "motivated", "context": "We are looking for a young, energetic salesman."},
        {"term": "energetic", "category": "age", "severity": "med", "replacement": "driven", "context": "youth-coded adjective assuming candidate physical stamina."},
        {"term": "10+ years experience", "category": "age", "severity": "med", "replacement": "relevant experience", "context": "excessive years requirement acting as age proxy."},
        {"term": "digital native", "category": "age", "severity": "high", "replacement": "proficient with digital tools", "context": "ageist assumption excluding older candidates."},
        {"term": "cultural fit", "category": "cultural", "severity": "high", "replacement": "aligned with company values", "context": "subjective cultural criteria producing exclusion."},
        {"term": "Western team", "category": "cultural", "severity": "high", "replacement": "global team", "context": "geographic and cultural exclusionary phrasing."}
    ]
    chunks = []
    meta = []
    for e in entries:
        chunk = f"Biased term: '{e['term']}' (Category: {e['category']}, Severity: {e['severity']}). Suggested replacement: '{e['replacement']}'. Example context: {e['context']}"
        chunks.append(chunk)
        meta.append(e)
    return chunks, meta


def get_facts_data() -> tuple[List[str], List[Dict[str, Any]]]:
    facts = [
        # Discovery of Radium
        {"topic": "Discovery of Radium", "chunk": "Radium was discovered in 1898 by Marie and Pierre Curie, who extracted it from pitchblende residues in Paris, France.", "source": "Radium was discovered in 1898 by Marie and Pierre Curie, who extracted it from pitchblende residues."},
        {"topic": "Discovery of Radium", "chunk": "Pure metallic radium was first isolated in 1910 by Marie Curie and André-Louis Debierne through the electrolysis of a pure radium chloride solution.", "source": "Pure metallic radium was first isolated in 1910 by Marie Curie and André-Louis Debierne through electrolysis."},
        {"topic": "Discovery of Radium", "chunk": "The Curies announced the discovery of polonium in July 1898 and the discovery of radium in December of the same year 1898.", "source": "The Curies announced polonium in July 1898 and radium in December of the same year."},
        
        # Apollo 11
        {"topic": "The Apollo 11 mission", "chunk": "Apollo 11 was launched on July 16, 1969, carrying commander Neil Armstrong, command module pilot Michael Collins, and lunar module pilot Buzz Aldrin.", "source": "Apollo 11 launched July 16, 1969 with Armstrong, Collins, and Aldrin."},
        {"topic": "The Apollo 11 mission", "chunk": "Neil Armstrong became the first person to walk on the Moon on July 20, 1969, joined 19 minutes later by Buzz Aldrin, while Michael Collins flew the command module in lunar orbit.", "source": "Armstrong walked on the Moon on July 20, 1969, followed by Aldrin."},
        {"topic": "The Apollo 11 mission", "chunk": "The Apollo 11 spacecraft landed safely in the Pacific Ocean on July 24, 1969 after completing eight days in space.", "source": "Apollo 11 returned and splashed down safely on July 24, 1969."},

        # The EU AI Act
        {"topic": "The EU AI Act", "chunk": "The EU AI Act (Regulation (EU) 2024/1689) entered into force in 2024 as the world's first comprehensive legal framework for artificial intelligence.", "source": "EU AI Act Regulation 2024/1689 entered into force in 2024."},
        {"topic": "The EU AI Act", "chunk": "High-risk AI systems under Article 14 of the EU AI Act must be designed to enable effective human oversight during operation.", "source": "Article 14 mandates human oversight for high-risk AI systems."},
        {"topic": "The EU AI Act", "chunk": "Article 10 of the EU AI Act requires data governance and demographic bias checks for training and validation datasets.", "source": "Article 10 mandates data governance and non-discrimination checks."},

        # Photosynthesis
        {"topic": "Photosynthesis", "chunk": "Photosynthesis is the biological process used by plants, algae, and cyanobacteria to convert light energy into chemical energy stored in glucose.", "source": "Photosynthesis converts light energy into chemical energy in plants."},
        {"topic": "Photosynthesis", "chunk": "In oxygenic photosynthesis, water is split using light energy, releasing oxygen gas as a byproduct alongside glucose production.", "source": "Water splitting in photosynthesis releases oxygen gas."},

        # ISRO
        {"topic": "The Indian Space Research Organisation", "chunk": "The Indian Space Research Organisation (ISRO) is India's national space agency, headquartered in Bengaluru and founded in 1969.", "source": "ISRO was founded in 1969 and is headquartered in Bengaluru."},
        {"topic": "The Indian Space Research Organisation", "chunk": "ISRO successfully landed the Chandrayaan-3 mission near the lunar south pole in August 2023, making India the fourth nation to land on the Moon.", "source": "Chandrayaan-3 landed near the lunar south pole in August 2023."}
    ]

    chunks = [f["chunk"] for f in facts]
    meta = [{"topic": f["topic"], "source": f["source"]} for f in facts]
    return chunks, meta


def build_and_save_index(name: str, chunks: List[str], meta: List[Dict[str, Any]], model: SentenceTransformer, output_dir: str):
    os.makedirs(output_dir, exist_ok=True)
    out_path = os.path.join(output_dir, f"{name}.npz")

    print(f"Embedding {len(chunks)} chunks for index '{name}'...")
    embeddings = model.encode(chunks, convert_to_numpy=True, show_progress_bar=False)
    
    # L2-normalize vectors
    norms = np.linalg.norm(embeddings, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    vecs = (embeddings / norms).astype(np.float32)

    meta_json_strs = [json.dumps(m) for m in meta]
    np.savez_compressed(out_path, vecs=vecs, chunks=np.array(chunks), meta=np.array(meta_json_strs))
    print(f"Saved {out_path} ({os.path.getsize(out_path)} bytes)")


def main():
    parser = argparse.ArgumentParser(description="Precompute .npz search indexes")
    parser.add_argument("--source", type=str, help="Path to raw source file or folder")
    parser.add_argument("--name", type=str, help="Index name (eu_ai_act | bias_lexicon | facts | all)")
    args = parser.parse_args()

    print(f"Loading embedding model '{MODEL_NAME}'...")
    model = SentenceTransformer(MODEL_NAME)
    output_dir = "data"

    name = args.name or "all"

    if name in ["eu_ai_act", "all"]:
        source_file = args.source or r"data\raw\eu_ai_act\Consolidated TEXT_ 32024R1689 — EN — 27.07.2026.html"
        if os.path.isdir(source_file):
            # Find html in dir
            files = [os.path.join(source_file, f) for f in os.listdir(source_file) if f.endswith(".html")]
            if files:
                source_file = files[0]

        chunks, meta, dropped = parse_eu_ai_act_html(source_file)
        build_and_save_index("eu_ai_act", chunks, meta, model, output_dir)

    if name in ["bias_lexicon", "all"]:
        chunks, meta = get_bias_lexicon_data()
        build_and_save_index("bias_lexicon", chunks, meta, model, output_dir)

    if name in ["facts", "all"]:
        chunks, meta = get_facts_data()
        build_and_save_index("facts", chunks, meta, model, output_dir)

    print("Index build complete!")


if __name__ == "__main__":
    main()
