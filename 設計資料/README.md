# PathLift 設計資料

PathLift の設計は **3例の実データ PoC から導いた**。本ディレクトリがその正本である。

## 読む順序

1. **`PoC知見と設計判断.md`** — 正本の中心。3例から導いた経験則と設計判断（A〜G章）。まずこれ。
2. `pathway-liftover-spec.md` — 正規仕様（何をするか・入出力契約・スコープ）。
3. `recipe.schema.md` — recipe / curation サイドカーのスキーマ。
4. `c4_model.md` + `pathlift_c4_l3_after_implementation.svg` — コンポーネント構成。
5. `runtime_flow_and_branching.md` — ランタイムの実行時フロー・設定分岐（mermaid）。旧`conversion_flow.md`。

関連：`../開発管理/手動PoC記録.md`（バイト氏の手動 lift 記録。MISS の支配機構を説明する一次資料）。

## PoC 前ドラフトについて

PoC 前の検討（旧 `設計資料/仕様検討/`：`c4_model_draft` / `conversion_flow_draft` / `pathway-liftover-spec` / `仕様書作成までのTODO`）は、本資料に supersede された。

経緯参照用に、退避時点のスナップショットをタグ **`pre-poc-snapshot`** に保存してある（ドラフトブランチ `draft/pre-poc` も）。当時の検討を見るには：

```
git show pre-poc-snapshot:設計資料/仕様検討/pathway-liftover-spec.md
# または
git switch draft/pre-poc
```

## 設計の3行サマリ

- 境界（recipe）は機能した：3経路・2種・3 IDタイプを**コード変更1箇所**で通した。
- MISS の主因は生物学的不在でなく **パラログ × 表カーディナリティ**。recall優先の思想と表のprecision優先が構造的に緊張し、compute ルートがその解。
- 展開率・マッチ率は経路依存（**アセット粒度 × パラログ密度**）。固定値で約束しない。
