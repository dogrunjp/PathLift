import sys
import urllib.request
import urllib.parse
import time

def parse_fasta_records(fasta_data):
    records = []
    header = None
    seq_lines = []

    for line in fasta_data.strip().splitlines():
        if line.startswith(">"):
            if header and seq_lines:
                records.append((header, "\n".join(seq_lines)))
            header = line[1:]
            seq_lines = []
        else:
            seq_lines.append(line)

    if header and seq_lines:
        records.append((header, "\n".join(seq_lines)))

    return records

def fetch_fasta_from_uniprot(unmapped_list, source_taxid, output_fasta="unmapped_queries.fa"):
    if not unmapped_list:
        return None

    target_symbols = set(unmapped_list)
    found_count = 0

    print(f"[*] {len(target_symbols)} 種類の迷子遺伝子について、UniProtサーバーにFASTA配列を問い合わせます...")

    try:
        with open(output_fasta, "w") as out_file:
            for symbol in target_symbols:
                time.sleep(0.5)

                reviewed_query = f"(gene_exact:{symbol}) AND (taxonomy_id:{source_taxid}) AND (reviewed:true)"
                encoded_query = urllib.parse.quote(reviewed_query)
                url = (
                    f"https://rest.uniprot.org/uniprotkb/search?"
                    f"query={encoded_query}&format=fasta&size=10&includeIsoform=true"
                )
                try:
                    with urllib.request.urlopen(urllib.request.Request(url)) as response:
                        fasta_data = response.read().decode("utf-8")
                except urllib.error.URLError as e:
                    print(f"  -> [通信エラー] {symbol}: {e}")
                    fasta_data = ""

                records = parse_fasta_records(fasta_data)

                if records:
                    for i, (_header, sequence) in enumerate(records, start=1):
                        qid = symbol if len(records) == 1 else f"{symbol}|reviewed{i}"
                        out_file.write(f">{qid}\n{sequence}\n")
                    found_count += 1
                    print(f"  -> [取得成功] {symbol} reviewed {len(records)}件")
                    continue

                fallback_query = f"(gene_exact:{symbol}) AND (taxonomy_id:{source_taxid})"
                encoded_query = urllib.parse.quote(fallback_query)
                url = f"https://rest.uniprot.org/uniprotkb/search?query={encoded_query}&format=fasta&size=1"

                try:
                    with urllib.request.urlopen(urllib.request.Request(url)) as response:
                        fasta_data = response.read().decode("utf-8")
                except urllib.error.URLError as e:
                    print(f"  -> [通信エラー] {symbol}: {e}")
                    fasta_data = ""

                records = parse_fasta_records(fasta_data)

                if records:
                    _header, sequence = records[0]
                    out_file.write(f">{symbol}\n{sequence}\n")
                    found_count += 1
                    print(f"  -> [取得成功] {symbol} fallback")
                else:
                    print(f"  -> [取得失敗] {symbol} (UniProtで見つかりません)")

        print("=========================================")
        print(f"[+] 完了: {found_count} / {len(target_symbols)} 件の配列を {output_fasta} に保存しました。")

        if found_count == 0:
            return None
        return output_fasta

    except Exception as e:
        print(f"[-] FASTA取得処理中にエラーが発生しました: {e}", file=sys.stderr)
        return None