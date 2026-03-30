#!/usr/bin/env bash
# SCRIPTS/download_embeddings.sh — Download sentence-transformer models.
#
# Downloads the embedding models used for ingestion and query.
# This is a one-time setup step. Models are cached in ~/.cache/huggingface/.
#
# Usage:
#   ./download_embeddings.sh          # Download all-MiniLM-L6-v2 (default)
#   ./download_embeddings.sh --mpnet   # Download all-mpnet-base-v2 (better, slower)

set -e

MODEL="${1:-all-MiniLM-L6-v2}"

echo "==> Downloading sentence-transformer model: ${MODEL}"
echo "    This may take a few minutes on first run (download ~90MB for MiniLM)."
echo "    Models are cached in ~/.cache/huggingface/"
echo ""

python3 -c "
from sentence_transformers import SentenceTransformer
print('Loading model: ${MODEL}')
model = SentenceTransformer('${MODEL}')
print(f'Model loaded. Embedding dimension: {model.get_sentence_embedding_dimension()}')
print('Download complete!')
"

echo ""
echo "==> Verification:"
python3 -c "
from sentence_transformers import SentenceTransformer
model = SentenceTransformer('${MODEL}')
vec = model.encode('test')
print(f'  Vector shape: {vec.shape}')
print(f'  All good!')
"
