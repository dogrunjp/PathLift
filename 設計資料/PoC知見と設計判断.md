# PathLift 設計資料：PoC知見と設計判断

> この文書は PathLift の設計の**正本の中心**である。設計は机上でなく、3例の実データ PoC から導いた。
> 各設計判断には根拠となった観測を併記する。
>
> PoC前のドラフト（旧 `設計資料/仕様検討/`）はタグ `pre-poc-snapshot` に退避済み。本書に supersede された。経緯参照用。

最終更新の対象 PoC: WP5609×A.cerana / WP5277×B.mori / WP5601×B.mori。


## A. 3例 PoC サマリ

PathLift は「WikiPathways の GPML パスウェイを、オーソログ解決で別種へ lift する」ツールである。3例は、種・経路ドメイン・対応表・source IDタイプを意図的にばらして選び、設計の一般性を叩いた。

| 項目 | PoC#1 WP5609 | PoC#2 WP5277 | PoC#3 WP5601 |
|---|---|---|---|
| 経路名 | メラノーマ関連代謝 | Steroid hormone precursor biosynthesis | Caffeine in blood vessels |
| 経路ドメイン | 代謝 | 代謝（ステロイド） | シグナル（血管） |
| target 種 | A. cerana japonica | B. mori | B. mori |
| 対応表 | FunFlow (figshare 27175734) | FF4I (figshare 19368137) | FF4I (figshare 19368137) |
| 候補ID系 | MSTRG / g（アセンブリ） | KWMTBOMO（SilkBase 遺伝子モデル） | KWMTBOMO（SilkBase 遺伝子モデル） |
| **source IDタイプ** | Entrez / HGNC / EC | **UniProt** | **Ensembl** |
| 記号導出の経路 | gene_info(Entrez) / HGNC直 | **TextLabel** | **TextLabel** |
| txgene 畳み込み | GTF（FunFlow GTF） | **パターン**（KWMTBOMO） | **パターン**（KWMTBOMO） |
| GeneProduct 数 | 38 | 13 | 33 |
| matched | 31（82%） | 7（54%） | 23（70%） |
| unmapped | 7 | 6 | 10 |
| 候補gene総数 | 72 | 12 | 68 |
| **展開率**（候補/matched） | **2.3** | **1.7** | **3.0** |
| 要したコード変更 | （基準実装） | txgene に KWMTBOMO 追加 | **なし** |

この表が以降の各節の土台になる。重要なのは、**3経路・2種・3 IDタイプを、コード変更わずか1箇所で通した**こと（B章）。そのうえで、マッチ率・展開率・MISSの素性は経路ごとに大きく異なり、その差が「アセット構造」と「経路の生物学」に分解できた（C〜E章）。


## B. 境界（recipe）の汎用性 — 検証結果

**設計判断：policy（人間の判断）と mechanism（決定的なランタイム）の境界を recipe ファイルに引く。この境界は妥当である。**

3例を通すのに要した差分を仕分けると、ほとんどが recipe で吸収され、コード変更は1箇所に限られた。

recipe で吸収（コード変更なし）:
- **対応表の列名**：`columns.{target_id, source_symbol, source_pid}` の値差し替えのみ。FunFlow（`ProteinID`/`H_sapiens-gene_symbol`/`H_sapiens-pid`）と FF4I（`B_mori-pid`/`H_sapiens-gsymbol`/`H_sapiens-ENSPID`）は列名の流儀が違うが、構造（1行＝target蛋白＋人側キー）は同じ。
- **gene_info の再利用**：source は全例ヒトなので `Homo_sapiens.gene_info` を共有。記号正規化は source 側の話で target 種に依存しない。
- **routes**：全例 `symbol` のみ有効。
- **GTF の有無**：B.mori は GTF を書かず（省略）= パターン畳みに自動で切り替わる（F章）。
- **source_gpml**：パスのみ。

コード変更を要した差分（1箇所）:
- **txgene に SilkBase パターン追加**（`KWMTBOMO#####.mrnaN → KWMTBOMO#####`）。

既存実装が無改修で吸収した差分:
- **source IDタイプの多様化**（UniProt / Ensembl）。`_symbol()` の「Entrez/HGNC以外は TextLabel」フォールバックが効いた（E章。ただしこれは潜在リスクでもある）。
- **ノード単位の source ID 読み**。経路内で IDタイプが割れても per-node で処理できる。

> **結論**：境界は機能した。「下流はパス探索も判定もせず、検証済み recipe からすべてを受け取る」という原則が、3例の差分の大半を policy 側（recipe 記述）に閉じ込めた。


## C. MISS の分類と支配機構

3例で MISS（unmapped）の素性を切り分けた結果、**4カテゴリ**に整理できた。そして WP5601 で、想定外の機構が**支配的**であることが分かった。

### C-1. 4カテゴリ

- **(a) 真の不在**：target 種にオーソログが存在しない。生物学的に正常な MISS。
  - 例：WP5277 のステロイド生成 CYP（CYP11A1 / CYP17A1 / CYP21A2）。これらは脊椎動物特異で、カイコに綺麗な直系がない。
- **(b) パラログ × 表カーディナリティ【支配的】**：後述。
- **(c) 綴り / synonym 違い**：記号だが対応表の `H_sapiens-gsymbol` と表記が違う。curation で救済可能。
  - 例：`GUCY1A3` は近年 `GUCY1A1` に改名。表が新名で持てば旧名ノードは落ちる。
- **(d) ラベル非記号【潜在】**：source ノードのラベルが遺伝子記号でない（複合体名・状態表記・代謝物名など）。3例とも**未観測**だが、E章の理由で潜在的に存在する破綻モード。

### C-2. 支配機構：パラログ × 表カーディナリティ

WP5601（シグナル系）の MISS 10件を割り出すと、**パラログ族に集中し、族内で部分的**だった。

| 族 | source ノード数 | matched | unmapped |
|---|---|---|---|
| ADCY（アデニル酸シクラーゼ） | 9 | 8 | 1（ADCY4） |
| ADRA1（α1アドレナリン受容体） | 3 | 1 | 2 |
| ADORA（アデノシン受容体） | 3 | 1 | 2 |
| PDE（ホスホジエステラーゼ） | 5 | 3 | 2 |
| GUCY1（可溶性グアニル酸シクラーゼ） | 3 | 1 | 2 |
| RYR | 2 | 1 | 1（RYR2） |
| 単独遺伝子（MYLK, NOS3, CALM×3, PPP1×3 等） | — | 全マッチ | 0 |

機構：**FF4I 表は「1 target蛋白 ＝ 最良の人記号1つ」という precision 優先の割り当て**である。target 種の族メンバー数は人より少ないので、カイコに K 個の遺伝子があれば表には K 個の人記号しか載らない。残る N−K 個の人パラログは、**族の親戚（matched 兄弟）が存在するのに**、表に自分の記号が無くて落ちる。

つまり (b) の MISS は、生物学的不在でもラベル不良でもなく、**「対応表の 1-best 割り当て」と「source 側のパラログ展開」の衝突**である。落ちた人パラログは、本来はマッチした兄弟が指す target 遺伝子に寄せられるべきもの。

### C-3. recall優先 vs 表 precision優先 という構造的緊張

**これは PathLift の思想に直結する重要な発見である。**

- PathLift の思想は **recall 優先**（絞らず全候補を出し、選別は後段の発現データに委ねる）。
- ところが FF4I のような対応表は **precision 優先**（1 target に 1-best の人記号）。
- したがって **symbol ルートの recall 上限は、対応表のカーディナリティに縛られる**。表が precision 優先である限り、PathLift がいくら「全候補を出す」と言っても、表に載っていないパラログは出せない。

この緊張の解消策が、保留中の **compute ルート（blastp/tblastn）**である。落ちた人パラログ蛋白を直接 target ゲノム/TSA に当てれば、表の 1-best を超えて族メンバーを回収できる。これは**バイト氏が手動でやっていたこと**そのものである（`開発管理/手動PoC記録.md`：「LDHA/LDHC/LDHAL6B → 対応済み LDHB と同一」「HK1/2/3 → GCK と同一」）。

> **設計判断**：compute ルートは「あれば便利」ではなく、**recall 優先の思想を表ルート単独では達成できないことの構造的な帰結**として位置づける。表ルート＝高速・高precisionだが recall に上限。compute ルート＝表の上限を超える recall 回収。両者は補完。


## D. 展開 magnitude の二要因モデル

**設計判断：「lift で候補が何倍に膨らむか」は一般則化せず、二要因で説明する。**

PoC#1 で「変換すると約2倍に膨らむ」と観測したが、3例で展開率がばらけた（2.3 / 1.7 / 3.0）。これは次の二要因の積で決まる。

1. **対応表の粒度**
   - transcript / アセンブリ断片レベル（MSTRG.x.y, g####）→ フラグメント水増しで膨張。WP5609 で MLST8→6遺伝子・SLC2A1→5遺伝子のような暴れが出た。
   - gene-model レベル（KWMTBOMO、1行＝1遺伝子の精選表）→ そもそも膨らみにくい。WP5277/WP5601 は外れ値的な暴れがない。
2. **経路のパラログ密度**
   - 大きな族が並ぶ経路（シグナル系：ADCY1〜9, PDE, ADORA…）→ 1記号が target の複数遺伝子に当たり膨張。WP5601=3.0。
   - 小さな族の経路（ステロイド代謝酵素）→ 穏当。WP5277=1.7。

3例の対比がこれを実証する：

| | 表の粒度 | 経路パラログ密度 | 展開率 |
|---|---|---|---|
| WP5609 | アセンブリ（粗い） | 中（代謝） | 2.3（一部暴れ） |
| WP5277 | gene-model（精選） | 小（ステロイド酵素） | 1.7 |
| WP5601 | gene-model（精選） | 大（シグナル族） | 3.0 |

> **結論**：「倍化」は WP5609 固有の現象であり、表の粒度と経路の生物学に依存する。設計資料・ユーザ向け説明では、展開率を固定値で約束しない。


## E. source ID の多様性と TextLabel 依存

**設計判断：記号導出は source IDタイプに依存し、非 Entrez/HGNC では TextLabel 依存になる。これは現状の許容前提だが、潜在リスクとして明記する。**

3例で source の IDタイプが3種類に割れた：

| | source IDタイプ | gene_info が効くか | 記号導出 |
|---|---|---|---|
| WP5609 | Entrez Gene / HGNC | ○（Entrez→記号） | gene_info / ID直 |
| WP5277 | UniProt (Uniprot-TrEMBL) | × | **TextLabel** |
| WP5601 | Ensembl (ENSG) | × | **TextLabel** |

`_symbol()` の分岐は「Entrez→gene_info、HGNC→ID直、それ以外→TextLabel」。gene_info は Entrez GeneID をキーにするので、**UniProt も Ensembl も gene_info を迂回して TextLabel に落ちる**。つまり **3例中2例が、記号導出を完全にラベル頼みにしていた**。

3例とも通ったのは、**WikiPathways 作成者がラベルに綺麗な遺伝子記号を使い、非遺伝子エンティティ（cAMP, Ca²⁺, caffeine 等）を Metabolite 型にしていた**おかげである。ツールが堅牢だからではない。

> **リスク**：ラベルが記号でない経路（複合体名・状態表記など）では、UniProt/Ensembl ノードの記号導出が破綻する（MISS分類 (d)）。これは実証された失敗ではなく潜在リスク。
>
> **堅牢化の選択肢（将来）**：UniProt/Ensembl → 公式記号 の対応を足す（gene_info の xref 列、または BridgeDb 的対応表）。これにより非 Entrez/HGNC でもラベルに依存せず記号導出できる。


## F. txgene 畳み込みの一般化

**設計判断：transcript→gene の畳み込みは「GTF」か「IDパターン」かをアセットに応じて選ぶ。将来は recipe で明示指定できるようにする。**

観測:
- WP5609（A.cerana）：FunFlow の GTF が MSTRG/g の ID と噛むので、GTF で畳み込み。
- WP5277/WP5601（B.mori）：入手できた GTF は `GCF_030269925.1`（RefSeq）で、`gene_id="LOC#####"`/`transcript_id="XM_…"` 系。対応表の `B_mori-pid`（KWMTBOMO）と**ID系統が異なり噛まない**。→ GTF を使わずパターン畳み（`KWMTBOMO#####.mrnaN → KWMTBOMO#####`）。

さらに**畳み込み粒度に作業者差**がある：
- PathLift：`MSTRG.x.y → MSTRG.x`（gene 単位に畳む）。
- バイト氏の手動 awk：`MSTRG.21962.8` を**そのまま**保持（畳まない）。

今回の表は全 KWMTBOMO のため MSTRG 粒度問題は不発だったが、将来 compute ルートで MSTRG 候補が入ると再浮上する。

> **設計判断**：
> 1. txgene は GTF とパターンの2モードを持つ（実装済み：GTF が無ければパターンに自動フォールバック）。
> 2. どちらを使うか・パターンの畳み込み粒度を、ハードコードでなく **recipe で指定可能にする**（将来拡張）。これにより「target アセットごとに変わる畳み込み規約」を policy 側へ寄せられる。


## G. 未解決点・次段階

| 項目 | 状態 | メモ |
|---|---|---|
| 座標/レイアウト規則 | 保留 | 現状は線形オフセット (24,16)。放射状/格子＋ボードクランプ案。他作業者の意見待ち。BoardWidth/Height は経路ごとに異なる |
| compute ルート実装 | 未実装 | blastp/tblastn を参照DBの型（蛋白/核酸）で切替。C-3 の recall 回収手段。policy=augment のゲート |
| ④ 発現リンカ実装 | 未実装 | TPM に gene_id 列を足すだけの薄い役。選別は QPX notebook（PathLift外）。txgene を共有 |
| MSTRG 畳み込み粒度 | 未決 | F章。compute ルートで MSTRG 候補が入ると再浮上 |
| UniProt/Ensembl→記号マップ | 未着手 | E章。ラベル依存の堅牢化 |
| MISS (b)(c) の curation 回収 | 運用課題 | パラログ落ち・綴り違いを override で兄弟target に寄せる |
| GraphId 発番 | 実装済 | `[a-f][0-9a-f]{4}` 規則準拠・既存IDと衝突回避。旧 `_lpN` 枝番は廃止 |
| unmapped の記号記録 | 実装済 | `unmapped: <記号> (no hit)`。MISS 同定が grep 一発に |
| 未対応IDの検知 | 実装済 | stats に `記号ラベル依存`（非Entrez/HGNC）と `txgene未対応`（畳めなかったID）を出す。下記 G-1 の穴に気づくため |

### G-1. 特殊ID の穴（既知）

新しい種・経路を通すとき、**未対応のIDが黙って品質を落とす**箇所が2つある。エラーにならないのが厄介。

- **source 側に新 IDタイプ**（RefSeq, MGI 等）：`_symbol()` で「Entrez/HGNC 以外」に落ち、記号導出が **TextLabel 依存**になる（E章）。ラベルが記号でない経路では黙って MISS する。
- **target 側に新パターン**（別アセンブリの `BMSK_######` 等）：`txgene` が畳めず**転写物IDのまま残り**、同一遺伝子の転写物が別候補として**重複展開**される。

対策：(1) **検知は実装済**（stats の `記号ラベル依存` / `txgene未対応`。0 でなければ要注意）。(2) 根治は **txgene の畳み込みパターンを recipe で指定可能にする**（F章の一般化）＋ **UniProt/Ensembl→記号マップ**（E章）。新種対応をコードでなく policy 側へ寄せる。

### G-2. 将来構想：RBH+inparalog による対応表の自前生成（compute / ⑤）

現状 PathLift は**外部の対応表を消費する**（FunFlow/FF4I）。これが C 章の支配的 MISS（パラログ × 表カーディナリティ）の原因＝表の「1 target＝1-best 人記号」が族メンバーを落とす。

構想：**DIAMOND の RBH（相互ベストヒット）＋ inparalog 展開で、source↔target の対応表を PathLift 自身が生成する**。多対多で族を取りこぼさないため、recall 優先の思想と初めて整合する。バイト氏の手動「LDHA/LDHC→LDHB」（`開発管理/手動PoC記録.md`）の体系的自動化に当たる。

収まりどころ：表生成は重い前処理なので、ランタイム（①②③④）の外に新コンポーネント **⑤オーソログ表ビルダ** として立て、生成物を `provided_table` として recipe に食わせる。**生成器と消費器を分ければ、③解決器は表の出自（FF4I か自前RBH か）を問わず不変**。今の境界設計の利益がそのまま効く。

※ これは C4 に L2 コンテナを1つ足す規模の設計変更（DIAMOND の重い依存を伴う）。着手時は CLAUDE.md の手順どおり**設計資料の変更について承認を取る**こと。本節は置き場所の確保のみ。


## 関連文書

- `pathway-liftover-spec.md` — 正規仕様（何をするか）
- `recipe.schema.md` — recipe / curation サイドカーのスキーマ
- `c4_model.md` + `pathlift_c4_l3_after_implementation.svg` — コンポーネント構成
- `conversion_flow.md` — ランタイムの変換フロー
- `開発管理/手動PoC記録.md` — バイト氏の手動 lift 記録（C-3 の一次資料）
