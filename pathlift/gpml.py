"""GPML(2013a/2021) の入出力アダプタ。XMLの詳細をここに閉じ込める。

stdlib の ElementTree を使い、default namespace を登録して prefix 無しで書き戻す。
DataNode は Pathway の直接の子なので、展開時のクローン挿入も root に対して行う。
"""
from __future__ import annotations

import copy
import random
import xml.etree.ElementTree as ET

from .models import GeneProductNode, ResolveResult


class GpmlDocument:
    def __init__(self, tree, root, ns):
        self.tree = tree
        self.root = root
        self.ns = ns
        # 既存の全 GraphId/GroupId を集め、新規発番の衝突回避に使う
        self._used_ids = set()
        for e in root.iter():
            for a in ("GraphId", "GroupId"):
                v = e.get(a)
                if v:
                    self._used_ids.add(v)

    def _q(self, tag: str) -> str:
        return f"{{{self.ns}}}{tag}" if self.ns else tag

    def _new_graph_id(self) -> str:
        """PathVisioのDataNode流儀 [a-f][0-9a-f]{4} の一意な GraphId を発番する。"""
        while True:
            gid = random.choice("abcdef") + "".join(
                random.choice("0123456789abcdef") for _ in range(4))
            if gid not in self._used_ids:
                self._used_ids.add(gid)
                return gid

    @classmethod
    def read(cls, path: str) -> "GpmlDocument":
        tree = ET.parse(path)
        root = tree.getroot()
        ns = root.tag[1:].split("}")[0] if root.tag.startswith("{") else ""
        if ns:
            ET.register_namespace("", ns)  # 書き戻しで prefix を付けない
        return cls(tree, root, ns)

    def gene_product_nodes(self):
        """(element, GeneProductNode) のリストを返す(materialize: 展開中の挿入と干渉しない)。"""
        out = []
        for el in list(self.root):
            if el.tag != self._q("DataNode") or el.get("Type") != "GeneProduct":
                continue
            xref = el.find(self._q("Xref"))
            g = el.find(self._q("Graphics"))

            def fnum(attr):
                v = g.get(attr) if g is not None else None
                return float(v) if v not in (None, "") else None

            out.append((el, GeneProductNode(
                graph_id=el.get("GraphId"), label=el.get("TextLabel"),
                database=xref.get("Database") if xref is not None else None,
                xref_id=xref.get("ID") if xref is not None else None,
                center_x=fnum("CenterX"), center_y=fnum("CenterY"),
                width=fnum("Width"), height=fnum("Height"),
            )))
        return out

    # ---- mutation ----
    def _set_xref(self, el, database: str, ident: str) -> None:
        xref = el.find(self._q("Xref"))
        if xref is None:
            xref = ET.SubElement(el, self._q("Xref"))
        xref.set("Database", database)
        xref.set("ID", ident)

    def _add_comment(self, el, text: str) -> None:
        c = ET.Element(self._q("Comment"))   # Comment は Graphics/Xref より前
        c.set("Source", "PathLift")
        c.text = text
        el.insert(0, c)

    def _nudge(self, el, dx: float, dy: float) -> None:
        g = el.find(self._q("Graphics"))
        if g is None:
            return
        for axis, d in (("CenterX", dx), ("CenterY", dy)):
            v = g.get(axis)
            if v not in (None, ""):
                g.set(axis, str(float(v) + d))

    def _apply(self, el, cand, out_namespace: str) -> None:
        self._set_xref(el, out_namespace, cand.gene_id)
        routes = ",".join(sorted(r.value for r in cand.routes))
        tx = ",".join(cand.transcript_ids())
        self._add_comment(el, f"candidate gene={cand.gene_id}; transcripts={tx}; routes={routes}")

    def expand(self, el, result: ResolveResult, out_namespace: str, nudge=(24, 16)) -> int:
        """候補gene数ぶんにノードを展開。先頭は元ノード(GraphId/位置維持)、残りはクローン+ずらし。"""
        cands = sorted(result.candidates, key=lambda c: c.gene_id)
        clones = [copy.deepcopy(el) for _ in cands[1:]]   # コメント付与前(pristine)に複製
        self._apply(el, cands[0], out_namespace)
        pos = list(self.root).index(el)
        for i, (clone, cand) in enumerate(zip(clones, cands[1:]), start=1):
            clone.set("GraphId", self._new_graph_id())
            self._apply(clone, cand, out_namespace)
            self._nudge(clone, nudge[0] * i, nudge[1] * i)
            self.root.insert(pos + i, clone)
        return len(cands)

    def mark_unmapped(self, el, note: str) -> None:
        self._add_comment(el, f"unmapped: {note}")

    def write(self, path: str) -> None:
        self.tree.write(path, xml_declaration=True, encoding="UTF-8")
