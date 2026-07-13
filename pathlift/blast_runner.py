import subprocess
import os
import csv

def filter_blast_results(input_tsv):
    """BLAST outfmt 6 の結果を条件でフィルタリングする。"""
    base_name = os.path.splitext(input_tsv)[0]
    filtered_output = f"{base_name}_filtered.tsv"

    with open(input_tsv, newline="", encoding="utf-8") as fin, \
         open(filtered_output, "w", newline="", encoding="utf-8") as fout:
        reader = csv.reader(fin, delimiter="\t")
        writer = csv.writer(fout, delimiter="\t", lineterminator="\n")

        for row in reader:
            if len(row) < 8:
                continue

            try:
                length = float(row[3])
                qlen = float(row[4])
                slen = float(row[5])
            except ValueError:
                continue

            if qlen == 0 or slen == 0:
                continue

            if (
                length >= 50
                and (length / qlen) >= 0.6
                and (length / slen) >= 0.6
                and (qlen / slen) >= 0.7
                and (slen / qlen) >= 0.7
            ):
                writer.writerow(row)

    return filtered_output

def execute_blast_pipeline(query_fasta, recipe, reference_fasta=None, output_tsv="unmapped_queries_results.tsv"):
    """統合されたBLAST実行関数"""

    # recipe の compute_fallback.blastp.evalue を使う。フィルタ閾値(identity/coverage)は
    # RBH_plus由来の固定ロジック(filter_blast_results)でrecipe化しない(recipe.schema.md参照)。
    evalue = str(
        ((getattr(recipe, "compute_fallback", None) or {}).get("blastp") or {}).get("evalue")
        or "1e-5"
    )

    # 1. ローカル/リモートの分岐コマンド構築
    if reference_fasta and os.path.exists(reference_fasta):
        print(f"[*] ローカルFASTA検索: {reference_fasta}")
        cmd = ["blastp", "-query", query_fasta, "-subject", reference_fasta,
               "-evalue", evalue, "-outfmt", "6 qseqid sseqid pident length qlen slen evalue bitscore",
               "-out", output_tsv]
    else:
        # recipe オブジェクトから taxid を取得
        taxid = getattr(recipe, 'target_taxid', None)
        print(f"[*] リモートBLAST検索 (TaxID: {taxid})")
        cmd = ["blastp", "-query", query_fasta, "-db", "nr",
               "-entrez_query", f"txid{taxid}[ORGN]", "-remote",
               "-evalue", evalue, "-outfmt", "6 qseqid sseqid pident length qlen slen evalue bitscore",
               "-out", output_tsv]

    # 2. 実行
    subprocess.run(cmd, check=True)
    
    # 3. フィルタリング
    return filter_blast_results(output_tsv)

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("fasta")
    parser.add_argument("yaml")
    args = parser.parse_args()
    execute_blast_pipeline(args.fasta, args.yaml)