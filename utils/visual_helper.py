import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from pyvis.network import Network
import streamlit as st
import streamlit.components.v1 as components

plt.rcParams["font.sans-serif"] = ["SimHei"]
plt.rcParams["axes.unicode_minus"] = False

DIM_NAMES = ["教育观","AI认知","社区文化","思辨态度","实践倾向","情绪倾向","包容度","批判倾向"]

def plot_radar(vec_base, vec_target, label_base="基准用户", label_target="候选用户"):
    num_dim = len(DIM_NAMES)
    angles = np.linspace(0, 2*np.pi, num_dim, endpoint=False).tolist()
    vb, vt = vec_base.copy(), vec_target.copy()
    vb.append(vb[0])
    vt.append(vt[0])
    angles.append(angles[0])

    fig, ax = plt.subplots(figsize=(6,6), subplot_kw={"projection":"polar"})
    ax.plot(angles, vb, "o-", linewidth=2, label=label_base, color="#1f77b4")
    ax.fill(angles, vb, alpha=0.2, color="#1f77b4")
    ax.plot(angles, vt, "o-", linewidth=2, label=label_target, color="#ff7f0e")
    ax.fill(angles, vt, alpha=0.2, color="#ff7f0e")
    ax.set_xticks(angles[:-1])
    ax.set_xticklabels(DIM_NAMES, fontsize=8)
    ax.set_ylim(-0.6,0.8)
    ax.legend(loc="upper right", bbox_to_anchor=(1.3,1.1))
    st.pyplot(fig)

def build_network_html(user_list):
    net = Network(height="500px", width="100%", bgcolor="#111111", font_color="white")
    for idx,u in enumerate(user_list):
        net.add_node(idx, label=u["name"], title=f"聚类:{u.get('cluster',-1)}")
    for i in range(len(user_list)):
        for j in range(i+1, len(user_list)):
            sim = np.dot(user_list[i]["embedding"], user_list[j]["embedding"])
            if sim > 0.05:
                net.add_edge(i,j, value=sim, title=f"相似度:{sim:.2f}")
    return net.generate_html()

def render_pyvis_html(html_str):
    components.html(html_str, height=520)

def plot_cluster_dist(user_list):
    df = pd.DataFrame(user_list)
    st.subheader("🎯 用户聚类分布")
    st.bar_chart(df["cluster"].value_counts())

def plot_heatmap(user_list):
    n = len(user_list)
    mat = np.zeros((n,n))
    for i in range(n):
        for j in range(n):
            mat[i,j] = np.dot(user_list[i]["embedding"], user_list[j]["embedding"])
    fig, ax = plt.subplots()
    sns.heatmap(mat, cmap="coolwarm", ax=ax)
    st.pyplot(fig)
