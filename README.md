# Contract LLM Generator (Offline)

Offline system for analysis, structuring and generation of contract documents using local Large Language Models (LLMs).

## Project goal
The goal of the project is to develop an **offline pipeline** that:
- preprocesses and analyzes real contract documents,
- extracts and structures their logical sections,
- and **generates new contracts on demand** based on user requirements, including **bilingual (RU / EN) output**.

The system is designed to operate **without Internet access and cloud-based LLMs**, which is critical for working with confidential contractual data.

## Key functionalities

### 1. Contract preprocessing and analysis (implemented)
- Extraction of text from DOCX files (including tables)
- Cleaning and normalization of contractual text
- Segmentation of contracts into logical sections
- Corpus-level quality analysis of segmentation results

### 2. Knowledge base from real contracts (implemented)
- Conversion of contracts into a structured JSON format
- Preservation of document structure and metadata
- Preparation of a local corpus for further retrieval and generation

### 3. Contract generation using local LLMs (planned / in progress)
- Generation of contracts by user request (e.g. equipment supply, works or services contracts)
- Support for Russian and English languages
- Ability to generate contracts directly in English or as bilingual (RU / EN) documents
- Reuse of real contractual formulations from the local corpus
- Offline operation using local LLM inference

### 4. Quality control and consistency checks (planned)
- Verification of mandatory contract sections
- Terminology consistency (Buyer / Seller, Contractor / Customer, etc.)
- Validation of dates, amounts, currencies and delivery terms
- Cross-language consistency for bilingual contracts

## Project structure

src/
preprocess/ # text cleaning, segmentation, quality analysis
retrieval/ # search and retrieval of relevant contract fragments (planned)
generation/ # contract generation using local LLMs (planned)
export/ # DOCX generation and formatting (planned)

## Offline-first approach
All stages of the pipeline are designed to work **fully offline**:
- no cloud APIs,
- no external LLM services,
- all models and data are stored locally.

This approach ensures data confidentiality and reproducibility of results.

## Academic context
The project is developed as a graduation (thesis) project and focuses on:
- practical NLP processing of legal documents,
- heuristic and corpus-based segmentation methods,
- application of local LLMs for controlled text generation in the legal domain.


