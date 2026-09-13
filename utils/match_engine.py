import numpy as np
from sklearn.cluster import KMeans


def match_users(candidate_pool, base_index, top_k=None, min_similarity=None):
    """Finds users with similar viewpoint vectors (cosine similarity).

    Embeddings are normalized once as a matrix to avoid per-loop norm recomputation.
    Zero vectors always get similarity 0.
    """
    if not candidate_pool:
        return []
    if not 0 <= base_index < len(candidate_pool):
        raise IndexError('base_index out of range')
    if top_k is not None and top_k < 0:
        raise ValueError('top_k cannot be negative')

    vectors = np.asarray([item['embedding'] for item in candidate_pool], dtype=float)
    if vectors.ndim != 2:
        raise ValueError('embeddings must be same-dimension 1D vectors')

    norms = np.linalg.norm(vectors, axis=1, keepdims=True)
    normalized = np.divide(vectors, norms, out=np.zeros_like(vectors), where=norms != 0)
    similarities = normalized @ normalized[base_index]

    results = []
    for index, similarity in enumerate(similarities):
        if index == base_index:
            continue
        similarity = float(np.clip(similarity, -1.0, 1.0))
        if min_similarity is not None and similarity < min_similarity:
            continue
        results.append({
            'index': index,
            'input': candidate_pool[index]['input_text'],
            'similarity': round(similarity, 4),
            'profile': candidate_pool[index],
        })

    results.sort(key=lambda item: (-item['similarity'], item['index']))
    if top_k is not None:
        results = results[:top_k]
    return results


def match_complementary(candidate_pool, base_index, top_k=None):
    """Finds users whose viewpoint vectors complement the base user.

    Complementary score = average of dimension-wise gaps where the other user
    scores higher than the base user. High score means the other user covers
    dimensions the base user lacks -- ideal for sparking discussion.
    """
    if not candidate_pool:
        return []
    if not 0 <= base_index < len(candidate_pool):
        raise IndexError('base_index out of range')

    base_vec = np.asarray(candidate_pool[base_index]['embedding'], dtype=float)
    base_norm = np.linalg.norm(base_vec)
    if base_norm > 0:
        base_vec = base_vec / base_norm

    vectors = np.asarray([item['embedding'] for item in candidate_pool], dtype=float)
    norms = np.linalg.norm(vectors, axis=1, keepdims=True)
    normalized = np.divide(vectors, norms, out=np.zeros_like(vectors), where=norms != 0)

    results = []
    for index, vec in enumerate(normalized):
        if index == base_index:
            continue
        gaps = vec - base_vec
        # only count dimensions where other user is stronger
        positive_gaps = np.where(gaps > 0, gaps, 0.0)
        comp_score = float(positive_gaps.mean())
        # also capture which dimensions are complementary for explanation
        top_dim_indices = np.argsort(positive_gaps)[::-1][:3]
        results.append({
            'index': index,
            'input': candidate_pool[index]['input_text'],
            'complementary_score': round(comp_score, 4),
            'top_complement_dims': top_dim_indices.tolist(),
            'profile': candidate_pool[index],
        })

    results.sort(key=lambda item: (-item['complementary_score'], item['index']))
    if top_k is not None:
        results = results[:top_k]
    return results


def get_similarity_breakdown(profile_a, profile_b):
    """Returns per-dimension similarity breakdown between two user profiles.

    For each of the 8 viewpoint dimensions, returns both users' scores
    and whether they are aligned (gap < 0.1), divergent (gap > 0.3),
    or neutral.
    """
    vec_a = np.asarray(profile_a['embedding'], dtype=float)
    vec_b = np.asarray(profile_b['embedding'], dtype=float)
    names = profile_a.get('viewpoint_names', [
        'Science Optimism', 'Social Equity', 'Cultural Inclusion',
        'Risk Caution', 'Individual-Collective', 'Pragmatism',
        'Innovation Adoption', 'Civic Engagement'
    ])

    breakdown = []
    for i, name in enumerate(names):
        a_score = float(vec_a[i]) if i < len(vec_a) else 0.0
        b_score = float(vec_b[i]) if i < len(vec_b) else 0.0
        gap = abs(a_score - b_score)
        if gap < 0.1:
            alignment = 'aligned'
        elif gap > 0.3:
            alignment = 'divergent'
        else:
            alignment = 'neutral'
        breakdown.append({
            'dimension': name,
            'score_a': round(a_score, 4),
            'score_b': round(b_score, 4),
            'gap': round(gap, 4),
            'alignment': alignment,
        })
    return breakdown


def cluster_users(candidate_pool):
    """K-Means clustering on 8-dim viewpoint vectors.

    Returns (user_clustered, centers). If pool is too small, cluster=-1 and centers=None.
    """
    if not candidate_pool or len(candidate_pool) < 2:
        for item in candidate_pool:
            item['cluster'] = -1
        return candidate_pool, None

    vecs = np.array([item['embedding'] for item in candidate_pool])
    n_clusters = min(3, vecs.shape[0])
    kmeans = KMeans(n_clusters=n_clusters, random_state=42, n_init='auto')
    labels = kmeans.fit_predict(vecs)
    centers = kmeans.cluster_centers_

    user_clustered = []
    for idx, item in enumerate(candidate_pool):
        new_item = item.copy()
        new_item['cluster'] = int(labels[idx])
        user_clustered.append(new_item)
    return user_clustered, centers
