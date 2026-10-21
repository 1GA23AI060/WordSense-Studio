# WordSense Studio

A web-based Word Sense Disambiguation (WSD) learning project built with Flask, NLTK WordNet, HTML, CSS and JavaScript.

## Features
- WordNet candidate senses, definitions, examples and lexical relations
- Lesk-style contextual overlap algorithm with a sense-frequency tie-break
- Custom sentence analysis through a REST API
- Bundled sample sentence dataset
- Generated text analysis report
- Responsive dashboard interface

## Requirements
- Python 3.10 or newer
- Internet access during initial dependency and WordNet downloads

## Run on macOS

```bash
python3 -m venv venv
source venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
python -m nltk.downloader wordnet omw-1.4
python app.py
```

Open http://127.0.0.1:5000 in your browser.

## API
- `GET /api/health` — service status
- `GET /api/samples` — sample dataset
- `POST /api/analyze` — analyze `{"sentence":"...","target":"bank"}`
- `POST /api/report` — generate the report
- `GET /api/report/download` — download the report

## Algorithm
The application scores WordNet synsets by overlap between context tokens and the synset definition, lemma names, and example sentences. Lemma frequency is used as a tie-breaker. This is a lightweight Lesk-style baseline, not a trained or calibrated model. Scores and heuristic confidence labels are not probabilities. Stronger evaluation requires a manually annotated gold-standard dataset.

## Project structure

```text
WordSense-Studio/
├── app.py
├── requirements.txt
├── README.md
├── .gitignore
├── templates/
│   └── index.html
├── static/
│   ├── style.css
│   └── app.js
├── data/
│   └── sample_sentences.json
└── reports/
    └── wsd_analysis_report.txt  # generated
```

## Academic note
The reference descriptions in the bundled dataset are intended for exploration. The generated report explicitly labels its reference matching count as a rough lexical heuristic, not verified benchmark accuracy.
