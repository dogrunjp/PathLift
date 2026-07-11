# CLAUDE.md / AGENTS.md

> AI エージェント（Claude / Codex 等）への指示。`AGENTS.md` は本ファイルへの symlink。

## 最優先原則：設計資料が権威

実装は **`設計資料/` に書かれた仕様に従う**こと。とくに次の2つが規範（normative）である。実装より仕様が上位にある。

1. **`設計資料/c4_model.md`**（+ `pathlift_c4_l1_context.svg` / `pathlift_c4_l2_container.svg` / `pathlift_c4_l3_after_implementation.svg`）
   — システム文脈・コンテナ・コンポーネントの構成、境界、各責務。
2. **`設計資料/pathway-liftover-spec.md`**
   — 何をするか、入出力契約、スコープ（するこ と／しないこと）。

設計の**根拠**は **`設計資料/PoC知見と設計判断.md`**（3例の実データ PoC から導いた）。判断に迷ったら、まずこれを読むこと。

## 矛盾が生じたときの手順（重要）

実装の都合で、どうしても上記 `c4_model.md` / `pathway-liftover-spec.md` の仕様と**矛盾する**場合：

1. **勝手に逸脱しない。** まず仕様どおりに実装できないかを検討する。
2. それでも矛盾が避けられないなら、**`c4_model.md`（必要なら spec も）を修正または追記する必要がある**。
3. ただし設計資料を変更する前に、**必ず人間に「この設計変更で良いか」を尋ねる**こと。承認を得ずに設計資料を書き換えてはならない。
4. 承認された変更は、**なぜ当初設計から変えたかの理由を併記**して設計資料へ反映する。

要約：**仕様を守る → 守れないなら設計資料を直す（要・人間承認）→ 理由を残す**。実装が黙って仕様から外れる状態を作らないこと。

## 開発の役割分担

- **設計・アーキテクチャ**（設計資料の作成/改訂、C4、仕様判断）は Web Claude。
- **実装**（コード変更）は Codex。実装時は本ファイルの最優先原則に従い、設計資料を規範として扱う。

## プロジェクト構成

```
PathLift/
├── pathlift/            # コード(パッケージ)。models / txgene / ortholog / gpml / transform / recipe / cli
├── configs/            # recipe + curation サイドカー
├── spike/              # 調査用スクリプト
├── 設計資料/            # ★権威。下記「読む順序」参照
├── 開発管理/            # セッションログ・手動PoC記録・mermaid凡例
├── resource/           # 大容量入力(gitignore)
└── pyproject.toml      # PyYAML 依存 + console_scripts: pathlift=pathlift.cli:main
```

### 設計資料を読む順序
1. `PoC知見と設計判断.md`（正本の中心・根拠）
2. `pathway-liftover-spec.md`（正規仕様）
3. `recipe.schema.md`（recipe/curation スキーマ）
4. `c4_model.md` + 3つの SVG（構成）
5. `runtime_flow_and_branching.md`（ランタイムフロー・設定分岐。旧`conversion_flow.md`）

### 実行
```
pip install -e .            # または依存だけ: pip install pyyaml
pathlift run configs/<recipe>.yaml -o out.gpml
```
相対パスは **recipe ファイルのディレクトリ基準**で解決される。

## 不変条件（実装で壊さないこと）

- ランタイムはパス探索も判定もしない。すべて検証済み recipe から受け取る（policy/mechanism 境界）。
- 解決は絞らず**全候補・和集合**（recall 優先）。選別は QPX notebook（PathLift 外）。
- 新規ノードの GraphId は `[a-f][0-9a-f]{4}` 規則準拠・既存IDと衝突回避。
- 出力 GPML は source と同じ GPML(2013a)。

## 履歴

- PoC 前の設計ドラフトはタグ **`pre-poc-snapshot`**（ブランチ `draft/pre-poc`）に退避。現行の `設計資料/` がこれを supersede。
