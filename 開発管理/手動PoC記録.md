# 手動PoC記録

設計と実際の操作の乖離を検出するための作業記録。
実際に手を動かして気づいたこと・設計への反映が必要な点を残す。

設計への反映が必要な観察は **【設計へのフィードバック】** タグで目立たせる。

---

## 記録の書き方

各セッションに以下を残す。

- **目的：** 何を確かめたくてやったか
- **環境・データ：** 使ったツール・ファイルの種類・実際の列構成など
- **手順：** 実際に行った操作（コマンド・操作手順）
- **観察：** 実際に何が起きたか（期待通りか・詰まった点・想定外の挙動）
- **設計へのフィードバック：** TODOのどの項目に影響するか

---
# マニュアルPoC: 1) 日本ミツバチのパスウェイ変換

## PoC #0 — 2026-06-01：リソース確認（WikiPathways DB更新・対応表の存在調査）

### 目的

- WikiPathwaysのローカルclone（設計A-5で確定した取得方式）が実際に使える状態かを確認する
- 日本ミツバチ（*Apis cerana japonica*）のオルソログ変換テーブルが既存のDBから取得可能か調査する（これは以前に作業したことのある種であるため、この種に特化した変換テーブルがあることが前提のPoC）
  - RefSeq・Entrez GeneがID体系として使えるか（設計A-4の前提確認）
  - 既存テーブルがなければ、RefSeqのfaaなどから変換テーブルを作成できるか判断する

### 参照作業

林さんによる2025/10/7の作業記録を参照。この種は以前に変換作業を行っているため、実際に使用したリソースの構成が判明している。

### 環境・データ

| 項目 | 内容 |
|------|------|
| 生物種 | 日本ミツバチ（*Apis cerana japonica*） |
| WikiPathways DBのローカルパス | `~/Desktop/docs/qp/src/wikipathways-database` |
| 変換ターゲットのWPID | WP5609（Inhibitors of metabolism in melanoma therapy）— ノード数・複雑さのバランスが適度 |
| 参照論文 | Comprehensive expression data for two honey bee species, *Apis mellifera* and *Apis cerana japonica* (doi: 10.1038/s41597-025-05279-z) |

**使用したリソース一覧（林さんの実績より）**

| ファイル・リソース | 内容 | 出典 |
|-------------------|------|------|
| `functional_annotation_transcript_Ac.tsv` | A.ceranaとヒトの対応関係（メインの変換テーブル） | figshare doi: 10.6084/m9.figshare.27175734 |
| `ref_transcript_Ac_pep.fa` | A.ceranaのPIDとtranscript IDの対応関係 | figshare doi: 10.6084/m9.figshare.27175734 |
| `tpm_Ac.tsv` | 発現データ（TPM） | figshare doi: 10.6084/m9.figshare.27157632 |
| UniProt | ヒトのアミノ酸配列（blastp用） | https://www.uniprot.org/ |
| NIH BLAST (blastp) | アノテーションで対応が取れなかった遺伝子の追加マッピング | https://blast.ncbi.nlm.nih.gov/Blast.cgi |
| NIH protein検索 | A.cerana PIDからGene IDへの変換 | https://www.ncbi.nlm.nih.gov/protein/ |

### 手順

1. WikiPathways DBを更新する（`git pull`）
2. 変換ターゲットのパスウェイ（WP5609）のGPMLを確認する
3. `functional_annotation_transcript_Ac.tsv` の列構成を確認する（ヘッダー行を記録）
4. テーブルでカバーできなかった遺伝子がどう処理されたか確認する（blastp手順を把握）
5. `ref_transcript_Ac_pep.fa` でPID→transcript IDのマッピング方法を確認する

### 観察

- 対応表の列構成（`functional_annotation_transcript_Ac.tsv` のヘッダー行）：

```
（ヘッダー行・funFlowの結果でありA. cerana-H.sapiens 以外の対応関係も記述されている）
1	ProteinID	H_sapiens-pid	H_sapiens-gene_symbol	H_sapiens_description	M_musculus-pid	M_musculus-gene_symbol	M_musculus_description	C_elegans-pid	C_elegans-gene_symbol	C_elegans-description	D_melanogaster-pid	D_melanogaster-gene_symbol	D_melanogaster-description	B_mori-pid	B_mori-gene_symbol	B_mori_description	B_terrestris-pid	B_terrestris-gene_symbol	B_terrestris-description	N_vitripennis-pid	N_vitripennis-gene_symbol	N_vitripennis-description	A_mellifera-pid	A_mellifera-gene_symbol	A_mellifera_description	UniGene-pid	UniGene-gene_symbol	UniGene-description	Pfam-IDs	Pfam-Names

```
- ヒトと日本ミツバチの変換に必要なのはとりあえず4列目まで。
- ミツバチのPIDはMSTRG*というこの種・研究独自のID。他の独自IDがついている可能性もあったかも。

- ヒト側のIDカラム：`H_sapiens-pid`（ENSP* ＝ Ensemblタンパク質ID）、`H_sapiens-gene_symbol`（NCBI遺伝子シンボル）、`H_sapiens_description`
- A.cerana側のIDカラム：`ProteinID`（MSTRG* ＝ この論文・研究プロジェクト固有のID。標準DBのIDではない）
- 表にEntrez Gene IDは含まれない。Entrez Gene IDはNIH protein検索で別途PIDから引く必要がある
- アノテーションで対応が取れなかった遺伝子の割合・傾向：（実施後に記入）
- blastp手順の詳細（実施後に記入）：
- 追加で気づいたこと：

### 【設計へのフィードバック】

参照：`設計資料/仕様検討/pathway-liftover-spec.md`（林さん作成の叩き台）との照合。

**実際の変換フロー（仕様書ステップ3〜7より）：**

```
GPML各ノードのgeneID
  ↓ [ステップ3] geneID → ヒトPID（Ensembl ENSP*）を取得（Ensemblを使用）
  ↓ [ステップ4] 対応表 で ヒトPID(ENSP*) → ミツバチPID(MSTRG*) を照合
  ↓ [ステップ5] ミツバチPID → geneID（またはtranscriptID）に変換、ノードを書き換え
  ↓ [ステップ6] 発現データとの照合。合わなければ発現データファイルにgeneID列を追加
  ↓ [ステップ7] 対応表にない遺伝子：UniProtからアミノ酸配列取得 → blastp → 手動確認 → ノード書き換え
```

| 関連TODO | 気づき・修正が必要な設計判断 |
|----------|------------------------------|
| A-4 | **設計前提との不一致。** 設計は「RefSeq NP_xxx + Entrez Gene ID」の2列を核とした単純な対応表を想定しているが、実際はステップ3で「geneID → ヒトPID（Ensembl ENSP*）」という前処理が別途必要。対応表はENSP*↔MSTRG*の対応であり、RefSeq NP_xxxはどこにも登場しない。A-4はこの実態に合わせて「対応表が持つべき列構成」ではなく「パイプラインが受け入れられるID体系の種類」として再定義が必要。 |
| A-4補足 | ミツバチPIDはgeneIDに変換したいが、できない場合はtranscriptIDで代替している（仕様書ステップ5注記）。ID変換の「望ましい姿」と「許容フォールバック」を設計に明示する必要がある。 |
| A-1 | 対応表はfanflow（坊農先生）の出力（funFlow）である可能性が高い。fanflowは対応表が存在しない場合の代替手段として仕様書に明記されている。blastp（NIH）はその先の補完手段（ステップ7）。A-1で整理すべき手法は「fanflow（funFlow）」と「blastp補完」の2段構え。 |
| A-2 | ステップ5のノード書き換えとステップ7のblasp結果確認が「手動介入」の2つの主要ポイント。特にステップ7は「UniProtから配列取得→blastp実行→機能確認→書き換え」という複合作業。Level 3の手動介入フローはこれら2段階を区別して設計する必要がある。 |
| A-6 | ステップ6では発現データファイルにgeneID列を**追加**する作業が発生する。これは発現データファイルへの書き込みを意味し、入力ファイルを研究者が提供するだけでは完結しない可能性がある。A-6の設定ファイル仕様に「発現データのID体系の明示」と「列追加の許可フラグ」等が必要かもしれない。 |
| その他 | 仕様書に「対応表が参考論文の参考文献内にある場合もある」という注記がある。研究者が対応表を見つけるための案内をドキュメント or ツールのエラーメッセージとして提供できるか検討する。 |

---
## PoC #1 — 2026-07-03：Arabidopsis→Chlamydomonas パスウェイリフトオーバー

### 目的
Arabidopsis thaliana のパスウェイ（GPML形式）を、オルソログ対応表を用いて Chlamydomonas reinhardtii の遺伝子IDにリフトオーバー（変換）できるか検証する。

### 環境・データ
| 項目 | 内容 |
|------|------|
| 生物種 | Arabidopsis thaliana（taxid: 3702）→ Chlamydomonas reinhardtii（taxid: 3055） |
| 使用ツール | ggsearch, pathlift |
| オルソログ対応表の出典・作成手法 | ggsearch36（FASTA36パッケージ、global-global alignment）による相同性検索結果（`aracyc_to_chlamycyc_best_hits_output.tsv`）。加えてNCBI `Arabidopsis_thaliana.gene_info` からAGIコード→シンボルの対応表（`agi2symbol.tsv`）を作成し、`awk`でJOINしてsymbol列を追加。 |
| GPMLファイルの取得元 | plantcycから得たデータをCyc_to_wikiを用いて変換したGPMLファイル|
| 発現データの有無 | 無し |

### オルソログ変換テーブルの実際の列構成

```
arabidopsis_gene_id	arabidopsis_symbol	chlamy_gene_id
```

- Arabidopsis側IDカラム：`arabidopsis_gene_id`（AGIコード、例: AT1G01090）
- 対象種側のIDカラム：`chlamy_gene_id`（例: CRE02.G099850_4532）
- 1:N対応の件数・傾向：
- IDマッピングが存在しなかった遺伝子の割合：

### 手順
1. Arabidopsis→Chlamydomonasの遺伝子対応表をRBH_plusを用いて作成。
2. refseqから入手したプロテオームFASTAではortholog抽出に成功したが、PMN由来・refseq由来いずれのmRNA FASTAでもほとんどorthologの出力ができなかった。
3. 遺伝子ID同士の対応を得ることが必要だったため、弓矢さんがggsearchを用いて配列類似性検索を実施してくださり、ortholog抽出に成功。
4. ggsearch36の検索結果TSV（`aracyc_to_chlamycyc_best_hits_output.tsv`）から`arabidopsis_gene_id`・`chlamy_gene_id`列を確認。
5. NCBI `Arabidopsis_thaliana.gene_info` をダウンロードし、`awk`でAGIコード（LocusTag列）→Symbol列を抽出して`agi2symbol.tsv`を作成。
6. `awk`で`agi2symbol.tsv`をキーにして、元のTSVの`arabidopsis_gene_id`列の直後に`arabidopsis_symbol`列を挿入し、`merged_with_symbol.tsv`を作成。
7. YAML（`ALACAT2_PWY_Ara.yaml`、`ALANINE-DEG3-PWY_2013a_Ara.yaml`）の`ortholog_resolver.provided_table.path`および`columns.source_symbol`をこのファイル・列名に合わせて設定。
8. `pathlift run configs/ALACAT2_PWY_Ara.yaml -o out_ALACAT2_PWY_Ara.gpml` を実行。
9. 実行は通ったが `GeneProduct: 0 / matched: 0 / 候補gene総数: 0` となり、変換対象が1件も検出されず。
10. GPMLファイルの中身を確認したところ、**GPML2013a形式ではなくGPML2021形式**（`type="GeneProduct"`が小文字、`<Xref identifier=".." dataSource="..">`という新属性名）であることが問題であると判明。pathliftが旧形式（`Type=`大文字、`Xref ID=`/`Database=`）を前提にパースしているためマッチ0件になったと推測。
11. 烏野さんが作成してくださった変換ツールを用いて、GPML2021形式のファイルをGPML2013a形式へダウングレード。
12. `ALACAT2_PWY.gpml`を変換したところ、中身が空になってしまった（変換時に何らかのデータが失われたことが原因と考えられる）。そのため、代わりに同ツールで変換した`ALANINE-DEG3-PWY_2013a.gpml`を使用したところ、GeneProductの認識はできたが、`GeneProduct: 6 / matched: 0 / unmapped: 6`となった。これは変換ツール自体の問題ではなく、対応表（`merged_with_symbol.tsv`）の中に、このパスウェイに含まれる6件の遺伝子IDが単純に存在しなかったためと考えられる。
    （今回は1つのGPMLファイルでしかテストできていないため、この変換ツールが他のパスウェイでも同様の問題を起こすのかは不明）

### 観察
- RBH_plusを用いて対応表を作成しようとしたがmRNA FASTAではorthologが数個しか出力されなかった。
- ggsearch36の出力にはシンボル情報が含まれないため、シンボルマッチング用には別途NCBI gene_infoのような外部の遺伝子ID⇔シンボル対応表を用意し、後からJOINする運用が必要だった。
- GPML2021からGPML2013aへのダウングレードも可能だが、Xref情報や新しいAnnotationが失われるなどの問題がある。

### 【設計へのフィードバック】
| 関連TODO | 気づき・修正が必要な設計判断 |
|----------|------------------------------|
| A-1 | GPMLのバージョン（2013a / 2021）をrecipe読み込み時に自動判定するか、非対応バージョンなら明示的にエラーを出す仕組みが必要（現状は無言で0件になる） |
| A-2 | pathliftがGPML2021に非対応であることが判明。対応の要否・工数を検討する必要がある |
| A-4 | ortholog対応表にsymbol列が最初から含まれていないケース（ggsearch36等の相同性検索ツール由来）のため、gene_info等からのsymbol補完を公式のワークフロー・スクリプトとして用意しておくことを検討|
| その他 | `source_gpml`のパスが見つからない場合のエラーと、列が見つからない場合のエラーが同じ「recipe検証に失敗」として並列に出るため、両方のエラーがある場合にどちらが根本原因か切り分けにくい。エラーメッセージに「ファイルパスを確認」「列名の大文字小文字を確認」等のヒントがあると良い |

---

## PoC #2 —（日付・テーマを記入）

### 目的

### 環境・データ

| 項目 | 内容 |
|------|------|
| 生物種 | |
| 使用ツール | |
| オルソログ対応表の出典・作成手法 | |
| GPMLファイルの取得元 | |
| 発現データの有無 | |

### オルソログ変換テーブルの実際の列構成

```
（実際のヘッダー行を貼り付ける）
```

- ヒト側のIDカラム：
- 対象種側のIDカラム：
- 1:N対応の件数・傾向：
- IDマッピングが存在しなかった遺伝子の割合：

### 手順

1.
2.
3.

### 観察

-

### 【設計へのフィードバック】

| 関連TODO | 気づき・修正が必要な設計判断 |
|----------|------------------------------|
| A-1 | |
| A-2 | |
| A-4 | |
| その他 | |

---


# マニュアルPoC: 2) カイコのパスウェイ変換

## PoC #0 — 2026-06-01：リソース確認（カイコ）

### 目的

- カイコ（*Bombyx mori*）のリフトオーバーに使用したリソースと手順を記録・整理する
- ミツバチのPoC #0で観察した変換フロー（7ステップ）がカイコでも同様に適用されるか確認する
- ミツバチより「込み入った判断が必要だった」という点の具体的な内容を記録し、設計に反映する

### 環境・データ

| 項目 | 内容 |
|------|------|
| 生物種 | カイコ（*Bombyx mori*） |
| 変換ターゲットのWPID | WP534, WP2453, WP500, WP4317, WP368, WP497（複数パスウェイを対象） |

**使用したリソース一覧**

| ファイル・リソース | 内容 | 出典 |
|-------------------|------|------|
| `FF4I-B_mori-protein.tsv` | ヒト↔カイコのメイン対応表（坊農先生の論文由来） | figshare doi: 10.6084/m9.figshare.19368137 |
| `node_integ_Bmori.ipynb` | ヒトとカイコの遺伝子を結合した表を作成するノートブック | — |
| WikiPathways participants / datanodes TSV | 変換元パスウェイのノード情報 | WikiPathways（ローカルclone） |
| NCBI TSA `ICPK01`（`ICPK01.1.fsa_nt.gz`） | カイコのリファレンス配列（SilkBaseから変更） | https://www.ncbi.nlm.nih.gov/Traces/wgs?val=ICPK01 |
| UniProtKB | ヒトのアミノ酸配列（tblastn クエリ用） | https://www.uniprot.org/ |
| Ensembl bioMart | Ensembl Gene ID → UniProt ID 変換（MANE Selectフィルタ） | — |
| TOGOID | EC番号（eccode）→ UniProt ID + taxonomy ID 変換 | — |
| `tblastn.sh` | tblastn実行スクリプト | — |
| `wikipathways_convert.ipynb` | eccode対応の変換コード（米澤さん作成） | — |
| PathVisio | GPMLファイルの編集 | — |

**ミツバチPoC #0との共通点：** ミツバチ対応表（`functional_annotation_transcript_Ac.tsv`）にも`B_mori-pid`列が存在するが、今回はカイコ専用の`FF4I-B_mori-protein.tsv`を使用。

### 手順

1. WikiPathwaysのparticipantsからdatanode TSVを取得する
2. `FF4I-B_mori-protein.tsv`（メイン対応表）でヒト→カイコの遺伝子対応を引く（`node_integ_Bmori.ipynb`で結合）
3. 対応表になかった遺伝子は以下のいずれかで補完する：
   - **通常ケース（geneID / Ensembl IDがIdentifier）：** Ensembl bioMartでEnsembl Gene ID → UniProt IDを取得（MANE Selectフィルタ） → UniProtKBでアミノ酸配列取得 → tblastn（クエリ：ヒト、DB：ICPK01 TSA nucl）で検索
   - **特殊ケース（IdentifierがEC番号のみ）：** TOGOIDでeccode → UniProt ID + taxonomy IDを取得 → taxonomyID:9606（ヒト）でフィルタ → 以降同様にtblastnで検索（`wikipathways_convert.ipynb`使用）
4. tblastn結果から遺伝子ごとの最小e-valueヒットを抽出し、カイコのgene IDを確定する
5. 複数ヒット・パラログ統一の判断を行い、ノードを書き換える（PathVisioで編集）

**※途中でリファレンスをSilkBase（タンパク質fasta）からNCBI TSA ICPK01（ヌクレオチド）に変更。それに伴いblastpからtblastnに切り替え。**

### 観察

**カイコ側のID体系：** KWMTBOMO* と MSTRG.* の2系統が混在（ミツバチと同様）。いずれも標準DBのIDではなく、プロジェクト固有ID。

**ミツバチより「込み入った判断」が必要だった点：**

1. **IdentifierがEC番号（eccode）のノードが存在する。**
   GPMLのIdentifierがgeneIDやEnsembl IDではなく酵素番号（例：`1.2.1.46`）のみのノードがあり、標準の変換フローが使えない。TOGOIDを経由する別ルートが必要（`wikipathways_convert.ipynb`）。

2. **リファレンスの途中変更。**
   当初SilkBaseのタンパク質配列（blastp）を使っていたが、NCBI TSA ICPK01（ヌクレオチド）に変更し、tblastnに切り替えた。この変更により手順・スクリプトが途中で更新されている。

3. **パラログ統一の判断が多い。**
   LDHA/LDHC/LDHAL6B → LDHB相当、ENO2/ENO3 → ENO1相当、HK1/HK2/HK3 → GCK相当など、複数の遺伝子シンボルが同一カイコ遺伝子にマップされるケースが多数。「どれを正とするか」の判断が手動で必要。

4. **no hitが出る遺伝子がある。**
   NAGS・GATM・GAMT（WP497）など、tblastnでもヒットがなく対応不能な遺伝子が存在する。

5. **1:N対応の処理。**
   PCK1（7hits）、PPP2R5A（5hits）等、複数ヒットから最適なものを選ぶ判断が必要。

**tblastn結果のID出力パターン（2系統）：**
- `KWMTBOMO*`系：`stitle`に `KWMTBOMO00773.mrna1` 形式で出現 → `KWMTBOMO00773` を抽出
- `MSTRG.*`系：`stitle`に `MSTRG.21962.8` 形式で出現 → そのまま抽出

### 【設計へのフィードバック】

| 関連TODO | 気づき・修正が必要な設計判断 |
|----------|------------------------------|
| A-4 | ミツバチ同様、カイコもKWMTBOMO*/MSTRG.*の非標準IDを使用。「対応表の列構成をRefSeq/Entrez Gene IDで固定する」設計は成立しない。ツールが受け入れるID体系を柔軟に定義する必要がある。 |
| A-2 | **IdentifierがEC番号のノードは別ルートが必要。** GPMLノードのIdentifierタイプ（geneID / Ensembl ID / eccode / その他）を事前に判定し、ルートを分岐させる処理が必要。これは自動判定できる可能性があるが、手動確認が介入するポイントでもある。 |
| A-2補足 | パラログ統一（複数遺伝子シンボル→1つに集約）とno hit（対応なし）の2パターンが手動判断の主な形態。ツールはこれらをリストアップして研究者に提示する設計が必要。 |
| A-1 | tblastnが必要なケースがある（カイコのリファレンスがヌクレオチドTSAのため）。blastpだけでなくtblastnもツールのオプション機能として検討が必要。リファレンスの種類（タンパク質fasta vs ヌクレオチドfasta）によって手法が変わる。 |
| A-1補足 | リファレンスの選択（SilkBase vs NCBI TSA）が作業中に変更されており、再現性に影響する。ツールはどのリファレンスを使ったかを記録・固定できる仕組みが必要。 |
| その他 | EC番号変換に使ったTOGOIDと`wikipathways_convert.ipynb`（米澤さん作成）は、ツール本体に組み込むか外部依存として扱うかを決める必要がある。 |

---
