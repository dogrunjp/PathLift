"""pathlift CLI。

  pathlift run <recipe.yaml> [-o out.gpml]

recipe を読み(①)、③オーソログ解決器を組み立て、②変換器で出力GPMLを書き、stats を表示。
発現(④)は Phase2(未実装)。
"""
from __future__ import annotations

import argparse
import os
import sys

from .recipe import load_recipe, RecipeError
from .ortholog import OrthologResolver
from .transform import PathwayTransformer


def _default_out(source_gpml: str) -> str:
    stem = os.path.splitext(os.path.basename(source_gpml))[0]
    return f"{stem}.lifted.gpml"


def cmd_run(args) -> int:
    try:
        rc = load_recipe(args.recipe)
    except RecipeError as e:
        print(str(e), file=sys.stderr)
        return 2

    resolver = OrthologResolver.from_config(
        funflow_path=rc.table_path,
        columns=rc.columns,
        gene_info_path=rc.gene_info_path,
        gene_info_taxid=rc.gene_info_taxid,
        gtf_path=rc.transcript_gene_gtf,
        curation=rc.curation,
        routes=rc.routes,
        idmap_path=rc.idmap_path,
        policy=rc.policy,
    )
    transformer = PathwayTransformer(resolver, out_namespace=rc.output_id_namespace)

    out = args.output or _default_out(rc.source_gpml)
    stats = transformer.run(rc.source_gpml, out)

    routes_on = [r for r in ("symbol", "pid", "compute") if rc.routes.get(r)]
    print("== pathlift run ==")
    print(f"  source     : {rc.source_gpml}")
    print(f"  routes     : {','.join(routes_on)}  policy={rc.policy}")
    print(f"  out_ns     : {rc.output_id_namespace}")
    print(f"  GeneProduct: {stats['gene_product']}")
    print(f"    matched  : {stats['matched']}")
    print(f"    unmapped : {stats['unmapped']}")
    print(f"  候補gene総数 : {stats['candidate_genes']}")
    print(f"  追加ノード   : {stats['nodes_added']}  (展開後 GeneProduct ≒ "
          f"{stats['gene_product'] + stats['nodes_added']})")
    ld = stats.get("label_dependent", 0)
    tu = stats.get("txgene_unrecognized", 0)
    if ld or tu:
        print("  --- 注意(未対応の可能性) ---")
        if ld:
            print(f"  記号ラベル依存 : {ld}件 (非Entrez/HGNC。ラベルが記号でないと取りこぼす恐れ)")
        if tu:
            print(f"  txgene未対応   : {tu}件 (既にgene単位か、未知ID。重複展開の恐れ)")
    print(f"  -> {out}")
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="pathlift")
    sub = ap.add_subparsers(dest="cmd", required=True)
    p_run = sub.add_parser("run", help="recipe に従って liftover を実行")
    p_run.add_argument("recipe", help="recipe YAML へのパス")
    p_run.add_argument("-o", "--output", default=None, help="出力GPML(既定: <source>.lifted.gpml)")
    p_run.set_defaults(func=cmd_run)
    args = ap.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
