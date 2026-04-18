# RAG Corpus

MVP corpus of 12 PDFs covering Three-North Shelterbelt, Horqin, and Hunshandake.

## Recreating

PDFs are gitignored. To reproduce:

```bash
bash backend/rag/download_corpus.sh          # 12/35 succeed (MDPI blocks curl)
bash backend/rag/download_corpus_round2.sh   # retry + alternates
```

Any MDPI papers you want to add, download manually via browser and drop into
`papers_en/`, then run:

```bash
python -m rag.ingest --rebuild
```

## Structure

- `gov/` — Chinese government reports, standards
- `papers_cn/` — Chinese peer-reviewed papers
- `papers_en/` — English peer-reviewed papers
- `standards/` — (placeholder for future technical standards)
