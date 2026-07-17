"""③オーソログ解決器。

源ノード(GeneProductNode)を受け、候補集合(ResolveResult)を返す。絞らず全候補を出し、
provenance(どのルートで当たったか)を残す。選別は後段(④発現)で行う方針。

解決ルート(複合・和集合):
  - symbol  : 主。Entrez->公式記号(gene_info) / HGNCはID直 で記号を作り、表の記号列で引く。
  - pid     : 精密。源ID->ENSP(idmap)で表のpid列を引く。idmap未指定なら不活性。
  - override: curationの手動対応(最優先で候補に追加)。
  - compute : blastp計算。将来用の差し込み口(PoC未実装)。
curation.unmapped に載る源は解決を試みず確定的に unmapped。

本体 resolve() は組み立て済みデータで動く(単体テスト容易)。ファイル読込は from_config に集約。
recipe/サイドカーの検証は recipe.py(pydantic) 側の責務。
"""
from __future__ import annotations

import csv
from collections import defaultdict

from .models import GeneProductNode, ResolveResult, Route
from .txgene import TranscriptGeneMap


# ---- ローダ(from_config から使う) ----

def load_gene_info(path: str | None, taxid: str = "9606") -> dict[str, str]:
    """GeneID -> 公式記号。GeneIDは一意キーなので衝突しない(synonymは使わない)。"""
    gid2sym: dict[str, str] = {}
    if not path:
        return gid2sym
    with open(path, encoding="utf-8") as f:
        for line in f:
            if line.startswith("#"):
                continue
            c = line.rstrip("\n").split("\t")
            if len(c) < 3 or (taxid and c[0] != str(taxid)):
                continue
            gid, sym = c[1], c[2]
            if sym and sym != "-":
                gid2sym[gid] = sym
    return gid2sym


def load_funflow_index(path: str, columns: dict) -> tuple[dict, dict]:
    """FunFlow を1パスで symbol_index / pid_index 化(行は保持しない)。"""
    target_col = columns["target_id"]
    sym_col = columns["source_symbol"]
    pid_col = columns.get("source_pid")
    symbol_index: dict[str, set] = defaultdict(set)
    pid_index: dict[str, set] = defaultdict(set)
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f, delimiter="\t")
        for r in reader:
            tgt = (r.get(target_col) or "").strip()
            if not tgt:
                continue
            sym = (r.get(sym_col) or "").strip()
            if sym:
                symbol_index[sym.upper()].add(tgt)
            if pid_col:
                pid = (r.get(pid_col) or "").strip()
                if pid:
                    pid_index[pid].add(tgt)
                    pid_index[pid.split(".")[0]].add(tgt)
    return dict(symbol_index), dict(pid_index)


def load_idmap(path: str | None) -> dict[str, str]:
    idmap: dict[str, str] = {}
    if path:
        with open(path, encoding="utf-8") as f:
            for line in f:
                a = line.rstrip("\n").split("\t")
                if len(a) >= 2 and a[0] and a[1]:
                    idmap[a[0]] = a[1]
    return idmap


def build_curation(curation: dict | None) -> tuple[dict, dict]:
    """curation(辞書) -> (override_index, unmapped_index)。源キーは大文字で正規化。"""
    override_index: dict[str, list] = defaultdict(list)
    unmapped_index: dict[str, dict] = {}
    if curation:
        for ov in curation.get("overrides") or []:
            src = (ov.get("source") or "").strip()
            tgt = (ov.get("target") or "").strip()
            if src and tgt:
                target_database = (ov.get("target_database") or "").strip() or None
                override_index[src.upper()].append(
                    (tgt, ov.get("note"), ov.get("target_label"), target_database)
                )
        for um in curation.get("unmapped") or []:
            src = (um.get("source") or "").strip()
            if src:
                unmapped_index[src.upper()] = {
                    "reason": um.get("reason"),
                    "note": um.get("note"),
                }
    return dict(override_index), unmapped_index


def _enabled_routes(routes: dict | None) -> set:
    if not routes:
        return {Route.SYMBOL}
    out = set()
    if routes.get("symbol", True):
        out.add(Route.SYMBOL)
    if routes.get("pid"):
        out.add(Route.PID)
    if routes.get("compute"):
        out.add(Route.COMPUTE)
    return out or {Route.SYMBOL}


# ---- 解決器本体 ----

class OrthologResolver:
    def __init__(self, *, symbol_index, pid_index, gid2sym, txgene: TranscriptGeneMap,
                 override_index=None, unmapped_index=None,
                 enabled_routes=(Route.SYMBOL,), idmap=None, policy: str = "augment"):
        self.symbol_index = symbol_index
        self.pid_index = pid_index
        self.gid2sym = gid2sym
        self.txgene = txgene
        self.override_index = override_index or {}
        self.unmapped_index = unmapped_index or {}
        self.enabled_routes = set(enabled_routes)
        self.idmap = idmap or {}
        self.policy = policy

    @classmethod
    def from_config(cls, *, funflow_path, columns, gene_info_path=None,
                    gene_info_taxid="9606", gtf_path=None, curation=None,
                    routes=None, idmap_path=None, policy="augment"):
        symbol_index, pid_index = load_funflow_index(funflow_path, columns)
        gid2sym = load_gene_info(gene_info_path, gene_info_taxid)
        txgene = TranscriptGeneMap.from_gtf(gtf_path)
        override_index, unmapped_index = build_curation(curation)
        return cls(
            symbol_index=symbol_index, pid_index=pid_index, gid2sym=gid2sym,
            txgene=txgene, override_index=override_index, unmapped_index=unmapped_index,
            enabled_routes=_enabled_routes(routes), idmap=load_idmap(idmap_path),
            policy=policy,
        )

    def _symbol(self, node: GeneProductNode) -> str | None:
        """源ノードの正規化記号。Entrez->公式記号、HGNCはID直、他はTextLabel。"""
        db = (node.database or "").upper()
        nid = (node.xref_id or "").strip()
        label = (node.label or "").strip()
        if db == "ENTREZ GENE" and nid in self.gid2sym:
            return self.gid2sym[nid]
        if db == "HGNC" and nid and not nid[:1].isdigit() and not nid.upper().startswith("HGNC:"):
            return nid
        return label or None

    def resolve(self, node: GeneProductNode) -> ResolveResult:
        res = ResolveResult(source=node)
        sym = self._symbol(node)
        res.symbol = sym
        keys = {k.upper() for k in (sym, node.xref_id, node.label) if k}

        # curation.unmapped は最優先で短絡
        for key in sorted(keys):
            unmapped_metadata = self.unmapped_index.get(key)
            if unmapped_metadata is None:
                continue
            res.mark_unmapped(
                note=unmapped_metadata.get("note") or "curation: unmapped",
                reason=unmapped_metadata.get("reason"),
            )
            return res

        # ルートごとに protein を集め、route を記録(和集合)
        hits: dict[str, set] = defaultdict(set)
        if Route.SYMBOL in self.enabled_routes and sym:
            for p in self.symbol_index.get(sym.upper(), ()):
                hits[p].add(Route.SYMBOL)
        if Route.PID in self.enabled_routes and self.idmap and node.xref_id:
            ensp = self.idmap.get(node.xref_id)
            if ensp:
                tgts = self.pid_index.get(ensp) or self.pid_index.get(ensp.split(".")[0])
                for p in (tgts or ()):
                    hits[p].add(Route.PID)
        # Route.COMPUTE は将来ここに差し込む(policy=augment 時の blastp)

        # protein を gene 単位に畳んで候補化
        for protein, routes in hits.items():
            res.add_candidate(self.txgene.gene_of(protein), [protein], routes)

        # curation override(手動で候補を追加/固定)
        for key in keys:
            for target, _note, target_label, target_database in self.override_index.get(key, ()):
                res.add_candidate(
                    target,
                    [],
                    [Route.OVERRIDE],
                    label=target_label,
                    database=target_database,
                )

        if not res.candidates:
            res.mark_unmapped("no hit")
        return res
