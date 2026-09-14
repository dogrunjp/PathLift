# PathLift

WikiPathways の GPML パスウェイを、オルソログ対応表を参照して**別種の遺伝子IDに付け替える（lift する）** CLI ツール。
変換元（ヒト等）の GeneProduct ノードを、target 種の候補遺伝子ノードに置換・展開した GPML を出力する。

- 設計と背景：`設計資料/`（まず `設計資料/PoC知見と設計判断.md`）
- AI エージェント向け規範：`CLAUDE.md`
- 実行テストの記録：`開発管理/テストログ_*.md`

---

## 1. 環境構築



Python 3.10+ と PyYAML だけ。重い依存（lxml/pandas 等）は無い。

```bash
conda create -n pathlift python=3.12 -y
conda activate pathlift
pip install -e .          # pathlift コマンドが入る（PyYAML も自動で入る）
```

`pip install -e .` の代わりに依存だけ入れて `python -m pathlift.cli run …` でも動く。

確認：
```bash
pathlift run --help
```

> **`pip install -e .` は何をしている？（Python に不慣れな人向け）**
>
> - **必ずリポジトリのルート（`PathLift/`）で実行する。** `.` はカレントディレクトリの意味で、pip はそこの `pyproject.toml` を読む。別の場所で叩くと `pyproject.toml` が見つからず失敗する。
> - リポジトリ全体を漁るのではなく、`pyproject.toml` の `packages = ["pathlift"]` で**指定した `pathlift/` だけ**をパッケージとして登録する。`設計資料/` や `configs/` の中身は対象外。
> - 登録されると2つ起きる：(1) どこからでも `import pathlift` が通る、(2) `pathlift` という**コマンドが PATH に作られる**（`[project.scripts]` の指定による）。だから以後 `pathlift run …` と打てる。
> - **`-e`（editable）** は、コードをコピーせず今の `pathlift/` を参照したままインストールする指定。`pathlift/*.py` を編集したら再インストール不要で次の実行に反映される。
>
> うまくいかないとき：`pathlift: command not found` なら、その conda 環境を `activate` し忘れか、ルート以外で `install` した可能性。`pip install -e .` を `PathLift/` で叩き直す。

**`compute` ルート（BLASTレスキュー、5章）を使うなら追加で `blastp` が必要。** 使わない（`routes.compute: false`、既定）なら不要なので、まずは1章だけで動かせる。

---

## 2. リソースの取得

大容量入力は `resource/` 配下に置く（`.gitignore` 済み・リポジトリには含めない）。
**取得元（DOI/URL）を `開発管理/` に記録**しておくと、種を増やすとき楽。

**下表のリソースは自動では揃わない。** 無ければ `開発管理/手動PoC記録.md` を参照し、それでも分からなければ取得済みのメンバーに確認する。

| 入力 | 取得元 | 置き場所（例） | 取得元 |
|---|---|---|---|
| source GPML | WikiPathways | `resource/WP550.gpml` |`https://github.com/wikipathways/wikipathways-database/blob/main/pathways/WP550/WP550.gpml`|
| 対応表（A.cerana） | FunFlow figshare 27175734 | `resource/A_cerana/.../fuctional_annotation_transcript_Ac.tsv` | `https://figshare.com/articles/dataset/Apis_cerana_japonica_transcript_data_transcript_sequence_data_predicted_amino_acid_sequence_data_functional_annotation_data_/27175734/fuctional_annotation_transcript_Ac.tsv` |
| GTF（A.cerana） | 同上 | `resource/A_cerana/.../ref_transcript_Ac.gtf` |
| gene_info（ヒト） | NCBI（**ヒト単独**ファイル `Homo_sapiens.gene_info`） | `resource/Homo_sapiens.gene_info` |`https://ftp.ncbi.nlm.nih.gov/gene/DATA/GENE_INFO/Mammalia/Homo_sapiens.gene_info.gz`
| TPM（任意・Phase2） | figshare 27157632 等 | `resource/.../tpm_*.tsv` | |
| reference FASTA（任意・compute用） | target種の全アミノ酸配列（無ければ`false`でOK。5章） | `resource/A_cerana/.../ref_transcript_Ac_pep.fa` |

> B.mori は GTF（RefSeq `GCF_030269925.1`）が対応表の ID（KWMTBOMO）と系統が違うため **txgene では使わない**（パターン畳み）。詳細は `設計資料/PoC知見と設計判断.md` F章。

---

## 3. recipe を用意

`configs/` に recipe（＋必要なら curation サイドカー）を置く。書式は `設計資料/recipe.schema.md`。
雛形：`configs/WP5277_Bmori.yaml` ほか。

**recipe内に書くパス（`source_gpml`等）の基準は「recipe ファイルのあるディレクトリ」**。この配置（`configs/` と `resource/` が同階層）では `../resource/...` と書く。（`-o`の出力先やコマンドをどこで打つかは別の話 → 8章）

各項目の詳しい意味は `設計資料/recipe.schema.md` が正本。ここでは最小構成にコメントだけ添える：

```yaml
pathway:
  source_gpml: ../resource/WP5277.gpml   # 変換元(ヒト等)のGPML本体。2章の表から取得したもの

target:
  transcript_gene_gtf: ../resource/B_mori/...   # target種のtranscript→gene対応（任意）

ortholog_resolver:
  provided_table:
    path: ../resource/B_mori/FF4I-B_mori-protein.tsv   # 変換元↔target種の対応表
    columns:
      target_id:     B_mori-pid          # 対応表内の「target種ID」列名
      source_symbol: H_sapiens-gsymbol    # 対応表内の「変換元の遺伝子記号」列名（主ルート）
      source_pid:    H_sapiens-ENSPID     # 対応表内の「変換元のprotein ID」列名（精密ルート用・任意）
  gene_info: {path: ../resource/Homo_sapiens.gene_info}   # 変換元のGeneID→公式記号の変換表
  routes: {symbol: true, pid: false, compute: false}      # compute: true にする場合は5章参照
```

---

## 4. 実行

リポジトリ直下から：

```bash
pathlift run configs/WP550_Ac.yaml -o out_WP550_A_cerana_0914.gpml
```

出力 stats の読み方：

```
  GeneProduct: 13          変換元の GeneProduct 数
    matched  : 7           解決できた数
    unmapped : 6           落ちた数（MISS。素性は設計資料 C章）
  候補gene総数 : 12          展開後の候補遺伝子の総数
  追加ノード   : 5           展開で増えたノード数
  --- 注意(未対応の可能性) ---     ↓ 出たら要確認
  記号ラベル依存 : 13件        非Entrez/HGNC。ラベルが記号でないと取りこぼす恐れ（E章/G-1）
  txgene未対応   : 0件         畳めなかったID。重複展開の恐れ（F章/G-1）
```

`unmapped` が出て `routes.compute: true` なら、続けて次のようなログが出て自動レスキューが走る（詳細は5章）：

```
[!] 迷子遺伝子を 7 件検出。自動レスキューを開始します...
[*] 6 種類の迷子遺伝子について、UniProtサーバーにFASTA配列を問い合わせます...
  -> [取得成功] TPH1 reviewed 2件
[*] リモートBLAST検索 (TaxID: 7461)
[+] 自動キュレーションファイルを生成しました: configs/<recipe>_auto_curation.yaml
[*] キュレーションを適用してGPMLを再生成します...
[+] 自動レスキューによる補完が完了しました。
```

`routes.compute: false`（既定）なら、代わりに次の1行が出て自動レスキューはスキップされる（ネットワークアクセスなし）：

```
[!] 迷子遺伝子を 7 件検出しましたが、routes.compute が無効なため自動レスキューはスキップします。
```

---

## 5. compute ルート（BLASTレスキュー）

`symbol`/`pid` で解決できなかった unmapped 遺伝子を、BLASTで自動的に recall 回収する機能（`ortholog_resolver.routes.compute`）。
既定は `false`（何もしない）。有効にすると、`unmapped` が残った回に限り以下が自動実行される。

1. **UniProt REST**で unmapped の遺伝子記号ごとに変換元種のアミノ酸配列を取得
2. **blastp**を実行（`target.reference_fasta` があればローカル `-subject`、無ければ NCBI `nr` への `-remote`）
3. ヒットをフィルタし（閾値は固定ロジック。recipeでは変更しない。`設計資料/recipe.schema.md`参照）、`<recipeのstem>_auto_curation.yaml`（overrides/unmapped）を自動生成
4. そのcurationを適用して**2周目のliftoverを自動実行**し、同じ出力パスに上書き保存

### 有効にする設定

```yaml
ortholog_resolver:
  routes:
    compute: true
  compute_fallback:
    blastp:
      evalue: 1e-5      # 必須。recipeで調整できるのはこれだけ
target:
  reference_fasta: false   # target種の全アミノ酸配列FASTA。無ければ false（remote blastpになる）
```

`reference_fasta` を指定するとローカルblastp（速い・オフライン）、`false`/未指定だとNCBI `nr` への remote blastp（`target.taxid`で絞込。低速・要ネット）になる。

### `blastp` のインストール（macOS）

Homebrewを使わないなら、bioinformatics界隈で標準的な **conda（bioconda channel）** が簡単（動作確認済み：`blast 2.16.0`）。

```bash
conda create -n pathlift-blast -c bioconda -c conda-forge blast
conda activate pathlift-blast
blastp -version
```

`pathlift`本体とは別envで構わない。`blastp`さえ`PATH`に通っていれば、`pathlift`をどのPython環境で動かしていても`subprocess`経由で見つかる。

### 既知の注意点

- **NCBI E-utilitiesのレート制限（HTTP 429）が起きることがある**。remote blastp利用時、ヒットしたprotein accessionをEntrez Gene IDに変換する際に問い合わせる先（`ncbi_protein_to_gene_id`）が混み合うと発生する。起きても致命的ではなく、該当エントリの`target_label`（GPMLのTextLabel書き換え用）だけが空欄になる（`target`のGene ID自体は取れる）。詳細・再現例は`開発管理/テストログ_*.md`。
- remote blastpはNCBI側のキュー待ちが発生し、数分かかることがある。

---

## 6. 出力の確認

- **PathVisio**（3.x/4.x）で出力 GPML を開く。2013a なので開ける。
  - `output_id_namespace: assembly` は非標準 DataSource なので「未知のデータソース」警告が出る（**想定どおり**。ID は見えるがリンク解決はされない）。
- 展開と provenance、MISS を grep で確認：

```bash
grep -c 'Source="PathLift"' out.gpml      # PathLift が触れたノード数
grep -o 'routes=[^<"]*' out.gpml | sort | uniq -c   # どのルートで当たったか
grep -o 'unmapped:[^<]*' out.gpml          # MISS（記号付き）
```

- **候補の選別**（偽陽性の除去）は PathLift の外。出力 GPML と拡張 TPM を **QPX notebook** で発現と突き合わせて行う。

---

## 7. PoC 実績（再現用の実例）

| recipe | source | target | matched/GeneProduct | 展開率 |
|---|---|---|---|---|
| WP550_ac.yaml | WP550 | | |
| WP5609_Ac.yaml | WP5609（代謝） | A.cerana | 31/38 (82%) | 2.3 |
| WP5277_Bmori.yaml | WP5277（ステロイド代謝） | B.mori | 7/13 (54%) | 1.7 |
| WP5601_Bmori.yaml | WP5601（シグナル） | B.mori | 23/33 (70%) | 3.0 |

数字の解釈は `設計資料/PoC知見と設計判断.md`（マッチ率・展開率の二要因、MISS の支配機構）。

---

## 8. つまずきやすい点

- `bquote>` / `quote>` がシェルに出て止まる → 引用符（`` ` `` `'` `"`)の閉じ忘れ。`Ctrl-C` で抜ける。
- `recipe検証に失敗` → 正常動作。メッセージのパス／列名を直す。特に**相対パスの基準（recipe のディレクトリ）**と表ヘッダの列名一致。
- パスが `.../src/resource` のように一段ずれる → recipe の `../resource` の階層数を配置に合わせる。
- `-o` の出力パスは **実行時のカレントディレクトリ基準**（recipe 基準ではない）。
- `routes.compute: true` なのに `blastp: command not found` → `blastp`をインストールしたconda envを`activate`し忘れ。envは`pathlift`実行時のシェルのPATHに`blastp`が乗ってさえいればよく、`pathlift`自体を動かしているPython環境と同じである必要はない。
- `compute`実行時にNCBI関連のエラーが1件だけ出て止まらない → 5章「既知の注意点」のレート制限。致命的ではないので無視してよい（頻発するなら要相談）。

---

## ディレクトリ構成

```
PathLift/
├── pathlift/   コード(パッケージ)。models / txgene / ortholog / gpml / transform / recipe / cli
│               / query_fasta / blast_runner / auto_curation（compute ルート）
├── configs/    recipe + curation（+ compute実行時は *_auto_curation.yaml もここに生成される）
├── spike/      調査用スクリプト
├── 設計資料/    設計（権威）
├── 開発管理/    ログ・記録
├── resource/   大容量入力(gitignore)。unmapped_queries.fa 等の中間生成物もここに出る
└── pyproject.toml
```
