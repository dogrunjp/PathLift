# パスウェイのliftover自動化ツール検討：　林さんのLift over仕様書（pathway-liftover-spec）を元にClaude sonnet4.6に設計の叩き台を考えてもらった

仕様書を読み込みリフトオーバーワークフローの性質をよく理解した上で、C4モデル風に整理します。

C4モデルは本来4階層（Context → Container → Component → Code）ですが、今回はツール設計の検討段階なので **Context・Container・Component** の3層で構造化し、分岐ポイントや外部リソース依存も明示します。では、C4モデル風の仕様図を3層に分けて描きます。

**Level 1 (Context)** から順に見ていきましょう。まずシステム全体と外部アクターの関係から。
![alt text](liftover_L1_context.svg)

次に **Level 2 (Container)**：ツールの内部構成と処理パイプラインです。
![alt text](liftover_L2_container.svg)

最後に **Level 3 (Component)**：マッピング解決モジュール（最も複雑な内部ロジック）の詳細です。---
![alt text](liftover_L3_mapping_component.svg)

図の補足と、テキスト仕様のまとめです。

---

## ツール仕様まとめ（C4モデル準拠）

### Level 1 — Context（システム文脈）

研究者がGPMLと設定パラメータを与えると、ツールが外部リソース（WikiPathways・NCBI/Ensembl・発現データ）と連携して変換済みGPMLを出力する。BLASTp（TODO:要検討.「配列類似性検索」のように抽象度を少し上げるべきでは. あるいは手法を確定すべきか.BLASTpとは限らないので.）を必要とするケースのみ手動介入が入る。

TODO: 手動介入の部分要検証
TODO: 研究者ノードでリソースの選択も研究者の責務になるのでは？
TODO: パラメータ（リソースとかID体系やrelation keyに利用する属性、ツールのパラメータなど）もう少し具体的に何が必要かここで記述すべき？？
memo: 入力として対応表があるならOK. 無ければ fanflow??

---

### Level 2 — Container（処理パイプライン）

| # | モジュール | 処理概要 | 自動/手動 |
|---|-----------|---------|----------|
| ① | 入力・フェッチ | WikiPathwaysからGPML取得、ノードTSV解析 | 自動 |
| ② | マッピング解決 | geneID→PID→対象種PID→geneID変換 | 自動（分岐あり） |
| ③ | ノード書き換え | Identifier / Database / Text Label更新 | 自動 |
| ④ | 発現データ照合 | ID対応確認、必要列追加 | 自動 |
| ⑤ | 未マップ遺伝子処理 | BLASTp候補提示 | **要手動レビュー** |
| ⑥ | 検証・レポート | カバレッジ率・未変換ノード一覧出力 | 自動 |
| ⑦ | GPML出力 | 投稿用ファイル生成 | 自動 |

TODO: 全体的に要検証. これでモジュールが十分か？自動化部分は本当に自動化可能か？
TODO: ノードの置き換えは手動になのではと思う（バイトの皆さんに確認する）。自動化が難しい部分と思うので
xmlの編集
---

### Level 3 — Component（マッピング解決の内部ロジック）

**設定として外部化すべきパラメータ（分岐の起点）：**

- `ortholog_source`：使用する対応表の種別（Ensembl PID / NCBI geneID / fanflow）
- `identifier_priority`：geneID優先 or transcriptID許容
- `expression_id_type`：発現ファイルのキー列（geneID / transcriptID / TPM列名）
- `blast_threshold`：BLASTp採用の同一性閾値（e値・identity%）

**主な分岐ポイント：**

1. 対応表にヒットするか → Yes: 自動変換 / No: BLASTpサブルーチンへ
2. BLASTpヒットの機能保存が確認できるか → 手動確認後、採否をツールに返す
3. 発現データのIDが合わないか → 自動的に対応列を補完するか警告を出す
---

### 設計上の重要な判断点

**「半自動」の境界線**として、BLASTpヒット後の機能確認だけは自動化せず、レビュー用の出力（ヒット配列・スコア・既知機能の注釈）を整形して研究者に提示する設計が現実的です。それ以外のステップは設定ファイル（YAMLやTSV）さえ用意すれば全自動化できます。

実装言語の候補としては、GPML操作・APIアクセス・ファイル処理を一括でこなせるPythonが最も適合します。次のステップとして、特定のモジュールの詳細設計や実装から始めたい部分があればお知らせください。


### 追記：関係者による現時点の印象のメモ

- 
