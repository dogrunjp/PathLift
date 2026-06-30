#!/usr/bin/env python3
"""
gpml_layout.py  (v2)
====================
gpml2network.py が抽出した情報をもとに、GPMLの各ノードへレイアウト座標(x,y)を
与え、必要なら GPML の DataNode/Graphics の CenterX/CenterY に書き戻す。

v1からの拡張（PlantCyc系GPMLのような複合構造への対応）
--------------------------------------------------------
GPMLのInteractionを種類で分類してから配置する:
  - conversion   : metabolite→metabolite（mim-conversion等）。レイアウトの背骨(BFS)。
  - translation  : gene→protein（mim-transcription-translation）。
  - catalysis    : 非metaboliteノード→anchor。酵素として反応の脇に配置。
  - reactant     : metabolite→anchor。共基質として反応の反対側・上流に配置。
  - product      : anchor→metabolite。共生成物として反応の反対側・下流に配置。
配置方針:
  - 背骨(conversion)を BFS でレイヤ配置（ルートは入次数0のノードを自動選択）。
  - 各 anchor（反応中心）について、親interactionの両端から反応軸を作り、
    酵素・共基質・共生成物をその軸まわりに配置（酵素と副基質は反対側）。
  - gene→protein は、対応タンパク質から反応中心の逆方向へ押し出して配置。
  - group(複合体)は構成メンバーを縦展開。
旧来の直鎖パスウェイ(WP5586)でも結果は変わらない（translation/reactant/productが
無いため、conversion背骨＋catalysis酵素配置のみが効く）。
"""

from __future__ import annotations

import argparse
import math
import sys
import xml.etree.ElementTree as ET
from collections import defaultdict

import networkx as nx

import gpml2network as g2n


# --- レイアウト定数 -------------------------------------------------------- #
MIN_STAGE_WIDTH = 400
STAGE_MARGIN = 150
INTERACTION_LENGTH = 180
INDEX_STEP = 150

PERP_ENZYME = 0.75      # 酵素を反応軸から離す距離（×|AB|）
PERP_METAB = 0.95       # 共基質/共生成物を離す距離（×|AB|）
METAB_ALONG = 0.35      # 共基質(上流)/共生成物(下流)の軸方向ずらし（×|AB|）
ENZYME_PIX_STEP = 34    # 同一anchorに複数酵素 → 軸方向にこのpx間隔で扇状（重なり防止）
METAB_PIX_STEP = 90     # 共基質/共生成物が複数のときの扇状間隔(px)
GENE_GAP = 120          # gene を protein から押し出す距離
GENE_FAN = 36           # 1タンパク質に複数遺伝子のときの間隔
GROUP_ROW_HEIGHT = 40   # group メンバーの縦展開間隔


# --------------------------------------------------------------------------- #
# 幾何ヘルパ
# --------------------------------------------------------------------------- #
def _unit(dx, dy):
    L = math.hypot(dx, dy) or 1.0
    return dx / L, dy / L, L


def _frame(A, B):
    """反応軸 A->B の 単位ベクトル u, 垂直単位ベクトル n, 長さ L を返す。"""
    ux, uy, L = _unit(B[0] - A[0], B[1] - A[1])
    return (ux, uy), (-uy, ux), L


def _lerp(A, B, r):
    return (A[0] + r * (B[0] - A[0]), A[1] + r * (B[1] - A[1]))


# --------------------------------------------------------------------------- #
# 分類
# --------------------------------------------------------------------------- #
def classify(parsed: g2n.Parsed):
    """Interactionを種類別に分類。"""
    anchor_ids = parsed.anchor_ids
    conversions, translations = [], []
    catalysis, reactants, products = [], [], []  # 各 (node_ref, anchor_id)

    for itx in parsed.interactions:
        s, e = itx.start_ref, itx.end_ref
        if not s or not e:
            continue
        if s in anchor_ids or e in anchor_ids:
            anchor = s if s in anchor_ids else e
            node = e if s in anchor_ids else s
            ntype = parsed.nodes[node].node_type if node in parsed.nodes else None
            if ntype == "Metabolite":
                if e in anchor_ids:            # node -> anchor（流入＝基質）
                    reactants.append((node, anchor))
                else:                          # anchor -> node（流出＝生成物）
                    products.append((node, anchor))
            else:                              # 酵素（protein/gene/group/不明）
                catalysis.append((node, anchor))
        else:
            if itx.arrowhead == "mim-transcription-translation":
                translations.append((s, e))    # gene -> protein
            else:
                conversions.append(itx)        # metabolite変換（背骨）
    return conversions, translations, catalysis, reactants, products


# --------------------------------------------------------------------------- #
# 背骨（conversion）の BFS 配置
# --------------------------------------------------------------------------- #
def detect_root(conv_edges):
    sources = {s for s, _ in conv_edges}
    targets = {t for _, t in conv_edges}
    roots = sorted(sources - targets)
    if roots:
        return roots[0]
    return sorted(sources)[0] if sources else None


def backbone_positions(conv_edges, root):
    G = nx.Graph()
    G.add_edges_from(conv_edges)
    if root is None or root not in G:
        return {}
    layers = dict(enumerate(nx.bfs_layers(G, [root])))
    pos = {}
    rel = [{"name": n, "layer": ln, "indx": i, "total": len(mem)}
           for ln, mem in layers.items() for i, n in enumerate(mem)]
    max_index = max((r["indx"] for r in rel), default=0)
    stage_width = MIN_STAGE_WIDTH + max_index * INDEX_STEP
    for n in rel:
        x = (n["indx"] + 1) * stage_width / (n["total"] + 1) + STAGE_MARGIN
        y = INTERACTION_LENGTH * n["layer"] + STAGE_MARGIN
        pos[n["name"]] = (x, y)
    return pos


# --------------------------------------------------------------------------- #
# anchor まわり（酵素・共基質・共生成物）の配置
# --------------------------------------------------------------------------- #
def satellite_positions(parsed, pos, catalysis, reactants, products):
    ibyid = parsed.interaction_by_id
    result = {}
    enzyme_anchor_M = {}   # enzyme_ref -> 反応中心M（gene配置で使う）

    def group_by_anchor(pairs):
        d = defaultdict(list)
        for node, anchor in pairs:
            d[anchor].append(node)
        return d

    enz_by_a = group_by_anchor(catalysis)
    react_by_a = group_by_anchor(reactants)
    prod_by_a = group_by_anchor(products)

    placed = set()  # 1ノード1座標（複数反応に跨る酵素は最初の反応で確定）

    for aid in set(list(enz_by_a) + list(react_by_a) + list(prod_by_a)):
        anchor = parsed.anchors.get(aid)
        if not anchor:
            continue
        parent = ibyid.get(anchor.interaction_id)
        if not parent:
            continue
        A = pos.get(parent.start_ref)
        B = pos.get(parent.end_ref)
        if not A or not B:
            continue
        (ux, uy), (nx_, ny_), L = _frame(A, B)
        M = _lerp(A, B, anchor.position)

        # --- 酵素：+n 側に、軸方向へpx固定間隔で扇状 ---
        enzymes = [x for x in enz_by_a.get(aid, []) if x not in placed]
        K = len(enzymes)
        for k, node in enumerate(enzymes):
            t = (k - (K - 1) / 2) * ENZYME_PIX_STEP
            foot = (M[0] + ux * t, M[1] + uy * t)
            p = (foot[0] + nx_ * PERP_ENZYME * L, foot[1] + ny_ * PERP_ENZYME * L)
            result[node] = p
            enzyme_anchor_M[node] = M
            placed.add(node)

        # --- 共基質：-n 側・上流(-u) に ---
        rs = [x for x in react_by_a.get(aid, []) if x not in placed]
        for j, node in enumerate(rs):
            off = (j - (len(rs) - 1) / 2) * METAB_PIX_STEP
            base = (M[0] - nx_ * PERP_METAB * L - ux * METAB_ALONG * L,
                    M[1] - ny_ * PERP_METAB * L - uy * METAB_ALONG * L)
            result[node] = (base[0] + nx_ * off, base[1] + ny_ * off)
            placed.add(node)

        # --- 共生成物：-n 側・下流(+u) に ---
        ps = [x for x in prod_by_a.get(aid, []) if x not in placed]
        for j, node in enumerate(ps):
            off = (j - (len(ps) - 1) / 2) * METAB_PIX_STEP
            base = (M[0] - nx_ * PERP_METAB * L + ux * METAB_ALONG * L,
                    M[1] - ny_ * PERP_METAB * L + uy * METAB_ALONG * L)
            result[node] = (base[0] + nx_ * off, base[1] + ny_ * off)
            placed.add(node)

    return result, enzyme_anchor_M


# --------------------------------------------------------------------------- #
# gene -> protein の配置（タンパク質から反応中心の逆へ押し出す）
# --------------------------------------------------------------------------- #
def gene_positions(translations, pos, enzyme_anchor_M):
    # protein -> [genes]
    genes_of = defaultdict(list)
    for gene, protein in translations:
        genes_of[protein].append(gene)

    result = {}
    for protein, genes in genes_of.items():
        ppos = pos.get(protein)
        if not ppos:
            continue
        M = enzyme_anchor_M.get(protein)
        if M:
            dx, dy, _ = _unit(ppos[0] - M[0], ppos[1] - M[1])
        else:
            dx, dy = -1.0, 0.0  # フォールバック：左へ
        px_, py_ = -dy, dx      # 押し出し方向に垂直（複数遺伝子の扇）
        G = len(genes)
        for k, gene in enumerate(genes):
            off = (k - (G - 1) / 2) * GENE_FAN
            result[gene] = (ppos[0] + dx * GENE_GAP + px_ * off,
                            ppos[1] + dy * GENE_GAP + py_ * off)
    return result


def expand_groups(positions, parsed):
    out = dict(positions)
    for gid in list(positions.keys()):
        grp = parsed.groups.get(gid)
        if not grp:
            continue
        x, y = positions[gid]
        members = grp["members"]
        M = len(members)
        for k, m in enumerate(members):
            out[m] = (x, y + (k - (M - 1) / 2) * GROUP_ROW_HEIGHT)
        out.pop(gid, None)
    return out


# --------------------------------------------------------------------------- #
# レイアウト本体
# --------------------------------------------------------------------------- #
def bfs_layout(parsed: g2n.Parsed, root=None) -> dict:
    conversions, translations, catalysis, reactants, products = classify(parsed)
    conv_edges = [(i.start_ref, i.end_ref) for i in conversions]

    if root is None:
        root = detect_root(conv_edges)
    backbone = backbone_positions(conv_edges, root)

    sats, enzyme_M = satellite_positions(parsed, backbone, catalysis, reactants, products)
    merged = {**backbone, **sats}
    merged = expand_groups(merged, parsed)

    genes = gene_positions(translations, merged, enzyme_M)
    merged = {**merged, **genes}

    for gid, (x, y) in merged.items():
        if gid in parsed.nodes:
            parsed.nodes[gid].x = x
            parsed.nodes[gid].y = y
    return merged


# --------------------------------------------------------------------------- #
# 接続辺の最適化（矩形のどの辺に付けるか）
# --------------------------------------------------------------------------- #
def _side_point(box, target):
    """
    box=(cx,cy,w,h) の中心から target=(tx,ty) へ向かうレイが抜ける辺を選び、
    その辺の中点の絶対座標と RelX/RelY を返す。矩形のアスペクト比を考慮する
    （＝幾何的に最短となる側）。
    """
    cx, cy, w, h = box
    hw, hh = w / 2.0, h / 2.0
    dx, dy = target[0] - cx, target[1] - cy
    if dx == 0 and dy == 0:
        return cx, cy, 0.0, 0.0
    # |dx|/hw と |dy|/hh の大小で、左右の辺か上下の辺かを決める
    if hh * abs(dx) >= hw * abs(dy):
        relx = 1.0 if dx > 0 else -1.0
        rely = 0.0
    else:
        rely = 1.0 if dy > 0 else -1.0
        relx = 0.0
    return cx + relx * hw, cy + rely * hh, relx, rely


def assign_connection_points(parsed, positions):
    """
    各 Interaction の両端 Point について、最短になる接続辺(RelX/RelY)と
    絶対座標(X/Y)を決める。返り値: {interaction_id: ((sx,sy,srx,sry),(ex,ey,erx,ery))}
    """
    anchor_ids = parsed.anchor_ids
    ibyid = parsed.interaction_by_id

    # ノードの矩形ボックス
    box = {}
    for gid, n in parsed.nodes.items():
        if gid in positions:
            cx, cy = positions[gid]
        elif n.x is not None:
            cx, cy = n.x, n.y
        else:
            continue
        box[gid] = (cx, cy, n.width, n.height)

    edge_pts = {}

    # 1) ノード同士のエッジ（anchorを含まない）→ 互いの中心へ向けて辺を選ぶ
    for itx in parsed.interactions:
        s, e = itx.start_ref, itx.end_ref
        if not s or not e or s in anchor_ids or e in anchor_ids:
            continue
        if s in box and e in box:
            sp = _side_point(box[s], (box[e][0], box[e][1]))
            ep = _side_point(box[e], (box[s][0], box[s][1]))
            edge_pts[itx.graph_id] = (sp, ep)

    # 2) anchor の絶対座標 = 親(変換)interactionの両端接続点を Position で内分
    anchor_xy = {}
    for aid, anchor in parsed.anchors.items():
        par = ibyid.get(anchor.interaction_id)
        if not par:
            continue
        pe = edge_pts.get(par.graph_id)
        if pe:
            (sx, sy, *_), (ex, ey, *_) = pe
        else:
            A, B = box.get(par.start_ref), box.get(par.end_ref)
            if not A or not B:
                continue
            sx, sy, ex, ey = A[0], A[1], B[0], B[1]
        anchor_xy[aid] = (sx + anchor.position * (ex - sx),
                          sy + anchor.position * (ey - sy))

    # 3) 片端が anchor のエッジ（触媒・共基質・共生成物）
    for itx in parsed.interactions:
        s, e = itx.start_ref, itx.end_ref
        if not s or not e or not (s in anchor_ids or e in anchor_ids):
            continue
        aid = s if s in anchor_ids else e
        node = e if s in anchor_ids else s
        axy = anchor_xy.get(aid)
        if node not in box or not axy:
            continue
        nx_, ny_, nrx, nry = _side_point(box[node], axy)
        anchor_pt = (axy[0], axy[1], 0.0, 0.0)   # anchorは点なのでRel=0
        if e in anchor_ids:   # node -> anchor
            edge_pts[itx.graph_id] = ((nx_, ny_, nrx, nry), anchor_pt)
        else:                 # anchor -> node
            edge_pts[itx.graph_id] = (anchor_pt, (nx_, ny_, nrx, nry))

    return edge_pts


# --------------------------------------------------------------------------- #
# GPML への書き戻し
# --------------------------------------------------------------------------- #
def write_gpml_with_layout(input_path, parsed, positions, output_path,
                           fit_board=True, optimize_sides=True, collapse_plan=None,
                           ndigits=2):
    tree = ET.parse(input_path)
    root = tree.getroot()
    ns = root.tag[1:root.tag.index("}")] if root.tag.startswith("{") else ""
    if ns:
        ET.register_namespace("", ns)

    # --- transcript->protein->anchor の畳み込み（Protein/転写翻訳を削除、触媒を張り替え）---
    if collapse_plan is not None:
        for child in list(root):
            ln = g2n.localname(child.tag)
            gid = child.get("GraphId")
            if ln == "DataNode" and gid in collapse_plan.remove_nodes:
                root.remove(child)
            elif ln == "Interaction" and gid in collapse_plan.remove_interactions:
                root.remove(child)
            elif ln == "Interaction" and gid in collapse_plan.rewire:
                for gr in g2n.iter_children(child, "Graphics"):
                    pts = list(g2n.iter_children(gr, "Point"))
                    if pts:
                        pts[0].set("GraphRef", collapse_plan.rewire[gid])

    # --- DataNode の中心を更新 ---
    updated = 0
    for dn in g2n.iter_descendants(root, "DataNode"):
        gid = dn.get("GraphId")
        if gid not in positions:
            continue
        x, y = positions[gid]
        for gr in g2n.iter_children(dn, "Graphics"):
            gr.set("CenterX", str(round(float(x), ndigits)))
            gr.set("CenterY", str(round(float(y), ndigits)))
            updated += 1

    # --- エッジの接続辺(Point の RelX/RelY と X/Y)を更新 ---
    if optimize_sides:
        edge_pts = assign_connection_points(parsed, positions)
        for itx_el in g2n.iter_descendants(root, "Interaction"):
            iid = itx_el.get("GraphId")
            if iid not in edge_pts:
                continue
            points = [pt for gr in g2n.iter_children(itx_el, "Graphics")
                      for pt in g2n.iter_children(gr, "Point")]
            if len(points) < 2:
                continue
            (sx, sy, srx, sry), (ex, ey, erx, ery) = edge_pts[iid]
            for pt, (px, py, rx, ry) in ((points[0], (sx, sy, srx, sry)),
                                         (points[-1], (ex, ey, erx, ery))):
                pt.set("X", str(round(px, ndigits)))
                pt.set("Y", str(round(py, ndigits)))
                pt.set("RelX", str(round(rx, 4)))
                pt.set("RelY", str(round(ry, 4)))

    # --- ボード寸法 ---
    if fit_board and positions:
        xs = [x for x, _ in positions.values()]
        ys = [y for _, y in positions.values()]
        for gr in root:
            if g2n.localname(gr.tag) == "Graphics":
                gr.set("BoardWidth", str(round(max(xs) + STAGE_MARGIN, 1)))
                gr.set("BoardHeight", str(round(max(ys) + STAGE_MARGIN, 1)))
                break

    tree.write(output_path, encoding="UTF-8", xml_declaration=True)
    return updated


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #
def main(argv=None):
    ap = argparse.ArgumentParser(
        description="GPMLにBFSベースのレイアウト座標を与え、CenterX/CenterYへ書き戻す")
    ap.add_argument("input")
    ap.add_argument("--root", help="BFSルートのGraphId（省略時は入次数0を自動選択）")
    ap.add_argument("--write-gpml")
    ap.add_argument("--nodes-out")
    ap.add_argument("--no-fit-board", action="store_true")
    ap.add_argument("--no-optimize-sides", action="store_true",
                    help="接続辺(RelX/RelY)の最短化を行わない")
    ap.add_argument("--no-collapse-proteins", action="store_true",
                    help="transcript->protein->anchor の冗長Protein層を畳み込まない")
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args(argv)

    parsed = g2n.parse_gpml(args.input)

    plan = None
    if not args.no_collapse_proteins:
        plan = g2n.collapse_transcript_protein(parsed)
        g2n.apply_collapse(parsed, plan)

    positions = bfs_layout(parsed, root=args.root)

    if args.nodes_out:
        with open(args.nodes_out, "w", newline="", encoding="utf-8") as f:
            g2n.write_node_list(parsed, f)
    else:
        g2n.write_node_list(parsed, sys.stdout)

    if args.write_gpml:
        n = write_gpml_with_layout(args.input, parsed, positions, args.write_gpml,
                                   fit_board=not args.no_fit_board,
                                   optimize_sides=not args.no_optimize_sides,
                                   collapse_plan=plan)
        if not args.quiet:
            print(f"\n# GPML書き戻し: {args.write_gpml}（DataNode {n}件を更新）", file=sys.stderr)

    if not args.quiet:
        if plan and plan.remove_nodes:
            print(f"# Protein畳み込み: {len(plan.remove_nodes)}個のProteinを削除し触媒を張り替え",
                  file=sys.stderr)
        placed = sum(1 for n in parsed.nodes.values() if n.x is not None)
        print(f"# 配置ノード: {placed}/{len(parsed.nodes)}", file=sys.stderr)


if __name__ == "__main__":
    main()
