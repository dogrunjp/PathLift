"""GTF由来の transcript <-> gene 対応。

③オーソログ解決器(候補をgene単位に畳み込む)と④発現リンカ(発現の突合)で
共有するため、独立モジュールに置く。GTFが無ければIDパターンで畳み込む。
"""
from __future__ import annotations

import re

_P_SUFFIX = re.compile(r"\.p\d+$")          # ProteinID の .pN を落として transcript に
_AUG_TX = re.compile(r"^(g\d+)\.t\d+$")      # Augustus: g123.t1 -> g123
_SILK_TX = re.compile(r"^(KWMTBOMO\d+)")     # SilkBase: KWMTBOMO00001.mrna1 -> KWMTBOMO00001
_GTF_GENE = re.compile(r'gene_id "([^"]+)"')
_GTF_TX = re.compile(r'transcript_id "([^"]+)"')


class TranscriptGeneMap:
    def __init__(self, tx2gene: dict[str, str] | None = None):
        self.tx2gene = dict(tx2gene or {})
        self.unrecognized: set[str] = set()   # GTF/パターンに当たらず畳めなかったID

    @classmethod
    def from_gtf(cls, path: str | None) -> "TranscriptGeneMap":
        m: dict[str, str] = {}
        if path:
            with open(path, encoding="utf-8") as f:
                for line in f:
                    if line.startswith("#"):
                        continue
                    c = line.split("\t")
                    if len(c) < 9 or c[2] != "transcript":
                        continue
                    g, t = _GTF_GENE.search(c[8]), _GTF_TX.search(c[8])
                    if g and t:
                        m[t.group(1)] = g.group(1)
        return cls(m)

    def gene_of(self, protein_id: str) -> str:
        """ProteinID -> gene。.pN を落とし、GTF優先、無ければIDパターン。"""
        tx = _P_SUFFIX.sub("", protein_id)
        if tx in self.tx2gene:
            return self.tx2gene[tx]
        ms = _SILK_TX.match(tx)                  # SilkBase: KWMTBOMO00001.mrna1 -> KWMTBOMO00001
        if ms:
            return ms.group(1)
        if tx.startswith("MSTRG."):
            parts = tx.split(".")
            return ".".join(parts[:2]) if len(parts) >= 2 else tx
        m = _AUG_TX.match(tx)
        if m:
            return m.group(1)
        self.unrecognized.add(protein_id)   # GTF/既知パターンに非該当=畳めず素通り
        return tx
