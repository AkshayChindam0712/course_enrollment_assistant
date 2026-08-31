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

    if __name__ == "__main__":

        questions = [
            ("prerequisites.md",
            "student completed the prerequisite course but their grade was below the minimum required grade"),

            ("fees.md",
            "student has unpaid fees and therefore cannot enrol in any course"),

            ("capacity.md",
            "the course has reached its maximum capacity and no additional students may join"),

            ("credit_limit.md",
            "adding the requested course would make the student's total credits greater than 60 in the current term"),

            ("timetable.md",
            "the requested course overlaps with a course the student is currently taking on the same day"),

            ("waivers.md",
            "student wants to request a waiver for a prerequisite because they have equivalent experience"),

            ("withdrawal.md",
            "student wants to drop a course during the first three weeks of the term"),

            ("advice.md",
            "student has multiple enrolment problems and should be told every reason, why each blocks enrolment, and what they can do next")
        ]

    for rule, question in questions:

        print("\nRule:", rule)
        print("Question:", question)
        print("Top results:")

        for result in search(question):

            print(
                f"  {result['file']}: "
                f"{result['score']:.2f}"
            )