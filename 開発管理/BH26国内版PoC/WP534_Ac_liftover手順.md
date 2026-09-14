# WP534 を A. cerana へ liftover する手順

## 今回のチャットでのリクエスト

実施日: 2026-09-14

ユーザーからの依頼内容:

1. `https://www.wikipathways.org/pathways/WP534.html` に対して、なんらかの生物種で liftover のテストを行い、動作確認しつつ手順書を作る。
2. 生物種が決まった後に必要リソースをマニュアルで探す想定で、確認すべき点はチャットで確認しながら進める。
3. target 生物種は A. cerana とする。
4. 必要なリソースのリストを手順書に含める。リストが決まったら表示する。
5. qpx-data 側にある `WP534.gpml` も候補として確認する。
6. WikiPathways から直接取得した GPML の方が新しければ、新しい方を使う。
7. BLAST を入れる。既存の BLAST 導入ドキュメントが見つかれば、それを参考にする。
8. PathVisio で GPML を表示して目視確認する。
9. 今回のチャットのリクエスト内容と、使ったローカルリソースを開発管理に書き出す。

作業上の判断:

- source GPML は qpx-data 既存版ではなく、WikiPathways 直接取得版を採用した。
- target は A. cerana、対応表は既存の FunFlow figshare 27175734 リソースを使用した。
- まず `compute: false` で表ルートのみを確認し、その後 `compute: true` でローカル BLAST 救済を確認した。
- BLAST は新規導入ではなく、既存 conda 環境 `pathlift-blast` に導入済みの `blastp` を使用した。
- PathVisio は `/Applications/pathvisio-3.3.0` を使用した。

## 使用したローカルリソース

### 参照した外部既存データ

| 用途 | パス | 備考 |
|---|---|---|
| qpx-data 側 WP534 GPML | `/Users/oec/Dropbox/workspace/qps/qpx-data/data/Bombyx_mori_primary_metabolism/Data/WP534/WP534.gpml` | `WP534_r137112` / `Last-Modified=20250227230102`。最新版ではないため採用しない |
| qpx-data 側 WP534 関連ファイル群 | `/Users/oec/Dropbox/workspace/qps/qpx-data/data/Bombyx_mori_primary_metabolism/Data/WP534/` | B. mori 用の手動変換・IDリスト系ファイルを含む。A. cerana liftover では直接使用しない |

### PathLift 入力リソース

| 用途 | パス | 備考 |
|---|---|---|
| source GPML | `resource/WP534.gpml` | WikiPathways 直接取得版。`WP534_r141823` / `Last-Modified=20251125012351` |
| A. cerana 対応表 | `resource/A_cerana/figshare_27175734/fuctional_annotation_transcript_Ac.tsv` | FunFlow figshare 27175734。`ProteinID` / `H_sapiens-gene_symbol` / `H_sapiens-pid` を使用 |
| A. cerana transcript→gene GTF | `resource/A_cerana/figshare_27175734/ref_transcript_Ac.gtf` | `MSTRG.x.y` を `MSTRG.x` へ畳み込むために使用 |
| A. cerana protein FASTA | `resource/A_cerana/figshare_27175734/ref_transcript_Ac_pep.fa` | `compute: true` のローカル `blastp -subject` に使用 |
| A. cerana TPM | `resource/A_cerana/figshare_27175734/tpm_Ac.tsv` | recipe に記載。今回の PathLift liftover 本体では未使用 |
| ヒト gene_info | `resource/Homo_sapiens.gene_info` | Entrez Gene ID から公式 symbol への正規化に使用 |

### 作成した recipe / curation

| 用途 | パス | 備考 |
|---|---|---|
| 表ルート確認 recipe | `configs/WP534_Ac.yaml` | `routes.compute: false` |
| 空 curation | `configs/WP534_Ac.curation.yaml` | 初回は `overrides: []` / `unmapped: []` |
| compute 確認 recipe | `configs/WP534_Ac_compute.yaml` | `routes.compute: true` / `evalue: 1e-5` |
| compute 自動 curation | `configs/WP534_Ac_compute_auto_curation.yaml` | BLAST 結果から自動生成 |

### 実行で生成したファイル

| 用途 | パス | 備考 |
|---|---|---|
| 表ルートのみ出力 GPML | `out_WP534_Ac.gpml` | matched 36 / unmapped 11 |
| compute 後出力 GPML | `out_WP534_Ac_compute.gpml` | matched 43 / unmapped 4。PathVisio で目視確認対象 |
| compute query FASTA | `resource/WP534_Ac_compute_unmapped_queries.fa` | UniProt から取得した unmapped 11件分 |
| BLAST raw TSV | `resource/WP534_Ac_compute_unmapped_queries_results.tsv` | ローカル BLAST 結果 |
| BLAST filtered TSV | `resource/WP534_Ac_compute_unmapped_queries_results_filtered.tsv` | RBH_plus 由来固定フィルタ通過結果 |

### 実行ツール

| 用途 | パス / コマンド | 備考 |
|---|---|---|
| PathLift CLI | `python -m pathlift.cli run ...` | repo 内 editable install に依存しない呼び方で実行 |
| BLAST | `/Users/oec/miniconda3/envs/pathlift-blast/bin/blastp` | `blastp: 2.16.0+` |
| PathVisio | `/Applications/pathvisio-3.3.0/pathvisio.jar` | `sh /Applications/pathvisio-3.3.0/pathvisio.sh ...` で起動 |

## 目的

WikiPathways の `WP534`（Glycolysis and gluconeogenesis / Homo sapiens）を source GPML とし、A. cerana の FunFlow リソースを使って PathLift の liftover 動作を確認する。

## 使用する WP534

- 採用版: WikiPathways から直接取得した最新版
- GPML: `resource/WP534.gpml`
- 取得 URL: `https://www.wikipathways.org/wikipathways-assets/pathways/WP534/WP534.gpml`
- 確認時の GPML version: `WP534_r141823`
- 確認時の Last-Modified: `20251125012351`

参考: qpx-data 側にも `WP534.gpml` があるが、確認時点では `WP534_r137112` / `20250227230102` であり、WikiPathways 直接取得版の方が新しいため採用しない。

## リソース一覧

### 必須

| 用途 | パス | 備考 |
|---|---|---|
| source GPML | `resource/WP534.gpml` | WikiPathways から直接取得 |
| A. cerana 対応表 | `resource/A_cerana/figshare_27175734/fuctional_annotation_transcript_Ac.tsv` | FunFlow figshare 27175734 |
| transcript→gene 畳み込み | `resource/A_cerana/figshare_27175734/ref_transcript_Ac.gtf` | FunFlow figshare 27175734 |
| ヒト Entrez→symbol 正規化 | `resource/Homo_sapiens.gene_info` | NCBI gene_info |

### 任意

| 用途 | パス / ツール | 備考 |
|---|---|---|
| compute ルート用 A. cerana protein FASTA | `resource/A_cerana/figshare_27175734/ref_transcript_Ac_pep.fa` | `routes.compute: true` のローカル blastp 用 |
| 発現データ | `resource/A_cerana/figshare_27175734/tpm_Ac.tsv` | 後段確認用。PathLift 本体の liftover では未使用 |
| ローカル BLAST | `blastp` | `pathlift-blast` conda 環境に導入済み |

## recipe

`configs/WP534_Ac.yaml` を使う。初回確認では表ルートのみを見るため、`routes.compute: false` にする。

`curation_file` として `configs/WP534_Ac.curation.yaml` を置く。初回は手動判定なしなので空配列にする。

```yaml
overrides: []
unmapped: []
```

対応表の列指定:

```yaml
columns:
  target_id: ProteinID
  source_symbol: H_sapiens-gene_symbol
  source_pid: H_sapiens-pid
```

## 初回実行

```bash
pathlift run configs/WP534_Ac.yaml -o out_WP534_Ac.gpml
```

`routes.compute: false` のため、unmapped があっても BLAST レスキューは走らない。

## BLAST の確認

既存ドキュメントでは、macOS では conda/bioconda で NCBI BLAST+ を入れる手順を採用している。

```bash
conda create -n pathlift-blast -c bioconda -c conda-forge blast
conda activate pathlift-blast
blastp -version
```

今回の環境では `pathlift-blast` は既に存在し、以下を確認済み。

```text
blastp: 2.16.0+
 Package: blast 2.16.0, build Mar 28 2025 16:33:14
```

`pathlift` 実行時には `blastp` が PATH から見える必要がある。conda 環境を activate するか、次のように一時的に PATH を足す。

```bash
PATH=/Users/oec/miniconda3/envs/pathlift-blast/bin:$PATH \
  pathlift run configs/WP534_Ac_compute.yaml -o out_WP534_Ac_compute.gpml
```

## compute 実行

compute ルート確認用に `configs/WP534_Ac_compute.yaml` を使う。`configs/WP534_Ac.yaml` との差分は `routes.compute: true` と `compute_fallback.blastp.evalue`。

```yaml
routes:
  symbol: true
  pid: false
  compute: true
compute_fallback:
  blastp:
    evalue: 1e-5
```

実行コマンド:

```bash
PATH=/Users/oec/miniconda3/envs/pathlift-blast/bin:$PATH \
  python -m pathlift.cli run configs/WP534_Ac_compute.yaml -o out_WP534_Ac_compute.gpml
```

注: 初回、サンドボックス内では UniProt への名前解決に失敗し、query FASTA が 0 件になった。ネットワーク許可付きで再実行すると成功した。

## compute 実行結果

実行日: 2026-09-14

```text
[!] 迷子遺伝子を 11 件検出。自動レスキューを開始します...
[*] 11 種類の迷子遺伝子について、UniProtサーバーにFASTA配列を問い合わせます...
  -> [取得成功] PGK2 reviewed 1件
  -> [取得成功] LDHAL6B reviewed 1件
  -> [取得成功] HK2 reviewed 1件
  -> [取得成功] HK3 reviewed 1件
  -> [取得成功] PGI fallback
  -> [取得成功] G6PC1 reviewed 2件
  -> [取得成功] FBP2 reviewed 2件
  -> [取得成功] SLC2A2 reviewed 2件
  -> [取得成功] PFKL reviewed 2件
  -> [取得成功] PGAM2 reviewed 1件
  -> [取得成功] PCK1 reviewed 2件
=========================================
[+] 完了: 11 / 11 件の配列を /Users/oec/Dropbox/workspace/qps/PathLift/resource/WP534_Ac_compute_unmapped_queries.fa に保存しました。
[*] ローカルFASTA検索: /Users/oec/Dropbox/workspace/qps/PathLift/resource/A_cerana/figshare_27175734/ref_transcript_Ac_pep.fa
[+] 自動キュレーションファイルを生成しました: /Users/oec/Dropbox/workspace/qps/PathLift/configs/WP534_Ac_compute_auto_curation.yaml

[*] キュレーションを適用してGPMLを再生成します...
[+] 自動レスキューによる補完が完了しました。
== pathlift run ==
  source     : /Users/oec/Dropbox/workspace/qps/PathLift/resource/WP534.gpml
  routes     : symbol,compute  policy=augment
  out_ns     : assembly
  GeneProduct: 47
    matched  : 43
    unmapped : 4
  候補gene総数 : 115
  追加ノード   : 72  (展開後 GeneProduct ≒ 119)
  --- 注意(未対応の可能性) ---
  記号ラベル依存 : 2件 (非Entrez/HGNC。ラベルが記号でないと取りこぼす恐れ)
  -> out_WP534_Ac_compute.gpml
```

生成物:

| 種別 | パス | 備考 |
|---|---|---|
| query FASTA | `resource/WP534_Ac_compute_unmapped_queries.fa` | 168行 |
| BLAST raw TSV | `resource/WP534_Ac_compute_unmapped_queries_results.tsv` | 439行 |
| BLAST filtered TSV | `resource/WP534_Ac_compute_unmapped_queries_results_filtered.tsv` | 256行 |
| auto curation | `configs/WP534_Ac_compute_auto_curation.yaml` | override 256行、unmapped 4行 |
| output GPML | `out_WP534_Ac_compute.gpml` | PathLift コメント 119件 |

routes provenance:

```text
78 routes=symbol
37 routes=override
```

auto curation の unique override:

| source | target |
|---|---|
| `FBP2` | `MSTRG.1711`, `MSTRG.10591` |
| `LDHAL6B` | `MSTRG.8280`, `MSTRG.8281`, `MSTRG.8282` |
| `PCK1` | `MSTRG.10482` |
| `PFKL` | `MSTRG.2400` |
| `PGAM2` | `MSTRG.4496` |
| `PGK2` | `MSTRG.5334` |
| `SLC2A2` | `g8192`, `g9923`, `MSTRG.174`, `MSTRG.1019`, `MSTRG.1099`, `MSTRG.1100`, `MSTRG.1255`, `MSTRG.1259`, `MSTRG.1392`, `MSTRG.1393`, `MSTRG.1717`, `MSTRG.3015`, `MSTRG.3241`, `MSTRG.3261`, `MSTRG.3262`, `MSTRG.3455`, `MSTRG.3538`, `MSTRG.3850`, `MSTRG.3851`, `MSTRG.3999`, `MSTRG.4768`, `MSTRG.5504`, `MSTRG.7234`, `MSTRG.8499`, `MSTRG.8502`, `MSTRG.8838`, `MSTRG.9662`, `MSTRG.11532` |

compute 後も unmapped:

```text
G6PC1
HK2
HK3
PGI
```

これらは auto curation 上で `reason: blast_no_hit` / `note: BLASTpで明確なオーソログ無し` として記録される。

注: compute 由来の候補は出力上 `routes=override` として記録される。現状実装では人手 override と BLAST 自動補完の provenance は GPML 上で分かれない。

## 初回実行結果

実行日: 2026-09-14

```text
[!] 迷子遺伝子を 11 件検出しましたが、routes.compute が無効なため自動レスキューはスキップします。
== pathlift run ==
  source     : /Users/oec/Dropbox/workspace/qps/PathLift/resource/WP534.gpml
  routes     : symbol  policy=augment
  out_ns     : assembly
  GeneProduct: 47
    matched  : 36
    unmapped : 11
  候補gene総数 : 78
  追加ノード   : 42  (展開後 GeneProduct ≒ 89)
  --- 注意(未対応の可能性) ---
  記号ラベル依存 : 2件 (非Entrez/HGNC。ラベルが記号でないと取りこぼす恐れ)
  -> out_WP534_Ac.gpml
```

source GPML の GeneProduct Xref 内訳:

```text
Entrez Gene: 45
Ensembl: 1
Enzyme Nomenclature: 1
```

出力 GPML の PathLift コメント数:

```text
89
```

routes provenance:

```text
78 routes=symbol
```

unmapped:

```text
PCK1
LDHAL6B
PGK2
SLC2A2
G6PC1
PFKL
HK2
PGAM2
FBP2
HK3
PGI
```

注: source GPML 上の `G6PC` は、`Homo_sapiens.gene_info` による Entrez Gene ID 正規化後、`G6PC1` として unmapped 記録された。

## 確認項目

- recipe 検証が通ること。
- stats の `GeneProduct` / `matched` / `unmapped` / `候補gene総数` / `追加ノード` を記録すること。
- `記号ラベル依存` が出た場合は、非 Entrez/HGNC ノードが TextLabel 依存で解決された数として扱うこと。
- `txgene未対応` が出た場合は、A. cerana の target ID が gene 単位に畳めているか確認すること。
- 出力 GPML の PathLift コメント、unmapped コメント、routes provenance を grep で確認すること。

確認コマンド:

```bash
grep -c 'Source="PathLift"' out_WP534_Ac.gpml
grep -o 'routes=[^<"]*' out_WP534_Ac.gpml | sort | uniq -c
grep -o 'unmapped:[^<]*' out_WP534_Ac.gpml
```
