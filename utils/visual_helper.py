import numpy as np
import matplotlib.pyplot as plt
import matplotlib
from matplotlib.patches import FancyArrowPatch
import io

matplotlib.rcParams['font.family'] = ['SimHei', 'Microsoft YaHei', 'DejaVu Sans']
matplotlib.rcParams['axes.unicode_minus'] = False

DIM_LABELS = [
    '科技乐观', '社会公平', '文化包容', '风险审慎',
    '个人/集体', '现实务实', '创新接纳', '公共参与'
]


def _radar_axes(fig, rect, n):
    import matplotlib.patches as mpatches
    angles = [i / n * 2 * np.pi for i in range(n)] + [0]
    ax = fig.add_axes(rect, polar=True)
    ax.set_theta_offset(np.pi / 2)
    ax.set_theta_direction(-1)
    ax.set_xticks(angles[:-1])
    ax.set_xticklabels(DIM_LABELS, size=9)
    ax.set_ylim(0, 1)
    ax.set_yticks([0.25, 0.5, 0.75, 1.0])
    ax.set_yticklabels(['', '0.5', '', '1.0'], size=7)
    ax.grid(color='grey', linestyle='--', linewidth=0.5, alpha=0.5)
    return ax, angles


def plot_single_radar(embedding, label='用户', color='#4A90D9'):
    "`Single-user 8-dim radar chart. Returns PNG bytes."
    vec = np.asarray(embedding, dtype=float)
    n = len(vec)
    norm = np.linalg.norm(vec)
    vec_norm = vec / norm if norm > 0 else vec

    fig = plt.figure(figsize=(5, 5), facecolor='white')
    ax, angles = _radar_axes(fig, [0.1, 0.1, 0.8, 0.8], n)

    values = list(vec_norm) + [vec_norm[0]]
    ax.plot(angles, values, color=color, linewidth=2)
    ax.fill(angles, values, color=color, alpha=0.25)
    ax.set_title(label, size=12, pad=15, fontweight='bold')

    buf = io.BytesIO()
    plt.savefig(buf, format='png', dpi=120, bbox_inches='tight')
    plt.close(fig)
    buf.seek(0)
    return buf.read()


def plot_compare_radar(embedding_a, label_a, embedding_b, label_b):
    "`Two-user overlay radar chart. Returns PNG bytes."
    vec_a = np.asarray(embedding_a, dtype=float)
    vec_b = np.asarray(embedding_b, dtype=float)
    n = len(vec_a)

    def _norm(v):
        nrm = np.linalg.norm(v)
        return v / nrm if nrm > 0 else v

    vec_a = _norm(vec_a)
    vec_b = _norm(vec_b)

    fig = plt.figure(figsize=(6, 6), facecolor='white')
    ax, angles = _radar_axes(fig, [0.1, 0.1, 0.8, 0.8], n)

    for vec, label, color in [
        (vec_a, label_a, '#4A90D9'),
        (vec_b, label_b, '#E87040'),
    ]:
        values = list(vec) + [vec[0]]
        ax.plot(angles, values, color=color, linewidth=2, label=label)
        ax.fill(angles, values, color=color, alpha=0.15)

    ax.legend(loc='upper right', bbox_to_anchor=(1.35, 1.15), fontsize=9)
    ax.set_title('观点对比雷达图', size=12, pad=15, fontweight='bold')

    buf = io.BytesIO()
    plt.savefig(buf, format='png', dpi=120, bbox_inches='tight')
    plt.close(fig)
    buf.seek(0)
    return buf.read()


def plot_group_heatmap(candidate_pool):
    "`Heatmap of all users x 8 dimensions. Returns PNG bytes."
    if not candidate_pool:
        return None
    labels = [p.get('input_text', f'用户{i}') for i, p in enumerate(candidate_pool)]
    matrix = np.array([p['embedding'] for p in candidate_pool], dtype=float)
    # row-wise normalise so each user's vector is on the same scale
    norms = np.linalg.norm(matrix, axis=1, keepdims=True)
    matrix = np.divide(matrix, norms, out=np.zeros_like(matrix), where=norms != 0)

    fig, ax = plt.subplots(figsize=(max(8, len(DIM_LABELS)), max(3, len(labels) * 0.6 + 1)))
    im = ax.imshow(matrix, aspect='auto', cmap='RdYlGn', vmin=0, vmax=0.6)
    ax.set_xticks(range(len(DIM_LABELS)))
    ax.set_xticklabels(DIM_LABELS, rotation=30, ha='right', fontsize=9)
    ax.set_yticks(range(len(labels)))
    ax.set_yticklabels(labels, fontsize=9)
    plt.colorbar(im, ax=ax, label='观点强度')
    ax.set_title('候选池观点分布热力图', fontsize=12, fontweight='bold')
    plt.tight_layout()

    buf = io.BytesIO()
    plt.savefig(buf, format='png', dpi=120, bbox_inches='tight')
    plt.close(fig)
    buf.seek(0)
    return buf.read()
