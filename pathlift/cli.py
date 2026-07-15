"""pathlift CLI。

  pathlift run <recipe.yaml> [-o out.gpml]

recipe を読み(①)、③オーソログ解決器を組み立て、②変換器で出力GPMLを書き、stats を表示。
発現(④)は Phase2(未実装)。
"""
from __future__ import annotations

import argparse
import os
import sys
import yaml

from .recipe import load_recipe, RecipeError
from .ortholog import OrthologResolver
from .transform import PathwayTransformer
from .query_fasta import fetch_fasta_from_uniprot
from .blast_runner import execute_blast_pipeline
from .auto_curation import generate_curation_yaml


def _default_out(source_gpml: str) -> str:
    stem = os.path.splitext(os.path.basename(source_gpml))[0]
    return f"{stem}.lifted.gpml"

def _resource_path(rc, filename: str) -> str:
    resource_dir = os.path.join(os.path.dirname(rc.base_dir), "resource")
    os.makedirs(resource_dir, exist_ok=True)
    return os.path.join(resource_dir, filename)

def cmd_run(args) -> int:
    try:
        rc = load_recipe(args.recipe)
    except RecipeError as e:
        print(str(e), file=sys.stderr)
        return 2
    
    recipe_stem = os.path.splitext(os.path.basename(args.recipe))[0]

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

    unmapped_list = stats.get("unmapped_list", [])
    if unmapped_list:
        print(f"\n[!] 迷子遺伝子を {len(unmapped_list)} 件検出。自動レスキューを開始します...")
        
        # フェーズ4: FASTA取得
        source_taxid = rc.gene_info_taxid
        query_fasta = fetch_fasta_from_uniprot(
            unmapped_list,
            source_taxid,
            output_fasta=_resource_path(rc, f"{recipe_stem}_unmapped_queries.fa"),
        )
        
        if query_fasta:
            # フェーズ5: BLAST実行とフィルタリング
            blast_tsv = _resource_path(rc, f"{recipe_stem}_unmapped_queries_results.tsv")

            filtered_result = execute_blast_pipeline(
                query_fasta,
                rc,
                reference_fasta=rc.reference_fasta,
                output_tsv=blast_tsv,
            )
            if filtered_result:
                auto_yaml_path = os.path.join(rc.base_dir, f"{recipe_stem}_auto_curation.yaml")
                use_entrez_gene = not (rc.reference_fasta and os.path.exists(rc.reference_fasta))

                generate_curation_yaml(
                    filtered_result,
                    unmapped_list,
                    resolver.txgene,
                    auto_yaml_path,
                    use_entrez_gene=use_entrez_gene,
                    query_fasta=query_fasta,
                )
                
                # フェーズ7: 新しいキュレーションを適用して2周目のリフトオーバーを実行
                print("\n[*] キュレーションを適用してGPMLを再生成します...")
                
                # rcオブジェクトの curation 属性を新しいファイルで上書き更新
                with open(auto_yaml_path, 'r', encoding='utf-8') as f:
                    data = yaml.safe_load(f) or {}
                rc.curation = {
                    "overrides": data.get("overrides") or [],
                    "unmapped": data.get("unmapped") or []
                }
                
                # 辞書(resolver)と変換器を再構築
                resolver_v2 = OrthologResolver.from_config(
                    funflow_path=rc.table_path,
                    columns=rc.columns,
                    gene_info_path=rc.gene_info_path,
                    gene_info_taxid=rc.gene_info_taxid,
                    gtf_path=rc.transcript_gene_gtf,
                    curation=rc.curation,  # ★更新されたYAMLが読み込まれる
                    routes=rc.routes,
                    idmap_path=rc.idmap_path,
                    policy=rc.policy,
                )
                transformer_v2 = PathwayTransformer(resolver_v2, out_namespace=rc.output_id_namespace)
                
                # 同じ出力パスに上書き保存
                stats = transformer_v2.run(rc.source_gpml, out)
                print("[+] 自動レスキューによる補完が完了しました。")

            else:
                print("[-] BLAST検索結果が得られなかったため、自動補完をスキップします。")

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
