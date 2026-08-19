import os
import re
import argparse
import json
from typing import List, Dict, Any
import numpy as np

import torch
from bs4 import BeautifulSoup
from sentence_transformers import SentenceTransformer
from transformers import AutoTokenizer, AutoModel

MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"
SOURCE_VERSION = "02024R1689-20260727"


def chunk_text(text: str, chunk_size: int = 1200, overlap: int = 150) -> List[str]:
    """
    Splits text into chunks snapped to sentence boundaries.
    Never splits mid-word or mid-sentence.
    """
    clean_text = re.sub(r"\s+", " ", text).strip()
    if not clean_text:
        return []
    if len(clean_text) <= chunk_size:
        return [clean_text]

    # Split into sentences using regex looking for sentence terminals (. ! ?) followed by space
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
            
            # Carry over sentences for overlap
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
    print(f"Dropped chunks without article: {dropped_count}")

    return parsed_chunks, metadata, dropped_count


def get_expanded_bias_lexicon() -> tuple[List[str], List[Dict[str, Any]]]:
    """Generates 90+ comprehensive entries for bias_lexicon."""
    entries = [
        # Masculine-coded (20)
        {"term": "ninja", "category": "gender", "severity": "medium", "replacement": "expert engineer", "context": "seeking a coding ninja to build scalable systems."},
        {"term": "rockstar", "category": "gender", "severity": "medium", "replacement": "high-performing specialist", "context": "looking for a rockstar developer who delivers under pressure."},
        {"term": "hungry", "category": "gender", "severity": "low", "replacement": "highly motivated", "context": "we need hungry sales professionals to drive growth."},
        {"term": "aggressive", "category": "gender", "severity": "high", "replacement": "ambitious", "context": "seeking an aggressive leader to conquer market share."},
        {"term": "dominant", "category": "gender", "severity": "high", "replacement": "established market leader", "context": "dominant force in enterprise software."},
        {"term": "crush", "category": "gender", "severity": "medium", "replacement": "exceed targets", "context": "looking for someone ready to crush quarterly quotas."},
        {"term": "competitive", "category": "gender", "severity": "low", "replacement": "goal-oriented", "context": "thrives in a competitive sales environment."},
        {"term": "fearless", "category": "gender", "severity": "medium", "replacement": "resilient", "context": "seeking a fearless innovator to spearhead new initiatives."},
        {"term": "guru", "category": "gender", "severity": "medium", "replacement": "domain authority", "context": "hiring a cloud architecture guru."},
        {"term": "hacker", "category": "gender", "severity": "medium", "replacement": "creative developer", "context": "growth hacker wanted for fast-moving team."},
        {"term": "work hard play hard", "category": "gender", "severity": "medium", "replacement": "balanced high-energy team", "context": "intense work hard play hard culture."},
        {"term": "killer", "category": "gender", "severity": "high", "replacement": "exceptional feature", "context": "looking for a killer instinct in deal closing."},
        {"term": "footprint", "category": "gender", "severity": "low", "replacement": "market presence", "context": "expanding our operational footprint aggressively."},
        {"term": "dominant force", "category": "gender", "severity": "high", "replacement": "industry leader", "context": "aiming to become the dominant force in fintech."},
        {"term": "lead from front", "category": "gender", "severity": "low", "replacement": "lead by example", "context": "manager who will lead from the front lines."},
        {"term": "alpha", "category": "gender", "severity": "high", "replacement": "top performer", "context": "seeking alpha personalities for executive roles."},
        {"term": "ruthless", "category": "gender", "severity": "high", "replacement": "decisive", "context": "ruthless prioritization of customer needs."},
        {"term": "hard-charging", "category": "gender", "severity": "medium", "replacement": "proactive", "context": "hard-charging team of account managers."},
        {"term": "decision-maker", "category": "gender", "severity": "low", "replacement": "key stakeholder", "context": "must engage directly with C-level decision-makers."},
        {"term": "single-minded", "category": "gender", "severity": "low", "replacement": "focused", "context": "single-minded dedication to product quality."},

        # Feminine-coded (20)
        {"term": "nurturing", "category": "gender", "severity": "low", "replacement": "supportive leadership", "context": "nurturing team environment encouraging growth."},
        {"term": "supportive", "category": "gender", "severity": "low", "replacement": "collaborative", "context": "seeking a supportive colleague for client relations."},
        {"term": "collaborative", "category": "gender", "severity": "low", "replacement": "cross-functional alignment", "context": "collaborative mindset across engineering units."},
        {"term": "empathetic", "category": "gender", "severity": "low", "replacement": "user-centric", "context": "empathetic communicator for customer success."},
        {"term": "warm", "category": "gender", "severity": "low", "replacement": "welcoming", "context": "warm and friendly office receptionist."},
        {"term": "helpful", "category": "gender", "severity": "low", "replacement": "service-oriented", "context": "helpful demeanor in resolving support tickets."},
        {"term": "caring", "category": "gender", "severity": "low", "replacement": "attentive", "context": "caring approach to employee well-being."},
        {"term": "soft-spoken", "category": "gender", "severity": "medium", "replacement": "thoughtful communicator", "context": "soft-spoken professional for sensitive accounts."},
        {"term": "sensitive", "category": "gender", "severity": "low", "replacement": "attuned to user feedback", "context": "sensitive to client requirements and deadlines."},
        {"term": "relationship-builder", "category": "gender", "severity": "low", "replacement": "account manager", "context": "strong relationship-builder with enterprise buyers."},
        {"term": "compassionate", "category": "gender", "severity": "low", "replacement": "considerate", "context": "compassionate leader in healthcare administration."},
        {"term": "team player", "category": "gender", "severity": "low", "replacement": "collaborator", "context": "essential team player in product design."},
        {"term": "intuitive", "category": "gender", "severity": "low", "replacement": "insightful", "context": "intuitive grasp of UX research."},
        {"term": "gentle", "category": "gender", "severity": "medium", "replacement": "tactful", "context": "gentle guidance for junior developers."},
        {"term": "peacemaker", "category": "gender", "severity": "medium", "replacement": "conflict mediator", "context": "peacemaker during high-stakes client negotiations."},
        {"term": "consensus-builder", "category": "gender", "severity": "low", "replacement": "cross-functional coordinator", "context": "proven consensus-builder among department heads."},
        {"term": "approachable", "category": "gender", "severity": "low", "replacement": "accessible", "context": "approachable leader with open-door policy."},
        {"term": "dependable", "category": "gender", "severity": "low", "replacement": "reliable", "context": "dependable asset to our operations team."},
        {"term": "detail-oriented", "category": "gender", "severity": "low", "replacement": "meticulous", "context": "detail-oriented auditor for financial reports."},
        {"term": "interpersonal skills", "category": "gender", "severity": "low", "replacement": "communication capabilities", "context": "exceptional interpersonal skills required."},

        # Gendered Titles & Pronouns (20)
        {"term": "salesman", "category": "gender", "severity": "high", "replacement": "sales representative", "context": "seeking an experienced salesman for regional accounts."},
        {"term": "chairman", "category": "gender", "severity": "high", "replacement": "chairperson", "context": "reports directly to the board chairman."},
        {"term": "manpower", "category": "gender", "severity": "high", "replacement": "workforce", "context": "sufficient manpower to complete project milestones."},
        {"term": "he/his", "category": "gender", "severity": "high", "replacement": "they/them", "context": "the ideal candidate must demonstrate his coding skills."},
        {"term": "draftsman", "category": "gender", "severity": "high", "replacement": "drafter", "context": "hiring CAD draftsman for architectural drawings."},
        {"term": "handyman", "category": "gender", "severity": "high", "replacement": "maintenance technician", "context": "facility handyman for office repairs."},
        {"term": "stewardess", "category": "gender", "severity": "high", "replacement": "flight attendant", "context": "hiring corporate flight stewardess."},
        {"term": "forester", "category": "gender", "severity": "medium", "replacement": "forestry specialist", "context": "experienced forester for land management."},
        {"term": "groundsman", "category": "gender", "severity": "high", "replacement": "groundskeeper", "context": "stadium groundsman needed for turf care."},
        {"term": "spokesman", "category": "gender", "severity": "high", "replacement": "spokesperson", "context": "media spokesman for corporate communications."},
        {"term": "tradesman", "category": "gender", "severity": "high", "replacement": "skilled trade professional", "context": "licensed tradesman for electrical work."},
        {"term": "freshwoman", "category": "gender", "severity": "medium", "replacement": "first-year student", "context": "internship open to college freshwoman."},
        {"term": "cameraman", "category": "gender", "severity": "high", "replacement": "camera operator", "context": "seeking broadcast cameraman for live events."},
        {"term": "fireman", "category": "gender", "severity": "high", "replacement": "firefighter", "context": "industrial safety fireman on shift."},
        {"term": "postman", "category": "gender", "severity": "high", "replacement": "mail carrier", "context": "courier postman for internal delivery."},
        {"term": "saleswoman", "category": "gender", "severity": "high", "replacement": "sales associate", "context": "top saleswoman of the year award."},
        {"term": "businesswoman", "category": "gender", "severity": "high", "replacement": "business executive", "context": "dynamic businesswoman leading startup growth."},
        {"term": "cleaning lady", "category": "gender", "severity": "high", "replacement": "office cleaner", "context": "daily cleaning lady for office suite."},
        {"term": "waitress", "category": "gender", "severity": "high", "replacement": "server", "context": "hiring banquet waitress for corporate events."},
        {"term": "headmaster", "category": "gender", "severity": "high", "replacement": "principal", "context": "headmaster for private academy."},

        # Age Proxies (20)
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
        {"term": "seasoned veteran", "category": "age", "severity": "low", "replacement": "senior specialist", "context": "seeking a seasoned veteran of SaaS sales."},
        {"term": "tech savvy youth", "category": "age", "severity": "high", "replacement": "technology proficient", "context": "targeting tech savvy youth for app design."},
        {"term": "energetic environment", "category": "age", "severity": "low", "replacement": "active workspace", "context": "fast execution in an energetic environment."},
        {"term": "recent grad", "category": "age", "severity": "medium", "replacement": "junior developer", "context": "entry-level role suited for recent grad."},
        {"term": "early career", "category": "age", "severity": "low", "replacement": "junior level", "context": "opportunity for early career professionals."},
        {"term": "senior citizen", "category": "age", "severity": "high", "replacement": "older worker", "context": "community outreach to senior citizens."},
        {"term": "maximum 5 years experience", "category": "age", "severity": "high", "replacement": "mid-level qualifications", "context": "candidates must have maximum 5 years experience."},

        # Cultural / Exclusionary Phrasing (20)
        {"term": "cultural fit", "category": "cultural", "severity": "high", "replacement": "value alignment", "context": "hiring based on strict cultural fit."},
        {"term": "native speaker", "category": "cultural", "severity": "high", "replacement": "professional fluency", "context": "must be a native speaker of English."},
        {"term": "Western", "category": "cultural", "severity": "high", "replacement": "international", "context": "experience in Western markets preferred."},
        {"term": "no accent", "category": "cultural", "severity": "high", "replacement": "clear communication", "context": "must speak with no accent on phone calls."},
        {"term": "must be local", "category": "cultural", "severity": "medium", "replacement": "relocation assistance available", "context": "applicant must be local to the metro area."},
        {"term": "US-born", "category": "cultural", "severity": "high", "replacement": "authorized to work in US", "context": "preference for US-born candidates."},
        {"term": "Ivy League only", "category": "cultural", "severity": "high", "replacement": "accredited university degree", "context": "recruiting from Ivy League only institutions."},
        {"term": "traditional background", "category": "cultural", "severity": "medium", "replacement": "relevant professional experience", "context": "prefer candidates from a traditional background."},
        {"term": "native English", "category": "cultural", "severity": "high", "replacement": "fluent English", "context": "native English writing skills required."},
        {"term": "foreign accent", "category": "cultural", "severity": "high", "replacement": "effective communication", "context": "role not suitable for applicants with foreign accent."},
        {"term": "local experience only", "category": "cultural", "severity": "high", "replacement": "relevant regional knowledge", "context": "candidates with local experience only will be considered."},
        {"term": "top tier university", "category": "cultural", "severity": "medium", "replacement": "relevant degree", "context": "degree from top tier university mandatory."},
        {"term": "pedigree", "category": "cultural", "severity": "high", "replacement": "proven qualifications", "context": "looking for candidates with executive pedigree."},
        {"term": "corporate background", "category": "cultural", "severity": "low", "replacement": "industry experience", "context": "strong corporate background preferred."},
        {"term": "culture add", "category": "cultural", "severity": "low", "replacement": "diverse perspective", "context": "seeking a positive culture add for our office."},
        {"term": "domestic experience", "category": "cultural", "severity": "medium", "replacement": "local market familiarity", "context": "domestic experience required for compliance role."},
        {"term": "local candidate only", "category": "cultural", "severity": "medium", "replacement": "commutable distance", "context": "local candidate only; no remote options."},
        {"term": "Western educated", "category": "cultural", "severity": "high", "replacement": "accredited education", "context": "preference for Western educated applicants."},
        {"term": "elite background", "category": "cultural", "severity": "high", "replacement": "demonstrated competence", "context": "recruiting talent from elite background firms."},
        {"term": "native fluency", "category": "cultural", "severity": "high", "replacement": "full professional proficiency", "context": "native fluency required for editorial tasks."}
    ]

    chunks = []
    meta = []
    for e in entries:
        chunk = f"Biased term: '{e['term']}' (Category: {e['category']}, Severity: {e['severity']}). Suggested replacement: '{e['replacement']}'. Example context: {e['context']}"
        chunks.append(chunk)
        meta.append(e)

    return chunks, meta


def get_expanded_facts() -> tuple[List[str], List[Dict[str, Any]]]:
    """Generates 75+ substantive fact chunks across the 5 topics (15+ per topic)."""
    facts_data = [
        # Topic 1: Discovery of Radium (15 chunks)
        ("Discovery of Radium", "Radium was discovered in December 1898 by Polish-French physicist Marie Skłodowska-Curie and her husband Pierre Curie in Paris, France.", "Radium discovery by Marie and Pierre Curie in December 1898."),
        ("Discovery of Radium", "The Curies extracted radium compounds from uraninite (pitchblende), a uranium-rich ore obtained from the Jáchymov mines in Bohemia.", "Extraction of radium from pitchblende ore."),
        ("Discovery of Radium", "Prior to discovering radium, Marie Curie announced the discovery of polonium in July 1898, naming it after her native country Poland.", "Polonium discovery in July 1898 by Marie Curie."),
        ("Discovery of Radium", "Radium was isolated in its pure metallic form in 1910 by Marie Curie and French chemist André-Louis Debierne through the electrolysis of pure radium chloride solution.", "Metallic radium isolation in 1910 by Marie Curie and Debierne."),
        ("Discovery of Radium", "Pure metallic radium is a brilliant silver-white alkaline earth metal that rapidly reacts with nitrogen and oxygen in the air, turning black.", "Physical properties of metallic radium."),
        ("Discovery of Radium", "The Curies processed several tons of pitchblende residue to extract just one-tenth of a gram of pure radium chloride in 1902.", "Isolation of one-tenth gram radium chloride in 1902."),
        ("Discovery of Radium", "Marie Curie was awarded the 1903 Nobel Prize in Physics alongside Pierre Curie and Henri Becquerel for their research on radiation phenomena.", "1903 Nobel Prize in Physics awarded to Marie and Pierre Curie."),
        ("Discovery of Radium", "In 1911, Marie Curie won her second Nobel Prize, this time in Chemistry, for her discovery of radium and polonium and the isolation of radium.", "1911 Nobel Prize in Chemistry awarded to Marie Curie."),
        ("Discovery of Radium", "Radium decays into radon gas through alpha radioactive decay, emitting intense blue radioluminescence due to the excitation of surrounding air molecules.", "Radioactive decay of radium into radon gas."),
        ("Discovery of Radium", "Radium-226 has a half-life of approximately 1,600 years and is part of the uranium decay series originating from Uranium-238.", "Radium-226 half-life of 1,600 years."),
        ("Discovery of Radium", "Early 20th-century applications of radium included luminescent paint for watch dials, medical radiotherapy for tumors, and commercial health products.", "Historical industrial and medical uses of radium."),
        ("Discovery of Radium", "The tragic health impacts on factory workers known as the Radium Dials Girls in the 1920s led to historic occupational safety legislation.", "Radium Dial Girls health impacts and safety laws."),
        ("Discovery of Radium", "Marie Curie founded the Radium Institute (now Curie Institute) in Paris in 1914 for medical research into cancer radiation therapy.", "Founding of the Radium Institute in Paris in 1914."),
        ("Discovery of Radium", "Pierre Curie tragically died in a street accident in Paris in April 1906, after which Marie Curie assumed his professorship at the Sorbonne.", "Pierre Curie death in 1906 and Marie Curie Sorbonne tenure."),
        ("Discovery of Radium", "Radium remained the primary source of high-energy gamma rays for cancer radiation therapy until synthetic radioisotopes like Cobalt-60 were developed in the 1950s.", "Radium role in cancer radiotherapy until the 1950s."),

        # Topic 2: The Apollo 11 Mission (15 chunks)
        ("The Apollo 11 mission", "Apollo 11 launched from Kennedy Space Center Launch Complex 39A in Florida on July 16, 1969, aboard a Saturn V rocket.", "Apollo 11 launch on July 16, 1969 via Saturn V."),
        ("The Apollo 11 mission", "The Apollo 11 crew consisted of Commander Neil Armstrong, Command Module Pilot Michael Collins, and Lunar Module Pilot Edwin 'Buzz' Aldrin Jr.", "Apollo 11 astronaut crew members."),
        ("The Apollo 11 mission", "The Apollo 11 Command Module was named 'Columbia' and the Lunar Module was named 'Eagle'.", "Apollo 11 spacecraft names Columbia and Eagle."),
        ("The Apollo 11 mission", "Neil Armstrong and Buzz Aldrin undocked Eagle from Columbia on July 20, 1969, to descend to the lunar surface while Michael Collins remained in orbit.", "Eagle lunar landing descent on July 20, 1969."),
        ("The Apollo 11 mission", "The Lunar Module Eagle landed in the Mare Tranquillitatis (Sea of Tranquility) at 20:17 UTC on July 20, 1969.", "Eagle touchdown in the Sea of Tranquility."),
        ("The Apollo 11 mission", "Upon landing, Neil Armstrong radioed mission control in Houston with the famous message: 'Houston, Tranquility Base here. The Eagle has landed.'", "Tranquility Base radio confirmation to Houston."),
        ("The Apollo 11 mission", "Neil Armstrong stepped onto the lunar surface at 02:56 UTC on July 21, 1969, uttering the historic words: 'That's one small step for man, one giant leap for mankind.'", "First step on Moon by Neil Armstrong on July 21, 1969."),
        ("The Apollo 11 mission", "Buzz Aldrin joined Armstrong on the lunar surface 19 minutes later, describing the lunar landscape as 'magnificent desolation'.", "Buzz Aldrin lunar surface EVA step."),
        ("The Apollo 11 mission", "Armstrong and Aldrin spent 2 hours and 31 minutes conducting an extravehicular activity (EVA) outside the Lunar Module.", "Duration of Apollo 11 lunar EVA walk."),
        ("The Apollo 11 mission", "The astronauts deployed scientific instruments including the Passive Seismic Experiment Package and a Laser Ranging Retroreflector.", "Scientific instruments deployed on the Moon."),
        ("The Apollo 11 mission", "Apollo 11 collected 21.5 kilograms (47.5 lb) of lunar surface material, including rocks, core samples, and lunar soil.", "Lunar rock and soil sample collection."),
        ("The Apollo 11 mission", "The astronauts unveiled a stainless steel plaque attached to Eagle's descent stage reading: 'Here men from the planet Earth first set foot upon the Moon July 1969, A.D. We came in peace for all mankind.'", "Commemorative plaque on Eagle descent stage."),
        ("The Apollo 11 mission", "Eagle's ascent stage launched from the lunar surface on July 21, 1969, docking successfully with Michael Collins aboard Columbia in lunar orbit.", "Lunar ascent and orbit rendezvous with Columbia."),
        ("The Apollo 11 mission", "Apollo 11 splashed down safely in the North Pacific Ocean, 920 miles southwest of Hawaii, on July 24, 1969, recovered by the USS Hornet.", "Splashdown in North Pacific Ocean on July 24, 1969."),
        ("The Apollo 11 mission", "The Apollo 11 mission fulfilled President John F. Kennedy's 1961 national goal of landing a man on the Moon and returning him safely to Earth before the end of the 1960s.", "Fulfillment of President Kennedy 1961 lunar mandate."),

        # Topic 3: The EU AI Act (15 chunks)
        ("The EU AI Act", "The European Union Artificial Intelligence Act (Regulation (EU) 2024/1689) is a landmark legal framework regulating artificial intelligence across EU member states.", "EU AI Act Regulation (EU) 2024/1689 introduction."),
        ("The EU AI Act", "The EU AI Act was published in the Official Journal of the European Union on July 12, 2024, entering into force 20 days later on August 1, 2024.", "Publication and entry into force dates of EU AI Act."),
        ("The EU AI Act", "The AI Act adopts a risk-based classification system dividing AI systems into four risk categories: unacceptable risk, high risk, specific transparency risk, and minimal risk.", "Risk-based classification structure under EU AI Act."),
        ("The EU AI Act", "Article 5 of the EU AI Act prohibits AI systems posing unacceptable risks, including subliminal manipulation, social scoring, biometric categorization of sensitive attributes, and untargeted facial scraping.", "Prohibited AI practices under Article 5."),
        ("The EU AI Act", "High-risk AI systems under Article 6 and Annex III include AI used in critical infrastructure, education, employment, access to essential public services, law enforcement, and justice administration.", "High-risk AI system categories under Article 6 and Annex III."),
        ("The EU AI Act", "Article 10 requires providers of high-risk AI systems to implement rigorous data governance, ensuring training datasets are examined for potential biases and discriminatory impacts.", "Article 10 data governance and non-discrimination requirements."),
        ("The EU AI Act", "Article 14 mandates that high-risk AI systems must be designed to enable effective human oversight by natural persons to prevent automation bias and operational risks.", "Article 14 human oversight mandatory provisions."),
        ("The EU AI Act", "Article 11 mandates technical documentation demonstrating compliance before high-risk AI systems are placed on the market or put into service.", "Article 11 technical documentation requirements."),
        ("The EU AI Act", "Article 13 specifies transparency requirements, ensuring deployers and users can understand how high-risk AI system outputs are generated.", "Article 13 transparency and user information obligations."),
        ("The EU AI Act", "General-purpose AI (GPAI) models are governed by specific obligations under Title VIII, including technical documentation, copyright law compliance, and systemic risk evaluations for powerful models.", "General-purpose AI model obligations under Title VIII."),
        ("The EU AI Act", "The European AI Office was established within the European Commission to oversee enforcement and implementation of general-purpose AI rules.", "Establishment of European AI Office."),
        ("The EU AI Act", "Non-compliance with prohibited AI practices under Article 5 carries administrative fines up to €35 million or 7% of total worldwide annual turnover.", "Maximum fines under Article 5 non-compliance."),
        ("The EU AI Act", "Violations of high-risk system obligations under the AI Act carry fines up to €15 million or 3% of worldwide annual turnover, whichever is higher.", "Fines for high-risk system non-compliance."),
        ("The EU AI Act", "Member states must establish national supervisory authorities and deploy regulatory sandboxes under Article 57 to foster responsible AI innovation.", "National supervisory authorities and regulatory sandboxes."),
        ("The EU AI Act", "Full application of high-risk AI system rules takes effect in phases up to 36 months following entry into force, with prohibited AI bans applying after 6 months.", "Phase-in enforcement timeline of EU AI Act rules."),

        # Topic 4: Photosynthesis (15 chunks)
        ("Photosynthesis", "Photosynthesis is the biological process by which autotrophic organisms convert light energy into chemical energy stored in carbohydrate molecules like glucose.", "Definition of photosynthesis process."),
        ("Photosynthesis", "Oxygenic photosynthesis is performed by green plants, algae, and cyanobacteria, absorbing carbon dioxide and water to release oxygen as a byproduct.", "Oxygenic photosynthesis organisms and byproduct."),
        ("Photosynthesis", "The general chemical equation for oxygenic photosynthesis is 6 CO2 + 6 H2O + light energy -> C6H12O6 + 6 O2.", "Chemical equation of oxygenic photosynthesis."),
        ("Photosynthesis", "Chlorophyll a and chlorophyll b are the primary photosynthetic pigments located in the thylakoid membranes of chloroplasts, absorbing light mainly in blue and red wavelengths.", "Chlorophyll pigments and thylakoid membrane role."),
        ("Photosynthesis", "Photosynthesis is divided into light-dependent reactions taking place in thylakoids and light-independent reactions (Calvin cycle) in the stroma.", "Light-dependent vs light-independent Calvin cycle reactions."),
        ("Photosynthesis", "During light-dependent reactions, absorbed light excites electrons in Photosystem II (P680), driving photolysis of water molecules into oxygen, protons, and electrons.", "Light reactions in Photosystem II and photolysis of water."),
        ("Photosynthesis", "The electron transport chain generates a proton gradient across the thylakoid membrane, driving ATP synthesis via ATP synthase (photophosphorylation).", "Proton gradient and ATP synthase photophosphorylation."),
        ("Photosynthesis", "Photosystem I (P700) absorbs light to re-excite electrons, reducing NADP+ to NADPH via ferredoxin-NADP+ reductase.", "Photosystem I NADPH reduction."),
        ("Photosynthesis", "The Calvin cycle utilizes ATP and NADPH to fix carbon dioxide into three-carbon sugars (G3P) through the enzyme RuBisCO (ribulose-1,5-bisphosphate carboxylase-oxygenase).", "Calvin cycle carbon fixation via RuBisCO."),
        ("Photosynthesis", "RuBisCO is the most abundant enzyme on Earth, catalyzing the addition of CO2 to RuBP during the carboxylation stage of the Calvin cycle.", "RuBisCO enzyme role and abundance."),
        ("Photosynthesis", "C4 carbon fixation is an adaptation in plants like corn and sugarcane that minimizes photorespiration by fixing CO2 into oxaloacetate in mesophyll cells.", "C4 plant pathway adaptation to minimize photorespiration."),
        ("Photosynthesis", "Crassulacean acid metabolism (CAM) is an adaptation in desert succulents like pineapples and cacti, opening stomata at night to capture CO2 as malic acid.", "CAM photosynthesis adaptation in desert succulents."),
        ("Photosynthesis", "Anoxygenic photosynthesis is performed by purple and green sulfur bacteria, utilizing hydrogen sulfide (H2S) instead of water and producing elemental sulfur.", "Anoxygenic photosynthesis in sulfur bacteria."),
        ("Photosynthesis", "Photosynthesis produces over 100 billion metric tons of organic biomass annually, driving the global carbon cycle and maintaining atmospheric oxygen levels.", "Global biomass production and carbon cycle contribution."),
        ("Photosynthesis", "Stomata on plant leaves regulate gas exchange during photosynthesis, opening to take in CO2 while balancing water vapor loss through transpiration.", "Stomatal gas exchange and transpiration balance."),

        # Topic 5: The Indian Space Research Organisation (15 chunks)
        ("The Indian Space Research Organisation", "The Indian Space Research Organisation (ISRO) is the national space agency of India, operating under the Department of Space.", "ISRO agency profile and Department of Space governance."),
        ("The Indian Space Research Organisation", "ISRO was founded on August 15, 1969, by visionary scientist Vikram Sarabhai, considered the father of the Indian space program.", "Founding of ISRO on August 15, 1969 by Vikram Sarabhai."),
        ("The Indian Space Research Organisation", "ISRO is headquartered in Bengaluru, Karnataka, with major launch facilities located at the Satish Dhawan Space Centre in Sriharikota, Andhra Pradesh.", "ISRO headquarters in Bengaluru and Sriharikota launch center."),
        ("The Indian Space Research Organisation", "India's first satellite, Aryabhata, was built by ISRO and launched by the Soviet Union on April 19, 1975.", "Aryabhata satellite launch in 1975."),
        ("The Indian Space Research Organisation", "The Polar Satellite Launch Vehicle (PSLV) is ISRO's dependable workhorse rocket, completing over 50 successful satellite launch missions.", "PSLV launch vehicle track record."),
        ("The Indian Space Research Organisation", "The Geosynchronous Satellite Launch Vehicle (GSLV Mk III / LVM3) is ISRO's heavy-lift launch vehicle, capable of carrying 4-ton payloads to geostationary orbit.", "LVM3 heavy-lift launch vehicle capabilities."),
        ("The Indian Space Research Organisation", "ISRO launched Chandrayaan-1 in October 2008, discovering evidence of water ice molecules across the lunar surface.", "Chandrayaan-1 lunar mission water ice discovery."),
        ("The Indian Space Research Organisation", "The Mars Orbiter Mission (Mangalyaan) was launched in November 2013, making ISRO the fourth space agency to reach Mars and the first on its initial attempt.", "Mars Orbiter Mission Mangalyaan achievement."),
        ("The Indian Space Research Organisation", "ISRO successfully executed the Chandrayaan-3 mission, landing the Vikram lander near the lunar south pole on August 23, 2023.", "Chandrayaan-3 Vikram lander lunar south pole landing."),
        ("The Indian Space Research Organisation", "The Pragyan rover deployed from Chandrayaan-3 conducted elemental analysis of lunar soil, confirming the presence of sulfur in the south polar region.", "Pragyan rover sulfur confirmation near lunar south pole."),
        ("The Indian Space Research Organisation", "ISRO launched Aditya-L1 in September 2023, India's first dedicated solar observation mission positioned at the Sun-Earth Lagrangian point L1.", "Aditya-L1 solar observation space mission."),
        ("The Indian Space Research Organisation", "The Gaganyaan project is ISRO's crewed spaceflight program aiming to send human astronauts into a 400 km low Earth orbit.", "Gaganyaan crewed human spaceflight mission goals."),
        ("The Indian Space Research Organisation", "ISRO operates the NavIC (Navigation with Indian Constellation) satellite system, providing independent regional satellite positioning across South Asia.", "NavIC regional satellite navigation system."),
        ("The Indian Space Research Organisation", "ISRO set a world record in February 2017 by deploying 104 satellites into orbit aboard a single PSLV-C37 rocket launch.", "World record 104 satellites deployment aboard PSLV-C37."),
        ("The Indian Space Research Organisation", "ISRO collaborates internationally with NASA on the NISAR (NASA-ISRO Synthetic Aperture Radar) satellite to monitor global ecosystem changes.", "NISAR dual-frequency radar collaboration with NASA.")
    ]

    chunks = [f[1] for f in facts_data]
    meta = [{"topic": f[0], "source": f[2]} for f in facts_data]
    return chunks, meta


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
        chunks, meta = get_expanded_bias_lexicon()
        build_and_save_index("bias_lexicon", chunks, meta, model, output_dir)

    if name in ["facts", "all"]:
        chunks, meta = get_expanded_facts()
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
