# GPML ネットワーク化 & 再レイアウト ツール

GPML（WikiPathways / PathVisio 形式）のパスウェイを扱う2本のスクリプト。

| スクリプト | 役割 |
|---|---|
| `gpml2network.py` | GPML を ノード/エッジ の **ネットワーク** に変換（TSV・GraphML 出力） |
| `gpml_layout.py` | ネットワーク情報から **BFSレイアウト座標** を計算し、`CenterX/CenterY` と エッジの接続辺 `RelX/RelY` を GPML に**書き戻す** |

`gpml_layout.py` は内部で `gpml2network.py` を import するので、**2ファイルは同じディレクトリ**に置く。

## 依存関係

- Python 3.10 以上（`X | None` 記法を使用）
- `networkx`（GraphML 出力・レイアウトで必須）
- 描画は任意（`matplotlib`。スクリプト本体では使わない）

```bash
pip install networkx
```

---

## クイックスタート

```bash
# 1) ネットワーク（エッジリスト）を見る
python3 gpml2network.py pathway.gpml

# 2) 再レイアウトして GPML に書き戻す（CenterX/CenterY と 接続辺 RelX/RelY を更新）
python3 gpml_layout.py pathway.gpml --write-gpml pathway_relayout.gpml

# 3) ノード座標を TSV で確認しつつ書き戻す
python3 gpml_layout.py pathway.gpml --write-gpml out.gpml --nodes-out nodes.tsv
```

---

## gpml2network.py

### 変換ルール

1. ネットワークを GPML(XML) から変換する。
2. Interaction の二つの Point を結んでエッジにする。ノード名は `GraphRef`（= `GraphId`）。
3. Interaction の端点のいずれかが **Anchor を参照する場合はエッジ化しない**（酵素→反応 の catalysis などを除外し、ノード同士の関係だけを残す）。

> ルール3で残るのは「両端が実ノードの Interaction」。代謝変換だけでなく `gene → protein` のような関係も含む（種類の区別は `gpml_layout.py` 側で行う）。

### CLI

| 引数 | 説明 |
|---|---|
| `input` | 入力 GPML（必須） |
| `-o, --output PATH` | エッジリスト(TSV)の出力先（省略時は標準出力） |
| `--graphml PATH` | GraphML を出力（networkx 経由） |
| `--labels` | GraphML のノード名を `TextLabel` にする（既定は GraphId） |
| `--quiet` | サマリ（stderr）を抑制 |

サマリは stderr に出るので、TSV をパイプしても混ざらない。

### 出力フォーマット

**エッジリスト TSV**：`source_id  target_id  source_label  target_label  interaction_id  arrowhead`

**GraphML**：有向グラフ。ノード属性に `label / type / xref_db / xref_id`（レイアウト後なら `x / y` も）、エッジ属性に `interaction_id / arrowhead`。

### ライブラリとして使う

```python
import gpml2network as g2n

parsed = g2n.parse_gpml("pathway.gpml")

parsed.nodes          # {GraphId: Node(label, node_type, xref_db, xref_id, group_ref, width, height, x, y)}
parsed.anchors        # {GraphId: Anchor(graph_id, interaction_id, position)}
parsed.interactions   # [Interaction(graph_id, start_ref, end_ref, arrowhead)]  ※全Interaction
parsed.groups         # {group GraphId: {"group_id":..., "members":[GraphId,...]}}
parsed.edges          # [Edge(source, target, interaction_id, arrowhead)]  ※anchor非参照のみ
parsed.skipped        # [(interaction_id, [endpoints], 除外理由)]

parsed.anchor_ids          # set(anchorのGraphId)
parsed.interaction_by_id   # {GraphId: Interaction}
```

`Node.x / Node.y` は `gpml_layout.bfs_layout()` を呼ぶと埋まる。

---

## gpml_layout.py

### レイアウトの流れ

1. **分類** — Interaction を種類別に分ける（下表）。
2. **背骨(BFS)** — `conversion` だけでグラフを作り、入次数0のノードを起点に BFS レイヤ配置。ルートは `--root` で上書き可。
3. **サテライト配置** — 各 anchor（反応中心）について、親の変換線から反応軸を作り、酵素・共基質・共生成物を軸まわりに置く（酵素と副基質は反対側、基質=上流／生成物=下流）。
4. **遺伝子配置** — `gene → protein` は、対応タンパク質から反応中心の逆方向へ押し出す。
5. **group 展開** — 複合体はメンバーを縦に展開。
6. **接続辺の最短化** — 各エッジを、両端ノードの位置関係から最寄りの辺に付け替える（次項）。

### Interaction の分類

| 種類 | 条件 | 配置 |
|---|---|---|
| `conversion` | 両端が実ノードで、`mim-transcription-translation` 以外 | 背骨（BFS） |
| `translation` | 両端が実ノードで `mim-transcription-translation` | 遺伝子→タンパク質 |
| `catalysis` | 片端が anchor、相手が **非metabolite**（protein/gene/group） | 反応軸の片側に酵素 |
| `reactant` | 片端が anchor、相手が **metabolite** で `node → anchor` | 反応の反対側・上流 |
| `product` | 片端が anchor、相手が **metabolite** で `anchor → node` | 反応の反対側・下流 |

> 旧来の直鎖パスウェイ（例：カフェイン合成 WP5586）は `translation/reactant/product` を持たないため、結果は「conversion 背骨＋catalysis 酵素」だけになり、従来どおりの見た目になる。

### 接続辺の最短化（RelX/RelY）

ノードを矩形（中心・幅・高さ）とみなし、中心から相手方向へのレイがどの辺を抜けるかを `|dx|/半幅` と `|dy|/半高` の比較で判定して、その辺の中点に接続点を置く。矩形のアスペクト比を考慮するため、幾何的に最短になる辺が選ばれる。

- 縦並びの変換 → 上下の辺、横並びの `gene→protein` → 左右の辺、のように自動で振り分く。
- PathVisio は `GraphRef + RelX/RelY` を正として描画するので、ノードを動かしたら接続辺も更新しないと線が古い位置に残る。本ツールは `RelX/RelY` と `X/Y` の両方を整合させて書き戻す。
- anchor は矩形ではなく反応線上の点。ノード同士の接続点を先に確定 → `Position` で内分して anchor 座標を求め → 触媒・共基質側ノードはその anchor へ最寄り辺を向ける。anchor 側の Point は `RelX=RelY=0`。
- `--no-optimize-sides` で従来挙動（接続辺はそのまま）に戻せる。

### CLI

| 引数 | 説明 |
|---|---|
| `input` | 入力 GPML（必須） |
| `--write-gpml PATH` | 座標と接続辺を書き戻した GPML を出力 |
| `--nodes-out PATH` | ノード+座標の TSV を出力（省略時は標準出力） |
| `--root GRAPHID` | BFS ルートを明示（省略時は入次数0のノードを自動選択） |
| `--no-fit-board` | `BoardWidth/BoardHeight` の自動再計算をしない |
| `--no-optimize-sides` | 接続辺 `RelX/RelY` の最短化をしない |
| `--no-collapse-proteins` | transcript→protein→anchor の冗長Protein層を畳み込まない（既定は畳み込む） |
| `--quiet` | サマリ（stderr）を抑制 |

### transcript→protein→anchor の畳み込み（既定ON / opt-out）

PlantCyc(Cyc_to_wiki)系の GPML は `GeneProduct(transcript) →[転写翻訳]→ Protein →[触媒]→ anchor` の3段になりがちで、Protein 層が冗長。既定ではこれを検出して **Protein を削除し、transcript を直接 anchor へ触媒接続に張り替えて**書き出す。

対象となる Protein 中間ノードの条件:

- `Type == "Protein"`、かつ group のメンバーでない
- 入ってくる転写翻訳(`mim-transcription-translation`)エッジがちょうど1本（transcript が一意）
- anchor へ向かう触媒(`mim-catalysis`)エッジが1本以上

→ 該当する Protein とその転写翻訳エッジを削除し、触媒エッジの起点を transcript に張り替える（複数の触媒先 anchor があれば全て張り替え）。`--no-collapse-proteins` で無効化。ライブラリでは `g2n.collapse_transcript_protein(parsed)` で計画を得て `g2n.apply_collapse(parsed, plan)` で適用し、`write_gpml_with_layout(..., collapse_plan=plan)` に渡す。

### ライブラリとして使う

```python
import gpml2network as g2n
import gpml_layout as gl

parsed = g2n.parse_gpml("pathway.gpml")

# 座標計算（戻り値 {GraphId: (x, y)}。parsed.nodes[*].x/.y も更新される）
positions = gl.bfs_layout(parsed, root=None)

# GPML へ書き戻し（接続辺の最短化込み）
gl.write_gpml_with_layout("pathway.gpml", parsed, positions, "out.gpml",
                          fit_board=True, optimize_sides=True)

# 個別に使いたい場合
conv, trans, cat, react, prod = gl.classify(parsed)
edge_pts = gl.assign_connection_points(parsed, positions)   # {iid: ((sx,sy,srx,sry),(ex,ey,erx,ery))}
```

### チューニング定数（`gpml_layout.py` 冒頭）

| 定数 | 既定 | 意味 |
|---|---|---|
| `MIN_STAGE_WIDTH` | 400 | 背骨レイヤの最小横幅 |
| `STAGE_MARGIN` | 150 | 全体の余白 |
| `INTERACTION_LENGTH` | 180 | 背骨レイヤ間の縦間隔 |
| `INDEX_STEP` | 150 | レイヤ内ノード増加時の横幅拡張 |
| `PERP_ENZYME` | 0.75 | 酵素を反応軸から離す距離（×\|AB\|） |
| `PERP_METAB` | 0.95 | 共基質/共生成物を離す距離（×\|AB\|） |
| `METAB_ALONG` | 0.35 | 共基質(上流)/共生成物(下流)の軸方向ずらし（×\|AB\|） |
| `ENZYME_PIX_STEP` | 34 | 同一 anchor に複数酵素のときの軸方向間隔(px) |
| `METAB_PIX_STEP` | 90 | 共基質/共生成物が複数のときの間隔(px) |
| `GENE_GAP` | 120 | 遺伝子をタンパク質から押し出す距離 |
| `GENE_FAN` | 36 | 1タンパク質に複数遺伝子のときの間隔 |
| `GROUP_ROW_HEIGHT` | 40 | group メンバーの縦展開間隔 |

---

## 典型ワークフロー

```bash
# ネットワークだけ抽出（解析・cytoscape等へ）
python3 gpml2network.py pathway.gpml -o edges.tsv --graphml pathway.graphml --labels

# 再レイアウトして PathVisio / WikiPathways で開ける GPML を作る
python3 gpml_layout.py pathway.gpml --write-gpml pathway_relayout.gpml

# 起点を指定して縦方向を固定（複数反応が連なる経路向け）
python3 gpml_layout.py pathway.gpml --root START_NODE_ID --write-gpml out.gpml

# 接続辺はいじらず座標だけ更新したい
python3 gpml_layout.py pathway.gpml --write-gpml out.gpml --no-optimize-sides
```

## 注意・既知の制約

- **GPML2013a / GPML2021 両対応**：要素は名前空間を無視して local name で判定。Xref は `Database/ID`（2013a）と `dataSource/identifier`（2021）の両方を読む。
- **group**：複合体は構成メンバー DataNode に展開して座標を与える。group 自体には `CenterX/CenterY` を書かない。
- **主軸の選び方**：可逆反応の副基質・副生成物（例：2-oxoglutarate / glutamate）は主基質と同じ metabolite として扱い、背骨ではなく反応の側枝に置く。主軸を別の取り方にしたい場合は `classify()` の規則を変える。
- **接続辺は「辺の中点」**：中心同士を結ぶ直線が辺と交わる正確な点ではなく、選んだ辺の中点に接続する（GPML の慣例に合わせている）。1つの辺に矢印が集中する場合に散らしたいときは、辺方向オフセットの追加で対応可能。
- **複数反応・分岐**：背骨は入次数0のノードを起点に縦に伸ばす。横向きや分岐レイアウトが必要なら軸方向の定数・向きで調整する。
