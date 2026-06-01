# 変換フロー分岐ダイアグラム（作業版）

PoCの観察（ミツバチ・カイコ）をもとに、ノード1件あたりの変換フローを整理する。
どこが共通でどこが分岐するかを可視化することで、A-2・A-4・A-6の設計判断の基盤とする。

確定後は`設計資料/`直下の正本に移動する。

---

## フローの対象範囲

- **入力：** WikiPathways GPMLパスウェイ（ヒト）の各DataNode
- **出力：** DataNodeに書き込む対象種のID（geneID優先、transcriptID許容）
- **ループ単位：** DataNode 1件ごとに以下のフローを実行する

---

## 変換フロー図

```mermaid
flowchart TD
    START([DataNode 1件の処理開始]) --> ID_TYPE

    ID_TYPE{"XREF Identifierタイプ\nGPMLのDatabase属性で判定"}
    ID_TYPE -->|"geneID / Ensembl ID\n（標準ルート）"| LOOKUP
    ID_TYPE -->|"EC番号（eccode）\n（特殊ルート）"| TOGOID["TOGOIDで\neccode → UniProt ID 変換\ntaxonomyID:9606でヒトにフィルタ"]
    ID_TYPE -->|その他| UNKNOWN["未定義ルート\n要設計【A-6】"]
    TOGOID --> LOOKUP

    LOOKUP["対応表で\nヒトID → 種PIDを照合"]
    LOOKUP --> LOOKUP_R{"照合結果"}

    LOOKUP_R -->|"1:1 対応あり"| SPECIES_ID["種のIDを取得"]
    LOOKUP_R -->|"1:N（パラログ・アイソフォーム）"| PARALOG["手動判断：統一候補を\nリストとして研究者に提示"]
    LOOKUP_R -->|"対応なし"| BLAST_PREP

    PARALOG --> SPECIES_ID

    BLAST_PREP["UniProtから\nヒトのアミノ酸配列を取得"]
    BLAST_PREP --> REF_TYPE{"対象種リファレンス\n配列の種別【A-1】"}
    REF_TYPE -->|"タンパク質 fasta"| BLASTP["blastp"]
    REF_TYPE -->|"ヌクレオチド fasta / TSA"| TBLASTN["tblastn"]

    BLASTP & TBLASTN --> BLAST_R{"BLAST結果"}
    BLAST_R -->|ヒットあり| MANUAL["手動確認：\nヒト遺伝子と機能同等か判断"]
    BLAST_R -->|ヒットなし| UNMAPPED["未マップとして記録\n（変換スキップ）"]

    MANUAL --> SPECIES_ID

    SPECIES_ID --> GENEID_R{"種geneIDに\n変換できるか【A-4】"}
    GENEID_R -->|"可能\n（NCBI protein等で変換）"| GENEID_OK["geneIDを使用"]
    GENEID_R -->|"不可\n（geneIDが存在しない／\n発現データと一致しない）"| TRANSCRIPT_FB["transcriptIDで代替\n（フォールバック）"]

    GENEID_OK & TRANSCRIPT_FB --> REWRITE["GPMLノードを書き換え\nIdentifier / Database / TextLabel"]

    REWRITE --> EXP{"発現データを\n使用するか（任意）"}
    EXP -->|なし| DONE
    EXP -->|あり| EXP_R{"発現データのIDと\n照合できるか"}
    EXP_R -->|"可能"| DONE(["次のノードへ / 完了"])
    EXP_R -->|"不可"| ADD_COL["発現データに\ngeneID列を追加して照合"]
    ADD_COL --> DONE
    UNMAPPED --> DONE
```

---

## 補足：NCBIのID同士で直接対応できる場合

上図の「対応表でヒトID → 種PIDを照合」の箇所は、対応表の中身によって処理が変わる。

| 対応表の型 | ヒト側キー | 種側の値 | 変換ステップ |
|-----------|-----------|---------|-------------|
| **標準型**（PoC実績） | Ensembl protein ID（ENSP*） | 種固有PID（MSTRG*等） | 種PID → geneID変換が別途必要 |
| **NCBI直接型**（未確認） | Entrez Gene IDまたはRefSeq NP_xxx | 種のEntrez Gene ID | geneIDがそのまま得られる（変換不要） |
| **fanflow出力型** | Ensembl protein ID | 複数種のPIDを1テーブルに収録 | 上記「標準型」と同様の変換が必要 |

「NCBI直接型」が実際に存在するかはPoC未確認。A-4の設計判断で整理する。

---

## 主要な分岐点の一覧

| 分岐ID | 条件 | 選択肢 | 関連TODO |
|--------|------|--------|---------|
| D-1 | GPMLのIdentifierタイプ | geneID/Ensembl ID / EC番号 / その他 | A-6 |
| D-2 | 対応表での照合結果 | 1:1 / 1:N（パラログ） / 対応なし | A-4 |
| D-3 | BLASTリファレンス種別 | タンパク質fasta / ヌクレオチドfasta(TSA) | A-1 |
| D-4 | BLAST結果 | ヒットあり / ヒットなし | A-2 |
| D-5 | 種geneIDへの変換可否 | 可能 / 不可（transcriptIDで代替） | A-4, A-6 |
| D-6 | 発現データとのID照合 | 一致 / 不一致（列追加） | A-6 |

---

## 手動介入が必要なポイント

| ステップ | 手動介入の内容 | 自動化の可否 |
|---------|--------------|-------------|
| D-2（1:N） | パラログ統一：どの遺伝子を代表として使うか選択 | 困難（生物学的判断が必要） |
| D-4（ヒットあり） | BLAST結果の機能同等性確認 | 困難（機能アノテーション確認が必要） |
| D-2（対応なし）→D-4（ヒットなし） | 未マップ遺伝子の最終扱いを決定 | 困難（研究者の判断が必要） |
| REWRITE | PathVisio等でのGPMLノード編集 | 要確認【B-2】 |

---

## 未解決・要設計の箇所

- **D-1「その他」ルート：** EC番号以外の特殊Identifierタイプへの対応は未設計。
- **対応表の型の自動判定：** ツールが対応表の型（標準型/NCBI直接型/fanflow出力型）を自動で識別できるか、または設定ファイルで指定させるかは未決（A-6）。
- **ノード書き換えの自動化：** PathVisioを使った手動編集を自動化できるかは未確認（B-2）。
