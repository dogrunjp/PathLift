# liftover recipe スキーマ仕様

`schema_version: 2`

> v2変更点(PoC spike反映): 主ルートをsymbolジョインに、`gene_info`でEntrez→公式記号を正規化、GTFを③④共有に、出力XREFをPoC暫定でassembly geneに（Entrez正規化は後段enrichmentで保留）。

## 1. 目的と位置づけ

recipeは、**人手・アドホックな発見と判定の「結果」を固定し、決定的なランタイムへ渡す境界アーティファクト**である。

- 書く人: curator（研究者）。表やGTFを探し、列対応を確認し、ルートや手動判定を決めた結果をここに落とす。
- 読む人: ①レシピローダ → 検証済みconfigを②③④へ。
- 原則: **ランタイムはパス探索も存在判定もしない**。必要なものは全てrecipeに書かれている。
- 形式: YAML。recipe本体と、手動判定を載せるcurationサイドカーの2ファイル構成。

## 2. ファイルと命名

| 種別 | パス例 | 役割 |
|---|---|---|
| 本体 | `configs/WP5609_Ac.yaml` | リソース・列対応・ルート・ポリシー |
| サイドカー | `configs/WP5609_Ac.curation.yaml` | 手動判定の結果（override / unmapped） |

- recipe内の相対パスは、**recipeファイルのあるディレクトリを基準**に解決する。

## 3. 本体スキーマ

### `pathway`（必須）

| フィールド | 型 | 必須 | 制約 |
|---|---|---|---|
| `source_gpml` | path | 必須 | 存在すること |

- 源IDの名前空間は**ノードごとに`Xref/@Database`から読む**（単一値で持たない）。WP5609実測では `Entrez Gene` / `HGNC` / `Enzyme Nomenclature` が混在。

### `target`（必須）

| フィールド | 型 | 必須 | 既定 | 制約 |
|---|---|---|---|---|
| `taxid` | int | 必須 | — | NCBI Taxonomy ID |
| `output_id_namespace` | string | 必須 | `assembly` | 出力XREFのDataSource。PoCは`assembly`暫定。Entrezは後段enrichmentで保留 |
| `transcript_gene_gtf` | path | 任意 | — | StringTie merged GTF。tx↔gene対応。**③(候補畳み込み)と④(発現)で共有**。未指定ならIDパターンで畳み込み |

### `ortholog_resolver`（必須）

| フィールド | 型 | 必須 | 既定 | 制約 |
|---|---|---|---|---|
| `policy` | enum | 必須 | `augment` | `strict`（表/記号に無い＝オーソログ無し）/ `augment`（外れは計算/curationで補う） |
| `provided_table.path` | path | 必須 | — | 存在すること |
| `provided_table.format` | enum | — | `tsv` | `tsv` / `csv` |
| `provided_table.columns.target_id` | string | 必須 | — | 対象種(ミツバチ)の列。表ヘッダに実在 |
| `provided_table.columns.source_symbol` | string | 必須 | — | **主ルートの結合キー**（ヒト記号列）。表ヘッダに実在 |
| `provided_table.columns.source_pid` | string | 任意 | — | 精密ルート用（ENSP列）。表ヘッダに実在 |
| `gene_info.path` | path | 任意 | — | NCBI gene_info。Entrez→公式記号の正規化に使用 |
| `gene_info.taxid` | int | — | `9606` | 源(ヒト)の tax_id |
| `routes.symbol` | bool | — | `true` | 主ルート（記号、再現率重視） |
| `routes.pid` | bool | — | `false` | 精密ルート。`true`なら`idmap`必須 |
| `routes.compute` | bool | — | `false` | blastp計算。PoCは保留（curationで代替） |
| `idmap` | path | 条件付 | — | `source_id<TAB>ENSP`。`routes.pid=true`で必須 |
| `compute_fallback.blastp` | object | 任意 | — | `routes.compute=true`時のみ。`{evalue, identity_min, coverage_min}` |

- 解決器は**候補集合**を返す: `[{gene, transcripts[], routes}]` ＋ status。各候補はどのルートで当たったか(provenance)を持つ。
- 記号正規化: Entrezノードは`gene_info`の`GeneID→公式記号`（一意キーなので衝突しない）。HGNCノードはIDがそのまま公式記号。**synonym経由の正規化はしない**（別遺伝子と衝突するため）。
- 候補のgene単位化: `target.transcript_gene_gtf`（無ければIDパターン）でProteinID→transcript→geneに畳み込む。

### `expression`（任意・Phase2）

| フィールド | 型 | 必須 | 制約 |
|---|---|---|---|
| `tpm` | path | — | 存在すること |

- GTFは`target.transcript_gene_gtf`を共有（ここには書かない）。
- セクション省略時は④発現リンカを起動しない（候補表示まで）。

### `curation_file`（任意）

| フィールド | 型 | 既定 |
|---|---|---|
| `curation_file` | path | `<本体名>.curation.yaml` |

## 4. curationサイドカースキーマ

手動判定の**結果**を残す層。解決の優先は **override > 表/記号ルート > 計算**。

```yaml
overrides:        # 候補を強制的に追加/固定する
  - source: RPS6KA3          # 源(正規化後symbol または Xref ID)
    target: MSTRG.xxxx       # assembly gene
    note: "兄弟RPS6KA1/2と同座位に手動対応"
unmapped:         # 解決不能として確定保持(解決を試みない)
  - source: PPARGC1A
    note: "ミツバチに明確なオーソログ無し"
```

| フィールド | 型 | 必須 | 制約 |
|---|---|---|---|
| `overrides[].source` | string | 必須 | 正規化後symbol または 源Xref ID |
| `overrides[].target` | string | 必須 | `output_id_namespace`に整合（assembly gene） |
| `overrides[].note` | string | 任意 | 判定根拠（再現と監査のため推奨） |
| `unmapped[].source` | string | 必須 | — |
| `unmapped[].note` | string | 任意 | — |

## 5. 検証ルール（①レシピローダが起動時に当てる）

1. 全pathの存在確認（`source_gpml` / `provided_table.path` / `gene_info.path`(指定時) / `target.transcript_gene_gtf`(指定時) / `tpm`(指定時)）。
2. `provided_table.columns.*` が実際の表ヘッダに存在するか（`target_id`・`source_symbol`は必須、`source_pid`は指定時）。
3. `output_id_namespace` が空でないか。
4. `policy` / `format` のenum値。
5. `routes.pid=true` なら `idmap` が指定・存在するか。`routes.compute=true` なら `compute_fallback.blastp` が妥当か（evalue>0、identity/coverageは0–100）。
6. 少なくとも1ルートが有効か。
7. `schema_version` の互換性。

検証失敗時は**ランタイムに入る前に**エラーで止める。

## 6. ID名前空間の約束

- **源(ヒト)**: ノードごとに`Xref/@Database`を読む。`Entrez Gene`は`gene_info`で公式記号へ、`HGNC`はIDが記号、`Enzyme Nomenclature`等は記号化できずcuration対象。
- **対象(ミツバチ)**: 候補の実体はassembly gene（`MSTRG.*` / `g####`）。これが出力XREFになる（PoC）。
- **Entrez正規化**: assembly→Entrezの橋渡しは本resourceからは取れないため、後段enrichmentとして保留。`output_id_namespace`を将来`Entrez Gene`に切り替える際に追加する。

## 7. 読み取り契約（どのコンポーネントが何を使うか）

| セクション | 使うコンポーネント |
|---|---|
| `pathway`, `target`(gtf除く) | ②パスウェイ変換器 |
| `target.transcript_gene_gtf` | ③解決器(候補畳み込み) と ④発現リンカ で**共有** |
| `ortholog_resolver`, `gene_info`, curationサイドカー | ③オーソログ解決器 |
| `expression.tpm` | ④発現リンカ |

## 8. 完全な例

```yaml
# configs/WP5609_Ac.yaml
schema_version: 2

pathway:
  source_gpml: ../resource/WP5609.gpml
  # 源IDの名前空間はノードごとに Xref/@Database から読む
  # (WP5609実測: Entrez Gene 25 / HGNC 12 / Enzyme Nomenclature 1)

target:
  taxid: 7461                          # Apis cerana（japonica亜種のtaxidは要確認）
  output_id_namespace: assembly        # PoC暫定。Entrezは後段enrichmentで保留
  transcript_gene_gtf: ../resource/A_cerana/figshare_27175734/ref_transcript_Ac.gtf

ortholog_resolver:
  policy: augment
  provided_table:
    path: ../resource/A_cerana/figshare_27175734/fuctional_annotation_transcript_Ac.tsv
    format: tsv
    columns:
      target_id:     "ProteinID"
      source_symbol: "H_sapiens-gene_symbol"   # 主ルートの結合キー
      source_pid:    "H_sapiens-pid"           # 精密ルート用(ENSP)
  gene_info:
    path: ../resource/Homo_sapiens.gene_info
    taxid: 9606
  routes:
    symbol: true        # 主・再現率重視
    pid: false          # 精密。要 idmap(source_id->ENSP)。PoCは保留
    compute: false      # blastp。PoCは保留(curationで代替)
  idmap: null

expression:                            # Phase2。最初の通しでは省略可
  tpm: ../resource/A_cerana/figshare_27157632/tpm_Ac.tsv

curation_file: WP5609_Ac.curation.yaml
```

## 9. 非目標（recipeに書かないもの）

- コード・処理ロジック（=mechanism側に置く）。
- 派生データ（解決結果のキャッシュ、出力GPML等）。
- 秘密情報（APIキー等）。
- パスウェイ／種ペアに依らず不変の一般設定（=既定値としてcode側）。

## 10. バージョニング

- `schema_version` でスキーマ変更を追跡する。
- 後方非互換な変更（フィールド削除・意味変更）はメジャー更新とし、ローダで弾く。
- v1→v2: `source_id_namespace`(単一値)を廃止しノード単位読みに、`columns`を`source_symbol`/`source_pid`/`target_id`に再編、`gene_info`/`routes`を追加、GTFを`target.transcript_gene_gtf`に移動して③④共有、`output_id_namespace`の既定を`assembly`に。
