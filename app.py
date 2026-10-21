import json
import re
from datetime import datetime
from pathlib import Path

import nltk
from flask import Flask, jsonify, render_template, request
from nltk.corpus import wordnet as wn

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
REPORT_DIR = BASE_DIR / "reports"
DATA_FILE = DATA_DIR / "sample_sentences.json"
REPORT_DIR.mkdir(exist_ok=True)

app = Flask(__name__)


def load_samples():
    with DATA_FILE.open(encoding="utf-8") as file:
        return json.load(file)


def tokenize(text):
    return set(re.findall(r"[a-z]+", text.lower()))


def synset_payload(synset, context_tokens=None):
    context_tokens = context_tokens or set()

    definition_tokens = tokenize(synset.definition())
    examples = synset.examples()
    example_tokens = set()
    for example in examples:
        example_tokens.update(tokenize(example))

    signature = definition_tokens | example_tokens
    overlap = len(context_tokens & signature)

    return {
        "id": synset.name(),
        "name": synset.name().split(".")[0].replace("_", " "),
        "pos": synset.pos(),
        "pos_label": {
            "n": "Noun",
            "v": "Verb",
            "a": "Adjective",
            "s": "Adjective",
            "r": "Adverb",
        }.get(synset.pos(), synset.pos()),
        "definition": synset.definition(),
        "examples": examples[:3],
        "lemmas": [lemma.name().replace("_", " ") for lemma in synset.lemmas()[:8]],
        "hypernyms": [
            item.definition() for item in synset.hypernyms()[:3]
        ],
        "hyponyms": [
            item.definition() for item in synset.hyponyms()[:3]
        ],
        "overlap": overlap,
        "score": 0,
    }


def resolve_target(sentence, target):
    words = re.findall(r"[a-z]+(?:'[a-z]+)?", sentence.lower())
    target = target.strip().lower()

    if not target or not re.fullmatch(r"[a-z]+(?:['-][a-z]+)*", target):
        raise ValueError("Enter a valid target word, such as 'bank' or 'bat'.")

    if target not in words:
        raise ValueError(
            f"The target word '{target}' was not found in the sentence. "
            "Enter a word that appears in the sentence."
        )

    return target


def analyze_sentence(sentence, target):
    if not isinstance(sentence, str) or not sentence.strip():
        raise ValueError("Please enter a sentence to analyze.")

    if len(sentence) > 2000:
        raise ValueError("Please keep the sentence under 2,000 characters.")

    target = resolve_target(sentence, target)
    target_tokens = tokenize(target)
    context_tokens = tokenize(sentence) - target_tokens

    candidates = wn.synsets(target)
    if not candidates:
        return {
            "sentence": sentence,
            "target": target,
            "found": False,
            "message": (
                f"No WordNet senses were found for '{target}'. "
                "Try a common English word in its base form."
            ),
            "candidates": [],
            "method": "Lesk-style definition and example overlap",
        }

    results = []
    for synset in candidates:
        item = synset_payload(synset, context_tokens)

        # Extended Lesk-style scoring: compare context against definitions,
        # examples and lemma names, not just the target word itself.
        lemma_tokens = set()
        for lemma in synset.lemmas():
            lemma_tokens.update(tokenize(lemma.name().replace("_", " ")))

        signature = (
            tokenize(synset.definition())
            | lemma_tokens
        )
        for example in synset.examples():
            signature |= tokenize(example)

        item["score"] = len(context_tokens & signature)

        # WordNet's sense frequency is a weak prior. It is used only
        # as a tie-breaker after contextual overlap.
        item["frequency"] = sum(
            lemma.count() for lemma in synset.lemmas()
        )
        results.append(item)

    results.sort(
        key=lambda item: (item["score"], item["frequency"]),
        reverse=True,
    )

    best = results[0]
    top_score = best["score"]
    second_score = results[1]["score"] if len(results) > 1 else 0

    # This is a heuristic indicator, not a calibrated probability.
    if top_score == 0:
        confidence = "Low"
    elif top_score > second_score:
        confidence = "Moderate" if top_score == 1 else "Higher"
    else:
        confidence = "Low"

    return {
        "sentence": sentence,
        "target": target,
        "found": True,
        "predicted_sense": best,
        "candidate_count": len(results),
        "candidates": results[:12],
        "confidence": confidence,
        "method": "Lesk-style contextual overlap with frequency tie-break",
        "explanation": (
            "The system compares the words surrounding the target with "
            "WordNet definitions, synonyms and example sentences. "
            "The highest-scoring sense is selected. This is a lightweight "
            "heuristic and may need human review."
        ),
    }


def write_report():
    samples = load_samples()
    rows = []
    correct = 0
    evaluated = 0

    for sample in samples:
        try:
            result = analyze_sentence(sample["sentence"], sample["target"])
            predicted = (
                result.get("predicted_sense", {}).get("definition", "")
                if result.get("found")
                else ""
            )
            predicted_name = (
                result.get("predicted_sense", {}).get("name", "")
                if result.get("found")
                else ""
            )

            expected = sample.get("expected", "")
            # Reference labels are approximate descriptions, not WordNet IDs.
            # A lexical label match is reported separately from model output.
            match = bool(
                predicted
                and any(
                    token in (predicted + " " + predicted_name).lower()
                    for token in tokenize(expected)
                    if len(token) > 3
                )
            )
            evaluated += 1
            correct += int(match)
            rows.append({
                "id": sample["id"],
                "target": sample["target"],
                "sentence": sample["sentence"],
                "reference_label": expected,
                "predicted_sense": predicted_name,
                "definition": predicted,
                "overlap_score": result.get("predicted_sense", {}).get("score", 0),
                "label_match_heuristic": match,
            })
        except (ValueError, LookupError) as error:
            rows.append({
                "id": sample.get("id"),
                "target": sample.get("target"),
                "sentence": sample.get("sentence"),
                "error": str(error),
            })

    report_path = REPORT_DIR / "wsd_analysis_report.txt"
    with report_path.open("w", encoding="utf-8") as file:
        file.write("WORDSENSE STUDIO — WSD ANALYSIS REPORT\n")
        file.write("=" * 48 + "\n")
        file.write(f"Generated: {datetime.now().astimezone().isoformat()}\n")
        file.write("Algorithm: Lesk-style contextual overlap\n")
        file.write("Lexical resource: NLTK WordNet\n\n")
        file.write(f"Sample sentences: {len(samples)}\n")
        file.write(f"Evaluated sentences: {evaluated}\n")
        file.write(
            "Reference-label heuristic matches: "
            f"{correct}/{evaluated}\n\n"
        )
        file.write(
            "IMPORTANT: The reference labels are human-readable descriptions, "
            "not verified gold-standard WordNet synset annotations. The match "
            "count above is only a rough lexical heuristic and must not be "
            "presented as benchmark accuracy.\n\n"
        )

        for row in rows:
            file.write(f"Sample {row.get('id')}: {row.get('sentence')}\n")
            file.write(f"Target: {row.get('target')}\n")
            file.write(f"Reference label: {row.get('reference_label', 'N/A')}\n")
            file.write(f"Predicted sense: {row.get('predicted_sense', 'N/A')}\n")
            file.write(f"Definition: {row.get('definition', 'N/A')}\n")
            file.write(f"Overlap score: {row.get('overlap_score', 'N/A')}\n")
            file.write("-" * 48 + "\n")

    return report_path, rows


@app.route("/")
def index():
    return render_template("index.html")


@app.get("/api/health")
def health():
    try:
        wn.synsets("bank")
        return jsonify({
            "status": "ok",
            "wordnet": "ready",
            "samples": len(load_samples()),
        })
    except LookupError:
        return jsonify({
            "status": "error",
            "message": "WordNet is not installed. Run the setup instructions.",
        }), 503


@app.get("/api/samples")
def samples():
    return jsonify(load_samples())


@app.post("/api/analyze")
def analyze():
    payload = request.get_json(silent=True) or {}
    try:
        result = analyze_sentence(
            payload.get("sentence", ""),
            payload.get("target", ""),
        )
        return jsonify(result)
    except ValueError as error:
        return jsonify({"error": str(error)}), 400
    except LookupError:
        return jsonify({
            "error": "WordNet data is missing. Run the NLTK download command."
        }), 503


@app.post("/api/report")
def generate_report():
    try:
        path, rows = write_report()
        return jsonify({
            "message": "Analysis report generated successfully.",
            "filename": path.name,
            "results": rows,
            "download_url": "/api/report/download",
        })
    except (OSError, LookupError, ValueError) as error:
        return jsonify({"error": str(error)}), 500


@app.get("/api/report/download")
def download_report():
    from flask import send_from_directory

    path = REPORT_DIR / "wsd_analysis_report.txt"
    if not path.exists():
        write_report()
    return send_from_directory(
        REPORT_DIR,
        path.name,
        as_attachment=True,
        download_name=path.name,
    )


if __name__ == "__main__":
    app.run(debug=True, port=5000)
