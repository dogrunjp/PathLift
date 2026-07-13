# PathLift 実行時フロー・分岐仕様（runtime_flow_and_branching）

> ランタイムの処理フローと、recipe/実行時データによる**分岐**（`routes.compute`・`reference_fasta`有無等）。
> C4のL2/L3が構造（何が存在し何をするか）を示すのに対し、本ファイルは「設定・実行時データに
> よってどの経路が発火するか」を示す。旧ファイル名 `conversion_flow.md`（2026-07-11改名）。
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
    W --> STATS[stats:<br/>matched/unmapped/候補数/unmapped_list]

    STATS --> CCHK{"unmapped_list あり<br/>かつ routes.compute?"}:::config
    CCHK -->|no| OUT[出力 GPML]

    subgraph RESCUE["⑤ 自動キュレーション（BLASTレスキュー、compute ルートの実体）"]
        FA[query_fasta.py<br/>UniProt REST → source種FASTA]:::external --> RCHK{"reference_fasta<br/>指定あり?"}:::config
        RCHK -->|yes| BLL[ローカル blastp -subject]:::external
        RCHK -->|no| BLR[remote blastp -db nr<br/>+ taxidで絞込]:::external
        BLL --> FIL[RBH_plus由来の固定フィルタ<br/>length&gt;=50 / qcov&gt;=0.6 / scov&gt;=0.6 等]:::auto
        BLR --> FIL
        FIL --> GEN["auto_curation.py<br/>overrides/unmapped 生成<br/>(*_auto_curation.yaml)"]:::auto
    end

    CCHK -->|yes| FA
    GEN --> RELOAD["curationを差し替えて<br/>①③②を再実行(2周目)"]:::auto
    RELOAD --> OUT

    OUT -.-> QPX[QPX notebook（PathLift外）<br/>発現で選別・可視化]

    classDef auto      fill:#d1fae5,stroke:#059669,color:#065f46
    classDef config    fill:#e0f2fe,stroke:#0284c7,color:#075985
    classDef external  fill:#dbeafe,stroke:#2563eb,color:#1e40af
```

> `routes.compute=false`（既定）なら`CCHK`は`no`に固定され、⑤は一切発火しない。
> `reference_fasta`は`RCHK`の分岐にのみ関わり、`compute`ルートのon/off自体は左右しない。


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
    RES5["⑤自動キュレーションが生成した<br/>override も同じ経路で合流<br/>(Route.OVERRIDE。Route.COMPUTEは未使用)"] -.->|2周目のcurationとして| OV
    OV --> CAND{候補あり?}
    CAND -->|yes| RESULT[候補集合 + provenance]
    CAND -->|no| MU2[unmapped: no hit]
```


> ⑤（BLASTレスキュー）は resolve() の内部処理ではなく、CLI（`cli.py`）が stats 確認後に
> curation を差し替えて①③②全体をもう一周させる形で実装されている（上記1.参照）。
> resolve() 自身にとっては「override が増えた2周目」でしかなく、compute専用の分岐は無い。

## 3. フローに表れる設計上の要点

- **検証は前段で完結**（`load_recipe`）。ランタイムはパス探索も判定もしない。
- **解決は全候補・和集合**。絞らない（recall 優先）。選別は QPX notebook（PathLift 外）。
- **記号導出は IDタイプ依存**で、非 Entrez/HGNC は TextLabel に落ちる（`PoC知見と設計判断.md` E章）。
- **txgene は GTF/パターンの2モード**で、選択はアセット依存（同 F章）。
- **MISS の主因はパラログ×表カーディナリティ**。`compute` ルート（⑤自動キュレーション、2026-07実装）が、`HITS`ではなくstats確認後の**2周目**としてrecallを回収する位置づけ（同 C-3）。フィルタはRBH_plus由来の固定ロジックで、recipeでは`evalue`のみ調整可能（`pathway-liftover-spec.md` §8、`recipe.schema.md`）。
- **`routes.compute`はunmapped発生後の分岐そのもの**（上記1.の`CCHK`）であり、`reference_fasta`有無は⑤内部のローカル/リモートblastp分岐（`RCHK`）にのみ関わる。両者を混同しないこと。
