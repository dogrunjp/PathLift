import sys
import urllib.request
import urllib.parse
import time

def fetch_fasta_from_uniprot(unmapped_list, source_taxid, output_fasta="unmapped_queries.fa"):
    """
    Gene Symbol (TPH1など) を使ってUniProtから配列を取得する関数
    """
    if not unmapped_list:
        return None

    # set() を使って MAOA のような重複を自動で排除します
    target_symbols = set(unmapped_list)
    found_count = 0

    print(f"[*] {len(target_symbols)} 種類の迷子遺伝子について、UniProtサーバーにFASTA配列を問い合わせます...")
    
    try:
        with open(output_fasta, 'w') as out_file:
            for symbol in target_symbols:
                time.sleep(0.5)

                queries = [
                    f"(gene_exact:{symbol}) AND (taxonomy_id:{source_taxid}) AND (reviewed:true)",
                    f"(gene_exact:{symbol}) AND (taxonomy_id:{source_taxid})",
                ]

                fasta_data = ""
                for query in queries:
                    encoded_query = urllib.parse.quote(query)
                    url = f"https://rest.uniprot.org/uniprotkb/search?query={encoded_query}&format=fasta&size=1"

                    try:
                        with urllib.request.urlopen(urllib.request.Request(url)) as response:
                            fasta_data = response.read().decode("utf-8")
                    except urllib.error.URLError as e:
                        print(f"  -> [通信エラー] {symbol}: {e}")
                        continue

                    if fasta_data.strip():
                        break

                if fasta_data.strip():
                    lines = fasta_data.strip().splitlines()
                    sequence = "\n".join(line for line in lines if not line.startswith(">"))
                    out_file.write(f">{symbol}\n{sequence}\n")
                    found_count += 1
                    print(f"  -> [取得成功] {symbol}")
                else:
                    print(f"  -> [取得失敗] {symbol} (UniProtで見つかりません)")
                    
        print(f"=========================================")
        print(f"[+] 完了: {found_count} / {len(target_symbols)} 件の配列を {output_fasta} に保存しました。")
        
        if found_count == 0:
            return None
        return output_fasta

    except Exception as e:
        print(f"[-] FASTA取得処理中にエラーが発生しました: {e}", file=sys.stderr)
        return None