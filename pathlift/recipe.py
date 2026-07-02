"""① Recipe Loader: liftover recipe(YAML, schema_version 2)を読み、検証し config を返す。

原則: 検証失敗なら RecipeError を投げ、ランタイムに入れない
(=「下流はパス探索も判定もしない」を担保)。相対パスは recipe のあるディレクトリ基準。
依存は PyYAML のみ(検証は明示的に実施)。
"""
from __future__ import annotations

import csv
import os
from dataclasses import dataclass

import yaml

SUPPORTED_SCHEMA = 2


class RecipeError(ValueError):
    pass


@dataclass
class Recipe:
    base_dir: str
    source_gpml: str
    output_id_namespace: str
    table_path: str
    table_format: str
    columns: dict
    routes: dict
    policy: str
    target_taxid: int | None = None
    transcript_gene_gtf: str | None = None
    reference_fasta: str | None = None
    gene_info_path: str | None = None
    gene_info_taxid: str = "9606"
    idmap_path: str | None = None
    compute_fallback: dict | None = None
    tpm_path: str | None = None
    curation: dict | None = None


def load_recipe(path: str) -> Recipe:
    with open(path, encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    base_dir = os.path.dirname(os.path.abspath(path))
    errs: list[str] = []

    def rp(p):
        """相対パスを recipe ディレクトリ基準で解決。"""
        if not p:
            return None
        return p if os.path.isabs(p) else os.path.normpath(os.path.join(base_dir, p))

    def need_file(p, label):
        if p and not os.path.exists(p):
            errs.append(f"{label} が見つからない: {p}")

    # schema_version
    sv = data.get("schema_version")
    if sv != SUPPORTED_SCHEMA:
        errs.append(f"schema_version は {SUPPORTED_SCHEMA} を要求(実際: {sv})")

    pathway = data.get("pathway") or {}
    target = data.get("target") or {}
    res = data.get("ortholog_resolver") or {}
    expr = data.get("expression") or {}

    # pathway
    source_gpml = rp(pathway.get("source_gpml"))
    if not source_gpml:
        errs.append("pathway.source_gpml は必須")
    else:
        need_file(source_gpml, "pathway.source_gpml")

    # target
    output_ns = target.get("output_id_namespace") or "assembly"
    if not str(output_ns).strip():
        errs.append("target.output_id_namespace が空")
    gtf = rp(target.get("transcript_gene_gtf"))
    need_file(gtf, "target.transcript_gene_gtf")
    ref_fa = rp(target.get("reference_fasta"))
    taxid = target.get("taxid")

    # ortholog_resolver
    policy = res.get("policy", "augment")
    if policy not in ("strict", "augment"):
        errs.append(f"ortholog_resolver.policy は strict|augment (実際: {policy})")

    pt = res.get("provided_table") or {}
    table_path = rp(pt.get("path"))
    table_format = pt.get("format", "tsv")
    if table_format not in ("tsv", "csv"):
        errs.append(f"provided_table.format は tsv|csv (実際: {table_format})")
    if not table_path:
        errs.append("provided_table.path は必須")
    else:
        need_file(table_path, "provided_table.path")

    columns = pt.get("columns") or {}
    for key in ("target_id", "source_symbol"):
        if not columns.get(key):
            errs.append(f"provided_table.columns.{key} は必須")
    # 表ヘッダに列が実在するか
    if table_path and os.path.exists(table_path):
        delim = "\t" if table_format == "tsv" else ","
        try:
            with open(table_path, newline="", encoding="utf-8") as f:
                header = next(csv.reader(f, delimiter=delim))
            for ckey in ("target_id", "source_symbol", "source_pid"):
                col = columns.get(ckey)
                if col and col not in header:
                    errs.append(f"列 '{col}' (columns.{ckey}) が表ヘッダに無い")
        except StopIteration:
            errs.append("provided_table が空")

    gi = res.get("gene_info") or {}
    gene_info_path = rp(gi.get("path"))
    need_file(gene_info_path, "gene_info.path")
    gene_info_taxid = str(gi.get("taxid", "9606"))

    routes = res.get("routes") or {"symbol": True}
    if not any(routes.get(r) for r in ("symbol", "pid", "compute")):
        errs.append("少なくとも1つの route を有効にすること")

    idmap_path = rp(res.get("idmap"))
    if routes.get("pid"):
        if not idmap_path:
            errs.append("routes.pid=true には idmap が必須")
        else:
            need_file(idmap_path, "idmap")

    compute_fallback = res.get("compute_fallback")
    if routes.get("compute"):
        bp = (compute_fallback or {}).get("blastp") or {}
        ev = bp.get("evalue")
        if ev is None or float(ev) <= 0:
            errs.append("routes.compute=true には compute_fallback.blastp.evalue(>0) が必要")
        for k in ("identity_min", "coverage_min"):
            v = bp.get(k)
            if v is not None and not (0 <= float(v) <= 100):
                errs.append(f"compute_fallback.blastp.{k} は 0-100")

    # expression(任意)
    tpm_path = rp(expr.get("tpm"))
    need_file(tpm_path, "expression.tpm")

    # curation サイドカー
    cur_name = data.get("curation_file")
    cur_path = rp(cur_name) if cur_name else os.path.join(
        base_dir, os.path.splitext(os.path.basename(path))[0] + ".curation.yaml")
    curation = {"overrides": [], "unmapped": []}
    if cur_path and os.path.exists(cur_path):
        with open(cur_path, encoding="utf-8") as f:
            cur = yaml.safe_load(f) or {}
        curation = {"overrides": cur.get("overrides") or [],
                    "unmapped": cur.get("unmapped") or []}
    elif cur_name:  # 明示指定なのに無い
        errs.append(f"curation_file が見つからない: {cur_path}")

    if errs:
        raise RecipeError("recipe検証に失敗:\n - " + "\n - ".join(errs))

    return Recipe(
        base_dir=base_dir, source_gpml=source_gpml, output_id_namespace=str(output_ns),
        table_path=table_path, table_format=table_format, columns=columns,
        routes=routes, policy=policy, target_taxid=taxid, transcript_gene_gtf=gtf,
        reference_fasta=ref_fa,
        gene_info_path=gene_info_path, gene_info_taxid=gene_info_taxid,
        idmap_path=idmap_path, compute_fallback=compute_fallback, tpm_path=tpm_path,
        curation=curation,
    )
