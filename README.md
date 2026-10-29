# PathLift

**English** | [日本語](README.ja.md)

PathLift is a CLI tool that **lifts** WikiPathways GPML pathways onto another species by re-assigning gene IDs through an ortholog table.
Each GeneProduct node of the source species (e.g., human) is replaced with, or expanded into, candidate gene nodes of the target species, and the result is written out as GPML.

```
source GPML (human) ─┐
ortholog table ──────┼─▶  pathlift run <recipe>.yaml  ─▶  lifted GPML (target species)
gene_info (human) ───┘
```

## Quick start

```bash
git clone https://github.com/dogrunjp/PathLift.git
cd PathLift
conda create -n pathlift python=3.12 -y
conda activate pathlift
pip install -e .

# After placing the input files under resource/ (see "Examples")
pathlift run configs/WP550_Ac.yaml -o out_WP550_A_cerana.gpml
```

---

## Installation

Requirements: Python 3.10+ and PyYAML. `pip install -e .` (run in the repository root) installs PyYAML and the `pathlift` command.

```bash
conda create -n pathlift python=3.12 -y
conda activate pathlift
pip install -e .
pathlift run --help   # verify
```

Alternatively, install only the dependencies and run `python -m pathlift.cli run …`.

`blastp` is needed **only** if you enable the optional compute route (see [compute route](#compute-route-blast-rescue)). With the default `routes.compute: false`, the steps above are all you need.

<details>
<summary>What does <code>pip install -e .</code> do? (for those new to Python)</summary>

- **Always run it in the repository root (`PathLift/`).** `.` means the current directory; pip reads `pyproject.toml` from there. Run elsewhere, it cannot find `pyproject.toml` and fails.
- It does not scan the whole repository. Only `pathlift/`, as specified by `packages = ["pathlift"]` in `pyproject.toml`, is registered as a package. `設計資料/` and `configs/` are not included.
- Two things happen once it is registered: (1) `import pathlift` works from anywhere, and (2) a `pathlift` **command is placed on your PATH** (via `[project.scripts]`). That is why you can type `pathlift run …`.
- **`-e` (editable)** installs by referencing the current `pathlift/` directory instead of copying it. Edits to `pathlift/*.py` take effect on the next run without reinstalling.

If `pathlift: command not found` appears, you probably forgot to `activate` the conda environment, or ran the install outside the repository root. Re-run `pip install -e .` inside `PathLift/`.
</details>

---

## Examples

Large input files go under `resource/` (git-ignored; not included in the repository).
**They are not downloaded automatically.** If something is missing, see `開発管理/手動PoC記録.md` (manual PoC notes, in Japanese) or ask a team member who already has it.
Recording each file's source (DOI/URL) under `開発管理/` makes adding new species easier.

### Example 1: WP550 → *Apis cerana*

| Input | Source | Location (example) |
|---|---|---|
| Source GPML | [WikiPathways WP550](https://github.com/wikipathways/wikipathways-database/blob/main/pathways/WP550/WP550.gpml) | `resource/WP550.gpml` |
| Ortholog table (*A. cerana*) | [fanflow, figshare 27175734](https://figshare.com/articles/dataset/Apis_cerana_japonica_transcript_data_transcript_sequence_data_predicted_amino_acid_sequence_data_functional_annotation_data_/27175734/fuctional_annotation_transcript_Ac.tsv) | `resource/A_cerana/.../fuctional_annotation_transcript_Ac.tsv` |
| gene_info (human) | [NCBI `Homo_sapiens.gene_info.gz`](https://ftp.ncbi.nlm.nih.gov/gene/DATA/GENE_INFO/Mammalia/Homo_sapiens.gene_info.gz): the **human-only** file; decompress with `gunzip` | `resource/Homo_sapiens.gene_info` |
| Reference FASTA (optional, compute only) | All protein sequences of the target species (may be omitted; see [compute route](#compute-route-blast-rescue)) | `resource/A_cerana/.../ref_transcript_Ac_pep.fa` |

Recipe `configs/WP550_Ac.yaml` (rename as you like):

```yaml
pathway:
  source_gpml: ../resource/WP550.gpml   # source (e.g., human) GPML

# target:
#   transcript_gene_gtf: ../resource/A_cerana/...   # transcript→gene mapping of the target (optional; not needed at present)

ortholog_resolver:
  provided_table:
    path: ../resource/A_cerana/figshare_27175734/fuctional_annotation_transcript_Ac.tsv   # source↔target ortholog table
    columns:
      target_id:     ProteinID           # column with target-species IDs
      source_symbol: H_sapiens-gsymbol   # column with source gene symbols (primary route)
      source_pid:    H_sapiens-pid       # column with source protein IDs (precise route; optional)
  gene_info: {path: ../resource/Homo_sapiens.gene_info}   # source GeneID → official symbol
  routes: {symbol: true, pid: false, compute: false}      # for compute: true, see "compute route"
```

Run from the repository root:

```bash
pathlift run configs/WP550_Ac.yaml -o out_WP550_A_cerana.gpml
```

### Example 2: WP5277 → *Bombyx mori*

| Input | Source | Location (example) |
|---|---|---|
| Source GPML | [WikiPathways WP5277](https://github.com/wikipathways/wikipathways-database/blob/main/pathways/WP5277/WP5277.gpml) | `resource/WP5277.gpml` |
| Ortholog table (*B. mori*) | [fanflow, figshare 19368137](https://figshare.com/ndownloader/files/34398281) | `resource/B_mori/FF4I-B_mori-protein.tsv` |
| gene_info (human) | Same as Example 1 | `resource/Homo_sapiens.gene_info` |
| Reference FASTA (optional, compute only) | All protein sequences of the target species | `resource/B_mori/...` |

Recipe `configs/WP5277_Bmori.yaml`:

```yaml
pathway:
  source_gpml: ../resource/WP5277.gpml

target:
  output_id_namespace: assembly   # non-standard DataSource; see "Checking the output"
  taxid: 7091                     # used to restrict remote BLAST

ortholog_resolver:
  policy: augment
  provided_table:
    path: ../resource/B_mori/FF4I-B_mori-protein.tsv
    columns:
      target_id:     B_mori-pid
      source_symbol: H_sapiens-gsymbol
      source_pid:    H_sapiens-ENSPID
  gene_info: {path: ../resource/Homo_sapiens.gene_info}
  routes: {symbol: true, pid: false, compute: false}
```

```bash
pathlift run configs/WP5277_Bmori.yaml -o out_WP5277_B_mori.gpml
```

> For *B. mori*, the GTF (RefSeq `GCF_030269925.1`) uses a different ID lineage from the ortholog table (KWMTBOMO), so it is **not used for txgene** (collapsing is done by pattern instead). See Section F of `設計資料/PoC知見と設計判断.md`.

---

## Writing a recipe

- Place recipes (and optional curation sidecars) in `configs/`. Existing files such as `configs/WP5277_Bmori.yaml` serve as templates.
- The authoritative format reference is `設計資料/recipe.schema.md`.
- **Relative paths inside a recipe** (`source_gpml`, etc.) are resolved **from the recipe's directory**. With `configs/` and `resource/` side by side, write `../resource/...`.
- The **`-o` output path** is resolved from the **current working directory**, not the recipe.

---

## Reading the output

After a run, PathLift prints statistics (labels are currently in Japanese):

```
  GeneProduct: 13
    matched  : 7
    unmapped : 6
  候補gene総数 : 12
  追加ノード   : 5
  --- 注意(未対応の可能性) ---
  記号ラベル依存 : 13件
  txgene未対応   : 0件
```

| Line | Meaning |
|---|---|
| `GeneProduct` | Number of GeneProduct nodes in the source |
| `matched` | Nodes resolved to target genes |
| `unmapped` | Nodes that could not be resolved (MISS; see Section C of the design notes) |
| `候補gene総数` (total candidates) | Total candidate genes after expansion |
| `追加ノード` (added nodes) | Nodes added by expansion |
| `注意(未対応の可能性)` (warnings) | **Check these if they appear** |
| `記号ラベル依存` (symbol-label dependent) | IDs that are not Entrez/HGNC; nodes may be missed if their label is not a gene symbol (Sections E, G-1) |
| `txgene未対応` (txgene unsupported) | IDs that could not be collapsed to gene level; may cause duplicated expansion (Sections F, G-1) |

If `unmapped` > 0 and `routes.compute: true`, an automatic rescue follows:

```
[!] 迷子遺伝子を 7 件検出。自動レスキューを開始します...
[*] 6 種類の迷子遺伝子について、UniProtサーバーにFASTA配列を問い合わせます...
  -> [取得成功] TPH1 reviewed 2件
[*] リモートBLAST検索 (TaxID: 7461)
[+] 自動キュレーションファイルを生成しました: configs/<recipe>_auto_curation.yaml
[*] キュレーションを適用してGPMLを再生成します...
[+] 自動レスキューによる補完が完了しました。
```

(Unmapped genes detected → fetching sequences from UniProt → remote BLAST → auto-curation file written → GPML regenerated → done.)

With `routes.compute: false` (default), a single line reports that the rescue was skipped, and no network access occurs:

```
[!] 迷子遺伝子を 7 件検出しましたが、routes.compute が無効なため自動レスキューはスキップします。
```

---

## compute route (BLAST rescue)

`ortholog_resolver.routes.compute` recovers genes left unmapped by the `symbol`/`pid` routes using BLAST. Default: `false` (does nothing).
When enabled and some genes remain `unmapped`, PathLift automatically:

1. Fetches source-species protein sequences for each unmapped gene symbol via the **UniProt REST** API
2. Runs **blastp**: locally against `-subject` if `target.reference_fasta` is set, otherwise `-remote` against NCBI `nr`
3. Filters hits (thresholds are fixed in code and cannot be changed from the recipe; see `設計資料/recipe.schema.md`) and writes `<recipe stem>_auto_curation.yaml` (overrides/unmapped)
4. Applies that curation, **re-runs the liftover**, and overwrites the same output path

### Configuration

```yaml
ortholog_resolver:
  routes:
    compute: true
  compute_fallback:
    blastp:
      evalue: 1e-5      # required; the only value adjustable from the recipe
target:
  reference_fasta: false   # all protein sequences of the target; false → remote blastp
```

| `reference_fasta` | Mode | Notes |
|---|---|---|
| path to FASTA | local blastp | fast, offline |
| `false` / unset | remote blastp against NCBI `nr` | filtered by `target.taxid`; slow, needs network |

### Installing `blastp` (macOS)

Without Homebrew, **conda (bioconda channel)** is the standard choice in bioinformatics (tested with `blast 2.16.0`):

```bash
conda create -n pathlift-blast -c bioconda -c conda-forge blast
conda activate pathlift-blast
blastp -version
```

A separate environment from `pathlift` is fine: PathLift calls `blastp` via `subprocess`, so it only needs to be on the `PATH` of the shell running `pathlift`.

### Known caveats

- **NCBI E-utilities rate limits (HTTP 429) can occur.** With remote blastp, hit protein accessions are converted to Entrez Gene IDs (`ncbi_protein_to_gene_id`); when that service is busy, the request may fail. This is not fatal: only the entry's `target_label` (used to rewrite the GPML TextLabel) is left empty, while the `target` Gene ID is still obtained. Details and reproductions are in `開発管理/テストログ_*.md`.
- Remote blastp may wait in the NCBI queue for several minutes.

---

## Checking the output

- Open the output GPML in **PathVisio** (3.x/4.x). It is GPML 2013a, so it opens.
  - `output_id_namespace: assembly` is a non-standard DataSource, so an "unknown data source" warning appears. **This is expected**: IDs are visible but not resolved to links.
- Inspect expansion, provenance, and MISSes with grep:

```bash
grep -c 'Source="PathLift"' out.gpml                  # nodes touched by PathLift
grep -o 'routes=[^<"]*' out.gpml | sort | uniq -c     # which route matched
grep -o 'unmapped:[^<]*' out.gpml                     # MISSes (with symbols)
```

- **Selecting candidates** (removing false positives) happens outside PathLift: compare the output GPML with extended TPM expression data in a **QPX notebook**.

---

## PoC results

| Recipe | Source | Target | matched / GeneProduct | Expansion ratio |
|---|---|---|---|---|
| WP550_Ac.yaml | WP550 | *A. cerana* | — | — |
| WP5609_Ac.yaml | WP5609 (metabolism) | *A. cerana* | 31/38 (82%) | 2.3 |
| WP5277_Bmori.yaml | WP5277 (steroid metabolism) | *B. mori* | 7/13 (54%) | 1.7 |
| WP5601_Bmori.yaml | WP5601 (signaling) | *B. mori* | 23/33 (70%) | 3.0 |

For interpretation (the two factors behind match and expansion ratios, and what drives MISSes), see `設計資料/PoC知見と設計判断.md`.

---

## Troubleshooting

| Symptom | Cause / fix |
|---|---|
| Shell shows `bquote>` / `quote>` and hangs | Unclosed quote (`` ` `` `'` `"`). Press `Ctrl-C`. |
| `recipe検証に失敗` (recipe validation failed) | Working as intended. Fix the path/column named in the message, especially **relative-path base (recipe directory)** and table header names. |
| Path shifts by one level, e.g. `.../src/resource` | Adjust the number of `../` in the recipe to your layout. |
| Output file in an unexpected place | `-o` is relative to the **current directory**, not the recipe. |
| `blastp: command not found` with `routes.compute: true` | The conda env containing `blastp` is not activated. It only needs to be on `PATH`; it need not be the same env as `pathlift`. |
| A single NCBI-related error during compute, but the run continues | Rate limit (see [Known caveats](#known-caveats)). Not fatal; report it if it happens often. |

---

## Repository layout

```
PathLift/
├── pathlift/      Package: models / txgene / ortholog / gpml / transform / recipe / cli
│                  / query_fasta / blast_runner / auto_curation (compute route)
├── configs/       Recipes + curation (*_auto_curation.yaml is generated here by compute)
├── spike/         Exploratory scripts
├── 設計資料/       Design documents (authoritative)
├── 開発管理/       Logs and records
├── resource/      Large inputs (git-ignored); intermediates such as unmapped_queries.fa go here
└── pyproject.toml
```

## Documentation (Japanese)

- Design and background: `設計資料/` (start with `設計資料/PoC知見と設計判断.md`)
- Recipe format: `設計資料/recipe.schema.md`
- Guidelines for AI agents: `CLAUDE.md`
- Test run logs: `開発管理/テストログ_*.md`
