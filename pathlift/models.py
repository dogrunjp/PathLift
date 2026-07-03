"""PathLift のドメインモデル(パイプラインを流れるデータ)。

外部入力(recipe/サイドカー)の検証は recipe.py(pydantic)が担当する。
ここは内部で受け渡す純粋なデータ構造(dataclass)に徹する。

主な流れ:
    GeneProductNode  --(③オーソログ解決器)-->  ResolveResult
                                                 └ candidates: [Candidate]
                                                      └ transcripts: [TranscriptHit]  (④が発現を充填)
    ResolveResult    --(②変換器)-->  候補gene数ぶんの出力ノードに展開
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

__all__ = [
    "Route", "ResolveStatus",
    "GeneProductNode", "TranscriptHit", "Candidate", "ResolveResult",
]


class Route(str, Enum):
    """候補がどの解決ルートで当たったか(provenance)。複数同時に成立しうる。"""
    SYMBOL = "symbol"      # 主ルート: 記号ジョイン(再現率重視)
    PID = "pid"            # 精密ルート: ENSP経由(要 idmap)
    OVERRIDE = "override"  # curationの手動対応
    COMPUTE = "compute"    # blastp計算(将来)


class ResolveStatus(str, Enum):
    MATCHED = "matched"
    UNMAPPED = "unmapped"


@dataclass
class GeneProductNode:
    """源GPMLの GeneProduct ノード(Type=GeneProduct)。"""
    graph_id: str
    label: str | None = None        # TextLabel
    database: str | None = None     # Xref/@Database (Entrez Gene / HGNC / Enzyme Nomenclature ...)
    xref_id: str | None = None      # Xref/@ID
    # 配置: ノード展開時のずらしに使う(Graphics由来)
    center_x: float | None = None
    center_y: float | None = None
    width: float | None = None
    height: float | None = None


@dataclass
class TranscriptHit:
    """候補を裏付ける transcript/protein。どれが正解かは後で発現で検証する。"""
    transcript_id: str                    # 例: MSTRG.100.1.p1 (FunFlowのProteinID)
    tpm: dict[str, float] | None = None   # sample -> TPM。④発現リンカが後で充填


@dataclass
class Candidate:
    """源ノードに対する候補オーソログ(対象種の assembly gene)。"""
    gene_id: str                                          # assembly gene (MSTRG.x / g####) = 出力XREF
    transcripts: list[TranscriptHit] = field(default_factory=list)
    routes: set[Route] = field(default_factory=set)       # 当たったルート(複数可)
    label: str | None = None

    def transcript_ids(self) -> list[str]:
        return [t.transcript_id for t in self.transcripts]

    def add_transcripts(self, ids) -> None:
        """transcript_id(文字列)を重複なく追加。"""
        seen = {t.transcript_id for t in self.transcripts}
        for tid in ids:
            if tid not in seen:
                self.transcripts.append(TranscriptHit(tid))
                seen.add(tid)


@dataclass
class ResolveResult:
    """1つの源ノードに対する解決結果(候補集合)。絞らず全候補を持つ。"""
    source: GeneProductNode
    symbol: str | None = None                 # 解決に使った正規化記号
    candidates: list[Candidate] = field(default_factory=list)
    status: ResolveStatus = ResolveStatus.UNMAPPED
    note: str | None = None                   # unmapped理由・備考

    @property
    def is_matched(self) -> bool:
        return self.status is ResolveStatus.MATCHED and bool(self.candidates)

    @property
    def gene_count(self) -> int:
        return len(self.candidates)

    @property
    def transcript_count(self) -> int:
        return sum(len(c.transcripts) for c in self.candidates)

    def add_candidate(self, gene_id: str, transcripts=(), routes=(), label=None) -> Candidate:
        """gene_id が既出なら統合(transcript和集合・route和集合)、無ければ新規。
        いずれも status を MATCHED にする。routes は Route か文字列を受ける。"""
        rs = {r if isinstance(r, Route) else Route(r) for r in routes}
        for c in self.candidates:
            if c.gene_id == gene_id:
                c.add_transcripts(transcripts)
                c.routes |= rs
                if label and not c.label:
                    c.label = label
                self.status = ResolveStatus.MATCHED
                return c
        c = Candidate(gene_id=gene_id, routes=rs, label=label)
        c.add_transcripts(transcripts)
        self.candidates.append(c)
        self.status = ResolveStatus.MATCHED
        return c

    def mark_unmapped(self, note: str | None = None) -> None:
        self.status = ResolveStatus.UNMAPPED
        if note:
            self.note = note
