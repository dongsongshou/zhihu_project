import numpy as np
import pandas as pd
from sklearn.metrics.pairwise import cosine_similarity
from sklearn.cluster import KMeans
from .config import CLUSTER_NUM, VECTOR_DIM

def calc_similarity(vec_a:list[float], vec_b:list[float])->float:
    a = np.array(vec_a).reshape(1,-1)
    b = np.array(vec_b).reshape(1,-1)
    cos_sim = float(cosine_similarity(a,b)[0][0])
    euc_dis = np.linalg.norm(np.array(vec_a)-np.array(vec_b))
    # 融合算法
    final = cos_sim - 0.1 * euc_dis
    return round(max(min(final,1.0),-1.0),3)

def calc_conflict_consensus(vec_a, vec_b):
    sim = calc_similarity(vec_a,vec_b)
    consensus = round((sim + 1)/2 * 100,1)
    conflict = round(100 - consensus,1)
    return consensus, conflict

def cluster_users(user_list):
    vecs = [u["embedding"] for u in user_list]
    kmeans = KMeans(n_clusters=CLUSTER_NUM, random_state=42)
    labels = kmeans.fit_predict(vecs)
    for idx,u in enumerate(user_list):
        u["cluster"] = int(labels[idx])
    return user_list, kmeans.cluster_centers_

def match_candidates(base_user, candidate_list, mode="syntropy"):
    base_vec = np.array(base_user["embedding"])
    res = []
    for cand in candidate_list:
        sim = calc_similarity(base_user["embedding"], cand["embedding"])
        consensus, conflict = calc_conflict_consensus(base_user["embedding"], cand["embedding"])

        if mode == "syntropy":
            weight = sim
            reason=f"共识度{consensus}%，观点高度契合，适合深度共鸣交流"
        elif mode == "complement":
            weight = 1.0 - abs(sim-0.5)*2
            reason=f"共识度{consensus}%，视角互补，适合互相启发"
        else:
            weight = 1.0 - sim
            reason=f"冲突度{conflict}%，视角差异大，可打破信息茧房"

        res.append({
            **cand,
            "similarity":sim,
            "consensus":consensus,
            "conflict":conflict,
            "weight_score":round(weight,3),
            "reason":reason
        })
    res.sort(key=lambda x:x["weight_score"],reverse=True)
    return res
