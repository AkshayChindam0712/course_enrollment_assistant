from pathlib import Path

import numpy as np
from sentence_transformers import SentenceTransformer


HANDBOOK_DIR = Path("data") / "handbook"

MODEL_NAME = "BAAI/bge-small-en-v1.5"

model = SentenceTransformer(MODEL_NAME)


# ------------------------------------------------------------
# Read the eight handbook files
# ------------------------------------------------------------

documents = []

for path in sorted(HANDBOOK_DIR.glob("*.md")):

    text = path.read_text(
        encoding="utf-8"
    ).strip()

    if text:
        documents.append(
            {
                "file": path.name,
                "text": text
            }
        )


# ------------------------------------------------------------
# Create embeddings
# ------------------------------------------------------------

texts = [
    document["text"]
    for document in documents
]

embeddings = model.encode(
    texts,
    normalize_embeddings=True
)


# ------------------------------------------------------------
# Search
# ------------------------------------------------------------

def search(question, k=3):

    question_embedding = model.encode(
        [question],
        normalize_embeddings=True
    )[0]

    scores = np.dot(
        embeddings,
        question_embedding
    )

    best_indexes = np.argsort(
        scores
    )[::-1][:k]

    results = []

    for index in best_indexes:

        results.append(
            {
                "file": documents[index]["file"],
                "score": float(scores[index])
            }
        )

    return results


# ------------------------------------------------------------
# Test search
# ------------------------------------------------------------

if __name__ == "__main__":

    question = (
        "student is currently enrolled in courses and adding another "
        "course would put their total credits above the maximum of "
        "60 credits for one term"
    )
    print("Question:")
    print(question)

    print()
    print("Top results:")

    for result in search(question):

        print(
            f"{result['file']}: "
            f"{result['score']:.2f}"
        )