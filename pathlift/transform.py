"""②パスウェイ変換器(オーケストレータ)。

源GPMLを走査し、各 GeneProduct を③でresolveして候補gene数ぶんにノード展開し、
出力GPMLを書く。発現(④)は別段階。configの配布役も兼ねる(③④はconfigを直接読まない)。
"""
from __future__ import annotations

from .gpml import GpmlDocument


class PathwayTransformer:
    def __init__(self, resolver, out_namespace: str, nudge=(24, 16)):
        self.resolver = resolver
        self.out_namespace = out_namespace
        self.nudge = nudge

    def run(self, in_gpml: str, out_gpml: str) -> dict:
        doc = GpmlDocument.read(in_gpml)
        nodes = doc.gene_product_nodes()
        stats = {
            "gene_product": len(nodes), "matched": 0, "unmapped": 0,
            "candidate_genes": 0, "nodes_added": 0, "label_dependent": 0,
            "unmapped_list": []
        }
        for el, node in nodes:
            db = (node.database or "").upper()
            if db not in ("ENTREZ GENE", "HGNC"):
                stats["label_dependent"] += 1   # 記号導出がTextLabel依存になるノード
            res = self.resolver.resolve(node)
            if res.is_matched:
                doc.expand(el, res, self.out_namespace, self.nudge)
                stats["matched"] += 1
                stats["candidate_genes"] += res.gene_count
                stats["nodes_added"] += res.gene_count - 1
            else:
                sym = res.symbol or node.label or "?"
                doc.mark_unmapped(el, f"{sym} ({res.note or 'unmapped'})")
                stats["unmapped"] += 1
                stats["unmapped_list"].append(sym)
        stats["txgene_unrecognized"] = len(self.resolver.txgene.unrecognized)
        doc.write(out_gpml)
        return stats
