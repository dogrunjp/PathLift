# PathLift コンポーネント構成（C4 Level 3）

> 図：`pathlift_c4_l3_after_implementation.svg`（実装反映版）。
> 旧 `仕様検討/c4_model_draft.md` を supersede。根拠は `PoC知見と設計判断.md`。

PathLift は1つの CLI コンテナ。内部のコンポーネントと、境界となる recipe、外部ストアの関係を C4 Level 3（コンポーネント図）で表す。

## コンポーネント

| # | コンポーネント | 責務 |
|---|---|---|
| ① | レシピローダ（`recipe.py`） | recipe を検証し config を返す。失敗ならランタイムに入れない |
| ② | パスウェイ変換器（`transform.py` + `gpml.py`） | GPML I/O・全体主導・ノード展開・配置。エントリ（`cli.py`）から組み立て |
| ③ | オーソログ解決器（`ortholog.py`） | source ノード→候補集合（provenance付き）。絞らず全候補 |
| ④ | 発現リンカ（**未実装**） | TPM に結合キー（gene_id）列を足すだけの薄い役 |
| 共有 | txgene（`txgene.py`） | transcript→gene 畳み込み。③（と将来④）で共有。GTF or パターン |
| — | models（`models.py`） | データ構造（候補・解決結果・Route 等） |

## 境界

- **recipe（+ curation サイドカー）** が policy/mechanism の境界。人間の判断（どの表・どの列・どのルート・手動対応）を recipe に閉じ込め、ランタイムは検証済み config だけで決定的に動く。
- **gene_info / 対応表 / GTF / TPM** は外部ストア。recipe がパスで指す。

## 実装で確定した2点（PoC反映）

1. **txgene はデータストア（GTF）の辺ではなく、独立コンポーネント**になった。GTF はそれが読む元ストアで、GTF が無ければパターン畳みに落ちる。③（将来④も）が共有する。
2. **④発現リンカの責務が縮小**。「候補に発現を付与・選別の主役」ではなく「TPM に gene_id 列を足すだけ」。選別の主役は **QPX notebook（PathLift 外）** に移った。②からの呼び出しは無く、出力（拡張TPM）と lift 済み GPML が QPX へ合流する。

詳細は SVG 図を参照。
