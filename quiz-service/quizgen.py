"""Rule-based quiz generator.

No LLM, no external API: split the extracted text into sentences, keep the
ones that contain a number or a capitalised term, blank that term out, and
offer it among distractors pulled from the other candidate sentences.
"""
import random
import re

SENTENCE_RE = re.compile(r"(?<=[.!?])\s+")
NUMBER_RE = re.compile(r"\b\d[\d,.]*\b")
CAP_WORD_RE = re.compile(r"^[A-Z][a-zA-Z]{2,}$")


def split_sentences(text: str) -> list[str]:
    return [s.strip() for s in SENTENCE_RE.split(text or "") if len(s.strip()) > 12]


def find_blank_candidate(sentence: str):
    numbers = NUMBER_RE.findall(sentence)
    if numbers:
        return numbers[0]

    words = sentence.split()
    for i, raw in enumerate(words):
        cleaned = raw.strip(".,;:!?\"'()")
        if i > 0 and CAP_WORD_RE.match(cleaned):
            return cleaned
    return None


def generate_questions(text: str, max_questions: int = 5) -> list[dict]:
    candidates = []
    for sentence in split_sentences(text):
        term = find_blank_candidate(sentence)
        if term:
            candidates.append((sentence, term))

    if not candidates:
        return []

    all_terms = [term for _, term in candidates]
    random.shuffle(candidates)

    questions = []
    for sentence, term in candidates[:max_questions]:
        blanked = sentence.replace(term, "_____", 1)

        pool = [t for t in set(all_terms) if t != term]
        random.shuffle(pool)
        distractors = pool[:3]

        options = distractors + [term]
        random.shuffle(options)

        questions.append({
            "question": blanked,
            "options": options,
            "answer_index": options.index(term),
        })

    return questions
