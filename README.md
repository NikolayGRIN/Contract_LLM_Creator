\# Contract LLM Creator (Offline)



Offline pipeline for preprocessing (cleaning + segmentation) of contract documents, analysis and using local LLMs.



\## Goals

\- Convert documents to a unified representation (text + metadata)

\- Clean text (remove headers/footers/page numbers, normalize whitespace)

\- Segment contracts into logical sections (Articles/Clauses)

\- Prepare dataset for offline search and local LLM inference



\## Project structure

\- `src/preprocess/` — cleaning + segmentation scripts

\- `src/llm/` — local LLM inference (offline)

\- `src/utils/` — common helpers

\- `data/samples/` — non-confidential sample files/texts (for demonstration only)



\## Data \& privacy

Real contracts and model weights are NOT stored in this repository.

Place confidential files locally (excluded by `.gitignore`).



\## Quick start (Windows)

1\. Create venv:

&nbsp;  ```bash

&nbsp;  python -m venv .venv

&nbsp;  .\\.venv\\Scripts\\activate



