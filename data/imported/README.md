# Put the exported files here

Create them with `colab/membrane_index_builder_with_app_export.ipynb` (run all cells, then section 9).

| File | Required | What it is |
|---|---|---|
| `chunks.jsonl` | yes | one JSON object per line (see `chunks.example.jsonl`) |
| `embeddings.npy` | yes | float32 array, shape (number_of_chunks, dimension) |
| `embedding_info.json` | yes | model name + query prefix (see `embedding_info.example.json`) |
| `pages.json` | recommended | page text `{paper: {page: text}}` - lets the app verify quoted evidence and numbers on the exact page |
| `papers.json` | optional | paper metadata, not required by the app |

## The rules that prevent every compatibility problem
1. Row *i* of `embeddings.npy` belongs to line *i* of `chunks.jsonl` (the notebook guarantees this).
2. Questions are embedded with the model named in `embedding_info.json` and its `query_prefix`.
3. Each chunk needs `chunk_id` (unique), `text`, `source` (paper id such as `P01`) and `page` (integer).
   Optional fields used when present: `section`, `chunk_type` (`text`/`table`/`caption`), `evidence_location`, `table`, `tags`, `title`, `publication_year`, `doi`.

The two `*.example.*` files are only templates; the app ignores them.
