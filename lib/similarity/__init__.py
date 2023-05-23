from typing import List


VECTOR_LETTER_ORDER = 'abcdefghijklmnopqrstuvwxyz012345789-_'


def make_word_vector(word):
    """Turn 'word' into a vector of letter/number occurance counts.  All symbols and unicode
    other than dash and underscore are treated as being the same character."""

    word = word.strip().lower()
    # Add 1 for the non-recognized characters.
    vec = [0] * (len(VECTOR_LETTER_ORDER) + 1)

    for ltr in word:
        if ltr in VECTOR_LETTER_ORDER:
            idx = VECTOR_LETTER_ORDER.index(ltr)
        else:
            idx = len(VECTOR_LETTER_ORDER)
        vec[idx] += 1

    return vec


def vec_dot(vec1, vec2):
    """Take the dot product of two equal length numerical vectors."""

    return sum([vec1[i]*vec2[i] for i in range(len(vec1))])


def vec_magnitude(vec):
    """Return the magnitude of the given vector."""

    return abs(vec_dot(vec, vec))**0.5


def vec_cos(vec1, vec2):
    """Return the cos of the angular difference between the two vectors."""

    return vec_dot(vec1, vec2)/(vec_magnitude(vec1)*vec_magnitude(vec2))

def find_matches(base:str , items:List[str], min_score: float = 0.8) -> List[str]:
    """Find similar items to the one base word, using cosine similarity."""

    base_vec = make_word_vector(base)

    scores = []
    for item in items:
        item = str(item)
        item_vec = make_word_vector(item)

        scores.append((vec_cos(base_vec, item_vec), item))

    scores.sort(reverse=True)
    matches = []
    for score, item in scores:
        if score > min_score:
            matches.append(item)
        else:
            break

    return matches
