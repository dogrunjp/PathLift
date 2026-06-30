#!/usr/bin/env python3
"""
gpml2network.py  (v2)
=====================
GPML (WikiPathways) のパスウェイXMLを、ノード-エッジのネットワークデータに変換する。

変換ルール（ネットワーク抽出）
------------------------------
1. ネットワークデータをGPML(XML)から変換する。
2. Interaction の二つの Point を結んでエッジとする。ノード名は GraphRef(GraphId)。
3. Interaction の端点のいずれかが Anchor を参照する場合、そのInteractionは
   エッジに変換しない（＝酵素→反応 の catalysis を除外し、メタボライト変換の
   骨格だけを残す）。

v2の追加点
----------
- レイアウト計算（gpml_layout.py）で必要になる情報を Parsed に保持する:
    * Anchor の Position（interaction上の相対位置 0–1）と親interaction
    * 各 Interaction の start_ref / end_ref（両端の GraphRef）
    * Group の GraphId → メンバー(DataNode)の対応
- GPML2013a / GPML2021 どちらの名前空間でも動く（local nameで判定）。
"""

from __future__ import annotations

import argparse
import csv
import sys
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field


# --------------------------------------------------------------------------- #
# XML helpers（名前空間に依存しない）
# --------------------------------------------------------------------------- #
def localname(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def iter_children(elem, name):
    for child in elem:
        if localname(child.tag) == name:
            yield child


def iter_descendants(elem, name):
    for child in elem.iter():
        if localname(child.tag) == name:
            yield child


# --------------------------------------------------------------------------- #
# データ構造
# --------------------------------------------------------------------------- #
@dataclass
class Node:
    graph_id: str
    label: str | None = None
    node_type: str | None = None
    xref_db: str | None = None
    xref_id: str | None = None
    group_ref: str | None = None   # 所属グループの GroupId
    width: float = 90.0            # 矩形サイズ（接続辺の計算に使う）
    height: float = 25.0
    x: float | None = None         # レイアウト後に埋まる
    y: float | None = None


@dataclass
class Anchor:
    graph_id: str
    interaction_id: str            # このanchorが乗っている親interaction
    position: float                # interaction上の相対位置（0–1）


@dataclass
class Interaction:
    graph_id: str | None
    start_ref: str | None          # 始点 Point の GraphRef
    end_ref: str | None            # 終点 Point の GraphRef
    arrowhead: str | None = None


@dataclass
class Edge:
    source: str
    target: str
    interaction_id: str | None = None
    arrowhead: str | None = None


@dataclass
class Parsed:
    nodes: dict = field(default_factory=dict)          # graph_id -> Node
    anchors: dict = field(default_factory=dict)        # graph_id -> Anchor
    interactions: list = field(default_factory=list)   # 全Interaction
    groups: dict = field(default_factory=dict)         # group GraphId -> {"group_id","members":[gid]}
    edges: list = field(default_factory=list)          # 変換エッジ（骨格）
    skipped: list = field(default_factory=list)        # 除外したInteractionの記録

    @property
    def anchor_ids(self) -> set:
        return set(self.anchors.keys())

    @property
    def interaction_by_id(self) -> dict:
        return {i.graph_id: i for i in self.interactions if i.graph_id}


# --------------------------------------------------------------------------- #
# パース
# --------------------------------------------------------------------------- #
def parse_gpml(path: str) -> Parsed:
    tree = ET.parse(path)
    root = tree.getroot()
    p = Parsed()

    # --- DataNode ---
    group_members = {}  # GroupId -> [node graph_id]
    for dn in iter_descendants(root, "DataNode"):
        gid = dn.get("GraphId")
        if not gid:
            continue
        node = Node(
            graph_id=gid,
            label=dn.get("TextLabel"),
            node_type=dn.get("Type"),
            group_ref=dn.get("GroupRef"),
        )
        for xref in iter_children(dn, "Xref"):
            node.xref_db = xref.get("Database") or xref.get("dataSource")
            node.xref_id = xref.get("ID") or xref.get("identifier")
        for gr in iter_children(dn, "Graphics"):
            try:
                node.width = float(gr.get("Width", node.width))
                node.height = float(gr.get("Height", node.height))
            except (TypeError, ValueError):
                pass
        p.nodes[gid] = node
        if node.group_ref:
            group_members.setdefault(node.group_ref, []).append(gid)

    # --- Group（GraphId -> GroupId + members） ---
    for g in iter_descendants(root, "Group"):
        ggid = g.get("GraphId")
        group_id = g.get("GroupId")
        if ggid:
            p.groups[ggid] = {
                "group_id": group_id,
                "members": group_members.get(group_id, []),
            }

    # --- Anchor（先に集める：Position と 親interaction を保持） ---
    for itx in iter_descendants(root, "Interaction"):
        iid = itx.get("GraphId")
        for anchor in iter_descendants(itx, "Anchor"):
            aid = anchor.get("GraphId")
            if not aid:
                continue
            try:
                pos = float(anchor.get("Position", "0.5"))
            except (TypeError, ValueError):
                pos = 0.5
            p.anchors[aid] = Anchor(graph_id=aid, interaction_id=iid, position=pos)

    # --- Interaction を解釈 ---
    anchor_ids = p.anchor_ids
    for itx in iter_descendants(root, "Interaction"):
        iid = itx.get("GraphId")
        points = list(iter_descendants(itx, "Point"))
        if len(points) < 2:
            continue

        start_ref = points[0].get("GraphRef")
        end_ref = points[-1].get("GraphRef")
        arrow = None
        for pt in points:
            if pt.get("ArrowHead"):
                arrow = pt.get("ArrowHead")

        p.interactions.append(
            Interaction(graph_id=iid, start_ref=start_ref,
                        end_ref=end_ref, arrowhead=arrow)
        )

        endpoints = [start_ref, end_ref]
        # ルール3: 端点のいずれかが Anchor → エッジ化しない
        if any(r in anchor_ids for r in endpoints if r):
            p.skipped.append((iid, endpoints, "anchor参照のため除外"))
            continue
        if not start_ref or not end_ref:
            p.skipped.append((iid, endpoints, "GraphRef欠落のため除外"))
            continue

        p.edges.append(
            Edge(source=start_ref, target=end_ref,
                 interaction_id=iid, arrowhead=arrow)
        )

    return p


# --------------------------------------------------------------------------- #
# 出力
# --------------------------------------------------------------------------- #
def label_of(p: Parsed, graph_id: str) -> str:
    node = p.nodes.get(graph_id)
    if node and node.label:
        return node.label
    if graph_id in p.groups:
        return f"(group:{p.groups[graph_id]['group_id']})"
    return graph_id


def write_edge_list(p: Parsed, out):
    w = csv.writer(out, delimiter="\t")
    w.writerow(["source_id", "target_id", "source_label", "target_label",
                "interaction_id", "arrowhead"])
    for e in p.edges:
        w.writerow([e.source, e.target, label_of(p, e.source),
                    label_of(p, e.target), e.interaction_id or "", e.arrowhead or ""])


def write_node_list(p: Parsed, out):
    """レイアウト後に x,y が入っていれば一緒に出す。"""
    w = csv.writer(out, delimiter="\t")
    w.writerow(["GraphId", "label", "type", "xref_db", "xref_id", "x", "y"])
    for n in p.nodes.values():
        w.writerow([n.graph_id, n.label or "", n.node_type or "",
                    n.xref_db or "", n.xref_id or "",
                    "" if n.x is None else round(n.x, 2),
                    "" if n.y is None else round(n.y, 2)])


def build_networkx(p: Parsed, use_labels: bool):
    import networkx as nx
    g = nx.DiGraph()
    for gid, n in p.nodes.items():
        attrs = dict(label=n.label or gid, type=n.node_type or "",
                     xref_db=n.xref_db or "", xref_id=n.xref_id or "")
        if n.x is not None and n.y is not None:
            attrs["x"], attrs["y"] = float(n.x), float(n.y)
        g.add_node(gid, **attrs)
    for e in p.edges:
        g.add_edge(e.source, e.target,
                   interaction_id=e.interaction_id or "", arrowhead=e.arrowhead or "")
    if use_labels:
        seen, safe = {}, {}
        for gid in g.nodes:
            lab = label_of(p, gid)
            safe[gid] = f"{lab} [{gid}]" if lab in seen else lab
            seen[lab] = gid
        g = nx.relabel_nodes(g, safe)
    return g


def main(argv=None):
    ap = argparse.ArgumentParser(description="GPML を ノード/エッジ ネットワークに変換")
    ap.add_argument("input")
    ap.add_argument("-o", "--output", help="エッジリスト(TSV)の出力先")
    ap.add_argument("--labels", action="store_true")
    ap.add_argument("--graphml")
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args(argv)

    p = parse_gpml(args.input)

    if args.output:
        with open(args.output, "w", newline="", encoding="utf-8") as f:
            write_edge_list(p, f)
    else:
        write_edge_list(p, sys.stdout)

    if args.graphml:
        import networkx as nx
        nx.write_graphml(build_networkx(p, args.labels), args.graphml, encoding="utf-8")

    if not args.quiet:
        print("", file=sys.stderr)
        print(f"# nodes(DataNode): {len(p.nodes)}", file=sys.stderr)
        print(f"# anchors        : {len(p.anchors)}", file=sys.stderr)
        print(f"# edges          : {len(p.edges)}", file=sys.stderr)
        print(f"# skipped        : {len(p.skipped)}", file=sys.stderr)
        for iid, eps, why in p.skipped:
            print(f"    - {iid}: {eps} … {why}", file=sys.stderr)


if __name__ == "__main__":
    main()
