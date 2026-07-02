import csv
import yaml
import os
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
import urllib.error

def normalize_protein_accession(sseqid):
    parts = sseqid.split("|")
    if len(parts) >= 2:
        return parts[1]
    return sseqid

def ncbi_protein_to_gene_id(sseqid):
    accession = normalize_protein_accession(sseqid)

    try:
        term = urllib.parse.quote(f"{accession}[Accession]")
        esearch_url = (
            "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
            f"?db=protein&term={term}&retmode=xml"
        )

        with urllib.request.urlopen(esearch_url) as response:
            root = ET.fromstring(response.read())

        protein_uid_el = root.find(".//Id")
        if protein_uid_el is None or not protein_uid_el.text:
            return None

        protein_uid = protein_uid_el.text

        time.sleep(0.34)

        elink_url = (
            "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/elink.fcgi"
            f"?dbfrom=protein&db=gene&id={protein_uid}&retmode=xml"
        )

        with urllib.request.urlopen(elink_url) as response:
            root = ET.fromstring(response.read())

        gene_id_el = root.find(".//Link/Id")
        if gene_id_el is None or not gene_id_el.text:
            return None

        return gene_id_el.text

    except urllib.error.HTTPError as e:
        print(f"  -> [NCBI変換失敗] {accession}: HTTP {e.code}")
        return None
    except urllib.error.URLError as e:
        print(f"  -> [NCBI通信エラー] {accession}: {e}")
        return None
    except ET.ParseError as e:
        print(f"  -> [NCBI XML解析失敗] {accession}: {e}")
        return None

def generate_curation_yaml(
    filtered_tsv,
    unmapped_list,
    txgene,
    output_yaml="auto_curation.yaml",
    use_entrez_gene=False,
):
    """
    BLASTのフィルタリング結果(TSV)から .curation.yaml を自動生成する
    """
    overrides = []
    unmapped = []
    found_sources = set()
    protein_gene_cache = {}

    # 1. BLAST結果の読み込みと overrides の作成
    if os.path.exists(filtered_tsv):
        # ※ TSVの列名（qseqid, sseqid）は実際のファイルに合わせて調整してください
        with open(filtered_tsv, newline="", encoding="utf-8") as f:
            reader = csv.reader(f, delimiter="\t")
            for row in reader:
                if len(row) < 2:
                    continue

                source = row[0]
                target_protein = row[1]

                if use_entrez_gene:
                    if target_protein not in protein_gene_cache:
                        protein_gene_cache[target_protein] = ncbi_protein_to_gene_id(target_protein)
                    target_gene = protein_gene_cache[target_protein]
                else:
                    target_gene = txgene.gene_of(target_protein)

                if not target_gene:
                    continue

                note = "blastpで自動補完"
                if use_entrez_gene:
                    note = (
                        f"blastp remoteで自動補完; "
                        f"original protein={target_protein}; "
                        f"target is Entrez Gene ID"
                    )

                overrides.append({
                    "source": source,
                    "target": target_gene,
                    "note": note,
                })
                found_sources.add(source)

    # 2. BLASTでも見つからなかった遺伝子を unmapped に分類
    for gene in unmapped_list:
        if gene not in found_sources:
            unmapped.append({
                'source': gene,
                'note': 'BLASTで明確なオーソログ無し'
            })

    # 3. YAMLデータの構築
    curation_data = {}
    if overrides:
        curation_data['overrides'] = overrides
    if unmapped:
        curation_data['unmapped'] = unmapped

    # 4. YAMLファイルとして書き出し
    with open(output_yaml, 'w', encoding='utf-8') as f:
        yaml.dump(curation_data, f, allow_unicode=True, default_flow_style=False, sort_keys=False)

    print(f"[+] 自動キュレーションファイルを生成しました: {output_yaml}")
    return output_yaml