# pathlay

GPML（WikiPathways / PathVisio 形式）のパスウェイを再レイアウトするツール。
ノードをBFSで配置し直し、エッジを最寄りの辺に付け替え、座標を GPML に書き戻す。

## 最小の使い方

```bash
pip install networkx
python3 gpml_layout.py pathway.gpml --write-gpml pathway_relayout.gpml
```

- `gpml_layout.py` と `gpml2network.py` を**同じフォルダ**に置くこと（前者が後者を import する）。
- Python 3.10 以上。

これで `pathway_relayout.gpml` が出力される。中では次が自動で効く:
再レイアウト（BFS）／接続辺の最短化（`RelX/RelY`）／`transcript→protein→anchor` の冗長Protein層の畳み込み。

## オプション（必要なときだけ）

| 引数 | 説明 |
|---|---|
| `--write-gpml PATH` | 書き戻した GPML を出力 |
| `--nodes-out PATH` | ノード+座標の TSV を出力 |
| `--root GRAPHID` | BFS の起点を指定（既定は入次数0のノードを自動選択） |
| `--no-collapse-proteins` | Protein層の畳み込みをしない |
| `--no-optimize-sides` | 接続辺の最短化をしない |
| `--no-fit-board` | ボード寸法の自動再計算をしない |
| `--quiet` | サマリ（stderr）を抑制 |

## ネットワークだけ欲しいとき

```bash
python3 gpml2network.py pathway.gpml            # エッジリスト(TSV)を標準出力
python3 gpml2network.py pathway.gpml --graphml out.graphml --labels
```
