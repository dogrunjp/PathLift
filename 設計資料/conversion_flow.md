# PathLift 変換フロー（conversion_flow）

> ランタイムの処理フロー。PoC で確認した実際の流れに合わせてある。
> 色は `開発管理/mermaid_color_legend.md` の凡例を適用する。
> 構成（コンポーネント）は `c4_model.md`、根拠は `PoC知見と設計判断.md`。

## 1. 全体フロー

```mermaid
flowchart TD
    R[recipe.yaml + curation.yaml] --> L[①load_recipe<br/>検証・パス解決]
    L -->|検証NG| E[RecipeError<br/>ランタイムに入れない]
    L -->|config| B[from_config<br/>解決器を組み立て]

    subgraph build[解決器の組み立て]
        B --> T[対応表 → symbol_index / pid_index]
        B --> GI[gene_info → GeneID→記号]
        B --> TX[txgene<br/>GTF or パターン]
        B --> CU[curation → override / unmapped]
    end

    SRC[source GPML] --> RD[②read<br/>GeneProduct を列挙]
    build --> LOOP
    RD --> LOOP{各 GeneProduct ノード}

    LOOP --> RES[③resolve]
    RES --> MATCH{候補あり?}
    MATCH -->|yes| EXP[②expand<br/>先頭=元ノード再利用<br/>残り=クローン+新GraphId+位置ずらし]
    MATCH -->|no| UNM[mark_unmapped<br/>unmapped: 記号 no hit]

    EXP --> LOOP
    UNM --> LOOP

    LOOP -->|全ノード処理後| W[②write<br/>lift済み GPML + stats]
    W --> OUT[出力 GPML]
    W --> STATS[stats:<br/>matched/unmapped/候補数]

    OUT -.-> QPX[QPX notebook（PathLift外）<br/>発現で選別・可視化]
```


## 2. resolve の内部（③）

```mermaid
flowchart TD
    N[GeneProduct ノード] --> SYM[記号導出<br/>Entrez→gene_info / HGNC直 / 他→TextLabel]
    SYM --> KEYS[キー集合: 記号 / Xref ID / TextLabel]

    KEYS --> UCHK{curation.unmapped?}
    UCHK -->|該当| MU[確定 unmapped]
    UCHK -->|否| ROUTES

    subgraph ROUTES[有効ルートを和集合]
        RS[symbol: 記号列を引く]
        RP[pid: ENSP で pid列を引く]
    end
    ROUTES --> HITS[target蛋白の集合<br/>+ どのルートで当たったか]
    HITS --> COL[txgene で gene 単位に畳む]
    COL --> OV[curation override を追加]
    OV --> CAND{候補あり?}
    CAND -->|yes| RESULT[候補集合 + provenance]
    CAND -->|no| MU2[unmapped: no hit]
```

## 3. フローに表れる設計上の要点

- **検証は前段で完結**（`load_recipe`）。ランタイムはパス探索も判定もしない。
- **解決は全候補・和集合**。絞らない（recall 優先）。選別は QPX notebook（PathLift 外）。
- **記号導出は IDタイプ依存**で、非 Entrez/HGNC は TextLabel に落ちる（`PoC知見と設計判断.md` E章）。
- **txgene は GTF/パターンの2モード**で、選択はアセット依存（同 F章）。
- **MISS の主因はパラログ×表カーディナリティ**。`compute` ルート（未実装）がこのフローの `HITS` を補完して recall を回収する位置づけ（同 C-3）。
