# PathLift 仕様書（pathway-liftover-spec）

> 正規仕様。「PathLift が**何をするか**」を規定する。設計の**根拠**は `PoC知見と設計判断.md` を参照。
> 旧 `仕様検討/pathway-liftover-spec.md`（pre-PoC ドラフト）を supersede する。

## 1. 目的とスコープ

PathLift は、WikiPathways の **GPML パスウェイ**を、**オーソログ解決**によって別種へ lift する CLI ツールである。入力の GeneProduct ノードを、target 種の候補遺伝子ノードに置換・展開した GPML を出力する。

### するこ と
- source GPML の各 GeneProduct を解決し、target 種の**候補遺伝子集合**に展開する。
- 絞らず**全候補を出す**（recall 優先）。各候補に provenance（どのルートで当たったか）を残す。
- 出力は source と同じ GPML（2013a）。PathVisio で開け、手動編集の出発点になる。

### しないこと（スコープ外）
- **候補の選別**：発現データで偽陽性を刈るのは後段（④発現リンカが TPM に結合キーを足し、選別は **QPX notebook**＝PathLift 外で行う）。
- **エッジ/相互作用の生成**：理想は target ノードを Group で束ね、PathVisio 上で手動構造編集する。エッジは追加しない（設計判断）。
- **座標の最適化**：重なり回避の最小限のみ（G章で改善保留）。
- **curation の全自動化**：MISS の素性切り分け・確定判断は引き続き人間（recipe のサイドカー）の責務。ただし unmapped の recall 回収に限っては、BLAST による自動キュレーション（`compute` ルート、§8）が override を自動生成する（2026-07 実装、人手 curation はこれを上書き・追記できる）。

## 2. 入出力契約

### 入力
- **source GPML**（必須）：ヒト等の元パスウェイ。GeneProduct ノードの Xref（Database/ID）と TextLabel を読む。
- **対応表**（必須）：1行＝target蛋白＋ source 種の突合キー（記号 / pid）。列名は recipe の `columns` で指定。
- **gene_info**（任意）：source 種の GeneID→公式記号。Entrez ノードの正規化に使う。
- **GTF**（任意）：transcript→gene 畳み込み。無ければ ID パターンで畳む。
- **recipe**（必須）：上記すべてを束ね、検証する policy ファイル。→ `recipe.schema.md`

### 出力
- **lift 済み GPML**：GeneProduct を候補遺伝子に置換・展開したもの。
  - 各候補ノードの `Xref`：`Database = output_id_namespace`（PoC暫定 `assembly`／非標準DataSource）、`ID = 候補gene_id`。
  - 各候補ノードに `<Comment Source="PathLift">candidate gene=…; transcripts=…; routes=…</Comment>`。
  - unmapped ノードに `<Comment Source="PathLift">unmapped: <記号> (no hit)</Comment>`（Xref は source のまま）。
  - 新規ノードの GraphId は `[a-f][0-9a-f]{4}` 規則準拠で発番（既存 ID と衝突しない）。クローンは source の GroupRef を継承。
- **stats**（標準出力）：`gene_product / matched / unmapped / candidate_genes / nodes_added`。

## 3. 解決ルート

有効化したルートを**すべて走らせ、結果を和集合**にする。候補ごとに当たったルートを provenance として記録。

| ルート | 内容 | 状態 |
|---|---|---|
| `symbol` | source ノードを公式記号に正規化し、表の記号列で引く | 主・実装済 |
| `pid` | source ID→ENSP（idmap）で表の pid 列を引く | 実装済（idmap 必須・通常オフ） |
| `override` | curation の手動対応を候補に追加 | 実装済 |
| `compute` | blastp 計算フォールバック（recall 回収の要） | **実装済**（2026-07。自動キュレーションとして。§8参照。tblastnは未対応） |

記号導出の優先順位：Entrez→gene_info、HGNC→ID直、**それ以外→TextLabel**。
→ 非 Entrez/HGNC（UniProt/Ensembl）は TextLabel 依存になる。潜在リスクは `PoC知見と設計判断.md` E章参照。

## 4. 候補の単位と畳み込み

- 解決器は **候補集合**（provenance 付き）を返す。同一 human gene が target の複数遺伝子に当たれば、複数ノードとして展開する（パラログ展開）。
- target 蛋白は **txgene** で gene 単位に畳む（`.pN` 除去 → GTF 優先 → IDパターン）。
  - 既知パターン：`MSTRG.x.y → MSTRG.x`、`g####.t# → g####`、`KWMTBOMO#####.mrnaN → KWMTBOMO#####`。
  - GTF とパターンの選択はアセット依存（`PoC知見と設計判断.md` F章）。

## 5. 展開（GeneProduct → 候補ノード）

- 候補 N 個に対し、**先頭は元ノードを再利用**（GraphId/位置を維持）、残り N−1 個は **クローン**して新規 GraphId 発番・位置を線形オフセットでずらす。
- 展開の magnitude は経路・アセット依存（固定倍率を仮定しない。D章）。

## 6. 出力 ID 名前空間

- `output_id_namespace`（PoC暫定 `assembly`）は出力 Xref の Database に書く文字列。候補 ID は target アセンブリ/遺伝子モデル ID（MSTRG/g/KWMTBOMO）で、標準 DataSource ではない。
- PathVisio では「未知のデータソース」警告が出る（想定どおり。ID は表示されるがリンク解決はされない）。
- 将来、target ID→Entrez 等の標準化（後段 enrichment）を入れたら、ここを標準 DataSource に変える。

## 7. 検証と失敗

- recipe は**ランタイム前に検証**する（`recipe.py`）。検証失敗なら `RecipeError` を投げ、ランタイムに入れない＝「下流はパス探索も判定もしない」を担保。
- 相対パスは **recipe ファイルのディレクトリ基準**で解決する。

## 8. 自動キュレーション（`compute` ルート）

> 2026-07、林さんのPR（#1・#3）で実装。`routes.compute` の実体。

`symbol`/`pid`/`override` の通常解決を終えても unmapped が残る場合、CLI（`cmd_run`）が追加で recall 回収を試みる。

1. **FASTA取得**：unmapped の遺伝子記号ごとに UniProt REST（`uniprotkb/search`）から source 種のアミノ酸配列を取得する（`query_fasta.py`）。reviewed エントリを優先し、無ければ fallback で再検索。
2. **blastp実行**：`target.reference_fasta` が指定されていればローカル `blastp -subject`、無ければ NCBI `nr` への remote blastp（`target.taxid` で entrez_query 絞込）を実行する（`blast_runner.py`）。結果を**RBH_plus由来の固定フィルター**（`length>=50` かつ `length/qlen>=0.6` かつ `length/slen>=0.6` かつ `qlen/slen>=0.7` かつ `slen/qlen>=0.7`。identityは見ない）でフィルタする。RBH_plusとPathLiftで同一ロジックを保つため、recipeでは調整しない固定値（`recipe.schema.md`参照）。
3. **override自動生成**：フィルタ後のヒットを curation の `overrides`（ヒットなしは `unmapped`）として `<recipeのstem>_auto_curation.yaml` に書き出す（`auto_curation.py`）。ローカルblastpの場合は txgene で target 遺伝子IDに畳み込み、remote（nr）の場合は NCBI E-utilities で protein→gene ID を引く。
4. **再解決**：生成した override を curation として読み込み直し、`OrthologResolver`／`PathwayTransformer` を再構築して2周目の変換を実行し、同じ出力パスに上書きする。

**実装上の注意点（設計と一致しない点）**：

- 候補は `Route.OVERRIDE` として記録される。`models.Route.COMPUTE` という enum 値は定義済みだが、現状コードからは使われていない（provenance 上は「BLAST由来」と「人手override」が区別できない）。
- `overrides` には任意で `target_label`（GPMLの`TextLabel`を上書きする値）を持たせられる（§4のcurationスキーマ拡張、`ortholog.py`/`gpml.py`）。
- **`ortholog_resolver.routes.compute` フラグと `compute_fallback.blastp.evalue` は現状参照されない**（`recipe.schema.md` 該当箇所の既知のギャップを参照）。unmapped が1件でもあれば `routes.compute` の値に関わらず自動キュレーションが発動し、evalueも`1e-5`固定。これは「ランタイムはrecipeの検証結果のみに従う」という本仕様の不変条件（1章・7章）に反するため、次の実装で `routes.compute` によるon/off・`compute_fallback.blastp.evalue` の注入を配線する必要がある（フィルタ閾値自体はRBH_plus由来の固定ロジックのままでよく、recipe化しない）。

## 関連
- 根拠・知見：`PoC知見と設計判断.md`
- スキーマ詳細：`recipe.schema.md`
- 構成：`c4_model.md` / 実行時フロー・設定分岐：`runtime_flow_and_branching.md`
