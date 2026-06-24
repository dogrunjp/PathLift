# PathLift

WikiPathways の GPML パスウェイを、オーソログ解決で**別種へ lift** する CLI ツール。
source（ヒト等）の GeneProduct ノードを、target 種の候補遺伝子ノードに置換・展開した GPML を出力する。

- 設計と背景：`設計資料/`（まず `設計資料/PoC知見と設計判断.md`）
- AI エージェント向け規範：`CLAUDE.md`

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

---

## 2. リソースの取得

大容量入力は `resource/` 配下に置く（`.gitignore` 済み・リポジトリには含めない）。
**取得元（DOI/URL）を `開発管理/` に記録**しておくと、種を増やすとき楽。

| 入力 | 取得元 | 置き場所（例） |
|---|---|---|
| source GPML | WikiPathways（**新 GitHub システム**。Classic は読み取り専用） | `resource/WP5277.gpml` |
| 対応表（A.cerana） | FunFlow figshare 27175734 | `resource/A_cerana/.../fuctional_annotation_transcript_Ac.tsv` |
| GTF（A.cerana） | 同上 | `resource/A_cerana/.../ref_transcript_Ac.gtf` |
| 対応表（B.mori） | FF4I figshare 19368137（`FF4I-B_mori-protein.tsv`） | `resource/B_mori/FF4I-B_mori-protein.tsv` |
| gene_info（ヒト） | NCBI（**ヒト単独**ファイル `Homo_sapiens.gene_info`） | `resource/Homo_sapiens.gene_info` |
| TPM（任意・Phase2） | figshare 27157632 等 | `resource/.../tpm_*.tsv` |

> B.mori は GTF（RefSeq `GCF_030269925.1`）が対応表の ID（KWMTBOMO）と系統が違うため **txgene では使わない**（パターン畳み）。詳細は `設計資料/PoC知見と設計判断.md` F章。

---

## 3. recipe を用意

`configs/` に recipe（＋必要なら curation サイドカー）を置く。書式は `設計資料/recipe.schema.md`。
雛形：`configs/WP5277_Bmori.yaml` ほか。

**相対パスの基準は「recipe ファイルのあるディレクトリ」**。この配置（`configs/` と `resource/` が同階層）では `../resource/...` と書く。

```yaml
pathway:
  source_gpml: ../resource/WP5277.gpml
ortholog_resolver:
  provided_table:
    path: ../resource/B_mori/FF4I-B_mori-protein.tsv
    columns: {target_id: B_mori-pid, source_symbol: H_sapiens-gsymbol, source_pid: H_sapiens-ENSPID}
  gene_info: {path: ../resource/Homo_sapiens.gene_info}
  routes: {symbol: true, pid: false, compute: false}
```

---

## 4. 実行

リポジトリ直下から：

```bash
pathlift run configs/WP5277_Bmori.yaml -o out_WP5277_B_mori.gpml
```

出力 stats の読み方：

```
  GeneProduct: 13          源の GeneProduct 数
    matched  : 7           解決できた数
    unmapped : 6           落ちた数（MISS。素性は設計資料 C章）
  候補gene総数 : 12          展開後の候補遺伝子の総数
  追加ノード   : 5           展開で増えたノード数
  --- 注意(未対応の可能性) ---     ↓ 出たら要確認
  記号ラベル依存 : 13件        非Entrez/HGNC。ラベルが記号でないと取りこぼす恐れ（E章/G-1）
  txgene未対応   : 0件         畳めなかったID。重複展開の恐れ（F章/G-1）
```

---

## 5. 出力の確認

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

## 6. PoC 実績（再現用の実例）

| recipe | source | target | matched/GeneProduct | 展開率 |
|---|---|---|---|---|
| WP5609_Ac.yaml | WP5609（代謝） | A.cerana | 31/38 (82%) | 2.3 |
| WP5277_Bmori.yaml | WP5277（ステロイド代謝） | B.mori | 7/13 (54%) | 1.7 |
| WP5601_Bmori.yaml | WP5601（シグナル） | B.mori | 23/33 (70%) | 3.0 |

数字の解釈は `設計資料/PoC知見と設計判断.md`（マッチ率・展開率の二要因、MISS の支配機構）。

---

## 7. つまずきやすい点

- `bquote>` / `quote>` がシェルに出て止まる → 引用符（`` ` `` `'` `"`)の閉じ忘れ。`Ctrl-C` で抜ける。
- `recipe検証に失敗` → 正常動作。メッセージのパス／列名を直す。特に**相対パスの基準（recipe のディレクトリ）**と表ヘッダの列名一致。
- パスが `.../src/resource` のように一段ずれる → recipe の `../resource` の階層数を配置に合わせる。
- `-o` の出力パスは **実行時のカレントディレクトリ基準**（recipe 基準ではない）。

---

## ディレクトリ構成

```
PathLift/
├── pathlift/   コード（パッケージ）
├── configs/    recipe + curation
├── spike/      調査用スクリプト
├── 設計資料/    設計（権威）
├── 開発管理/    ログ・記録
├── resource/   大容量入力（gitignore）
└── pyproject.toml
```
