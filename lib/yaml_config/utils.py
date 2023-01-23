

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


def dot(vec1, vec2):
    """Take the dot product of two equal length numerical vectors."""

    return sum([vec1[i]*vec2[i] for i in range(len(vec1))])


def magnitude(vec):
    """Return the magnitude of the given vector."""

    return abs(dot(vec, vec))**0.5


def cos(vec1, vec2):
    """Return the cos of the angular difference between the two vectors."""

    return dot(vec1, vec2)/(magnitude(vec1)*magnitude(vec2))
