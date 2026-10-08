# Paper Research Agent (free, Streamlit, light + dark)

Ask questions about your own papers (library mode) or search papers and the web (global mode).
Answers come with stat cards, a color-coded results table, charts and the evidence behind them.
Everything runs on free tiers. API keys live only in **Streamlit secrets**.

## 1. Build your files in Google Colab
Open `colab/membrane_index_builder_with_app_export.ipynb` in Colab (File → Upload notebook).
Name your PDFs `P01.pdf`, `P02.pdf`, ... and run the cells top to bottom (check *Parse health* and the *Table spot-check*).
The last section (**9. Export for the Streamlit app**) downloads `app_files.zip`.

Copy its contents into `data/imported/`:
`chunks.jsonl`, `embeddings.npy`, `embedding_info.json`, `pages.json` (see `data/imported/README.md`).

## 2. Deploy
1. Push this folder to GitHub (`.gitignore` already keeps secrets out).
2. share.streamlit.io → pick the repo, main file `app.py`.
3. App → **Settings → Secrets** (template: `.streamlit/secrets.toml.example`):

```toml
GEMINI_API_KEY = "..."       # free: aistudio.google.com/apikey
GROQ_API_KEY = "..."         # optional backup (free)
OPENALEX_API_KEY = "..."     # free account at openalex.org
TAVILY_API_KEY = "..."       # free 1,000 credits/month
```

4. Open the app → **Data check** → press the test buttons.

## 3. Use it
* **Extract records** (once per paper): builds the structured table of measured values. Uses your schema-driven
  retrieval + all table chunks, then verifies every quote and number against the real page.
* **Ask**: choose *Search my library* or *Search globally*. The page suggests what to type.
* Toggle **🌙 Dark mode** in the sidebar (or open the app with `?theme=dark`).
* Streamlit Cloud forgets files on restart: download `records_seed.json` on the Extract page and commit it to `data/records_seed.json`.

## What retrieval does
Hybrid search = BM25 (with your unit and synonym normalisation) + embedding similarity, fused by reciprocal-rank
fusion, with your evidence-quality priors (tables/results beat introduction/front matter).
The app keeps vectors in numpy and has its own BM25 implementation, so no faiss or rank_bm25 is needed on Streamlit.

## Saving free-tier tokens
Embeddings and search run locally (no LLM). A question costs at most 2 LLM calls. Extraction runs once per paper.

## Change the topic
Fields, prompts and suggested questions are in `core/schema.py`. Colors and CSS are in `ui/theme.py`.

## Known limits
* "Add to library" from global results is not built in: download the open-access PDF and add it with the notebook.
* Values inside figures cannot be extracted; table quality depends on your PDFs (check the notebook's table spot-check).
* Free-tier limits and model names change; override models with `GEMINI_MODEL`, `GROQ_MODEL`, `OPENROUTER_MODEL` secrets.
* Free Gemini may use prompts to improve Google products; keep confidential papers out or use another provider.
# Paper Research Agent (free, Streamlit, light + dark)

Ask questions about your own papers (library mode) or search papers and the web (global mode).
Answers come with stat cards, a color-coded results table, charts and the evidence behind them.
Everything runs on free tiers. API keys live only in **Streamlit secrets**.

## 1. Build your files in Google Colab
Open `colab/membrane_index_builder_with_app_export.ipynb` in Colab (File → Upload notebook).
Name your PDFs `P01.pdf`, `P02.pdf`, ... and run the cells top to bottom (check *Parse health* and the *Table spot-check*).
The last section (**9. Export for the Streamlit app**) downloads `app_files.zip`.

Copy its contents into `data/imported/`:
`chunks.jsonl`, `embeddings.npy`, `embedding_info.json`, `pages.json` (see `data/imported/README.md`).

## 2. Deploy
1. Push this folder to GitHub (`.gitignore` already keeps secrets out).
2. share.streamlit.io → pick the repo, main file `app.py`.
3. App → **Settings → Secrets** (template: `.streamlit/secrets.toml.example`):

```toml
GEMINI_API_KEY = "..."       # free: aistudio.google.com/apikey
GROQ_API_KEY = "..."         # optional backup (free)
OPENALEX_API_KEY = "..."     # free account at openalex.org
TAVILY_API_KEY = "..."       # free 1,000 credits/month
```

4. Open the app → **Data check** → press the test buttons.

## 3. Use it
* **Extract records** (once per paper): builds the structured table of measured values. Uses your schema-driven
  retrieval + all table chunks, then verifies every quote and number against the real page.
* **Ask**: choose *Search my library* or *Search globally*. The page suggests what to type.
* Toggle **🌙 Dark mode** in the sidebar (or open the app with `?theme=dark`).
* Streamlit Cloud forgets files on restart: download `records_seed.json` on the Extract page and commit it to `data/records_seed.json`.

## What retrieval does
Hybrid search = BM25 (with your unit and synonym normalisation) + embedding similarity, fused by reciprocal-rank
fusion, with your evidence-quality priors (tables/results beat introduction/front matter).
The app keeps vectors in numpy and has its own BM25 implementation, so no faiss or rank_bm25 is needed on Streamlit.

## Saving free-tier tokens
Embeddings and search run locally (no LLM). A question costs at most 2 LLM calls. Extraction runs once per paper.

## Change the topic
Fields, prompts and suggested questions are in `core/schema.py`. Colors and CSS are in `ui/theme.py`.

## Known limits
* "Add to library" from global results is not built in: download the open-access PDF and add it with the notebook.
* Values inside figures cannot be extracted; table quality depends on your PDFs (check the notebook's table spot-check).
* Free-tier limits and model names change; override models with `GEMINI_MODEL`, `GROQ_MODEL`, `OPENROUTER_MODEL` secrets.
* Free Gemini may use prompts to improve Google products; keep confidential papers out or use another provider.
