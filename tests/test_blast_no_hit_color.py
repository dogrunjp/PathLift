import tempfile
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path

import yaml

from pathlift.auto_curation import generate_curation_yaml
from pathlift.models import GeneProductNode
from pathlift.ortholog import OrthologResolver
from pathlift.transform import BLAST_NO_HIT_FILL_COLOR, PathwayTransformer


GPML_NS = "http://pathvisio.org/GPML/2013a"


class DummyTranscriptGeneMap:
    def __init__(self):
        self.unrecognized = set()

    def gene_of(self, protein):
        return f"gene:{protein}"


class BlastNoHitColorTests(unittest.TestCase):
    def test_auto_curation_marks_only_queried_sources_without_hits(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            query_fasta = tmp_path / "queries.fa"
            filtered_tsv = tmp_path / "filtered.tsv"
            output_yaml = tmp_path / "auto_curation.yaml"

            query_fasta.write_text(
                ">WITH_HIT|reviewed1\nAAAA\n>NO_HIT\nBBBB\n",
                encoding="utf-8",
            )
            filtered_tsv.write_text(
                "WITH_HIT|reviewed1\ttarget_protein\n",
                encoding="utf-8",
            )

            generate_curation_yaml(
                filtered_tsv,
                ["WITH_HIT", "NO_HIT", "NO_FASTA"],
                DummyTranscriptGeneMap(),
                output_yaml,
                query_fasta=query_fasta,
            )

            data = yaml.safe_load(output_yaml.read_text(encoding="utf-8"))
            self.assertEqual(
                data["unmapped"],
                [{
                    "source": "NO_HIT",
                    "reason": "blast_no_hit",
                    "note": "BLASTpで明確なオーソログ無し",
                }],
            )
            self.assertEqual(data["overrides"][0]["source"], "WITH_HIT")

    def test_reason_is_propagated_from_curation(self):
        resolver = OrthologResolver(
            symbol_index={},
            pid_index={},
            gid2sym={},
            txgene=DummyTranscriptGeneMap(),
            unmapped_index={
                "NO_HIT": {
                    "reason": "blast_no_hit",
                    "note": "BLASTpで明確なオーソログ無し",
                },
            },
        )

        result = resolver.resolve(GeneProductNode(
            graph_id="a0001",
            label="NO_HIT",
            database="HGNC",
            xref_id="NO_HIT",
        ))

        self.assertEqual(result.unmapped_reason, "blast_no_hit")
        self.assertEqual(result.note, "BLASTpで明確なオーソログ無し")

    def test_transform_colors_only_blast_no_hit_nodes(self):
        gpml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Pathway xmlns="{GPML_NS}">
  <DataNode TextLabel="BLAST_MISS" GraphId="a0001" Type="GeneProduct">
    <Graphics CenterX="10" CenterY="10" Width="80" Height="20" Color="0000ff" />
    <Xref Database="Entrez Gene" ID="1" />
  </DataNode>
  <DataNode TextLabel="NORMAL_MISS" GraphId="a0002" Type="GeneProduct">
    <Graphics CenterX="20" CenterY="20" Width="80" Height="20" Color="00aa00" />
    <Xref Database="Entrez Gene" ID="2" />
  </DataNode>
  <DataNode TextLabel="MANUAL_MISS" GraphId="a0003" Type="GeneProduct">
    <Graphics CenterX="30" CenterY="30" Width="80" Height="20" Color="aa00aa" />
    <Xref Database="Entrez Gene" ID="3" />
  </DataNode>
</Pathway>
"""
        resolver = OrthologResolver(
            symbol_index={},
            pid_index={},
            gid2sym={
                "1": "BLAST_MISS",
                "2": "NORMAL_MISS",
                "3": "MANUAL_MISS",
            },
            txgene=DummyTranscriptGeneMap(),
            unmapped_index={
                "BLAST_MISS": {
                    "reason": "blast_no_hit",
                    "note": "BLASTpで明確なオーソログ無し",
                },
                "MANUAL_MISS": {
                    "reason": None,
                    "note": "手動で未解決に確定",
                },
            },
        )

        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "source.gpml"
            output = Path(tmp) / "output.gpml"
            source.write_text(gpml, encoding="utf-8")

            PathwayTransformer(resolver, out_namespace="assembly").run(source, output)

            root = ET.parse(output).getroot()
            nodes = {
                node.get("TextLabel"): node
                for node in root.findall(f"{{{GPML_NS}}}DataNode")
            }
            blast_graphics = nodes["BLAST_MISS"].find(f"{{{GPML_NS}}}Graphics")
            normal_graphics = nodes["NORMAL_MISS"].find(f"{{{GPML_NS}}}Graphics")
            manual_graphics = nodes["MANUAL_MISS"].find(f"{{{GPML_NS}}}Graphics")
            blast_xref = nodes["BLAST_MISS"].find(f"{{{GPML_NS}}}Xref")

            self.assertEqual(
                blast_graphics.get("FillColor"),
                BLAST_NO_HIT_FILL_COLOR,
            )
            self.assertEqual(blast_graphics.get("Color"), "0000ff")
            self.assertIsNone(normal_graphics.get("FillColor"))
            self.assertEqual(normal_graphics.get("Color"), "00aa00")
            self.assertIsNone(manual_graphics.get("FillColor"))
            self.assertEqual(manual_graphics.get("Color"), "aa00aa")
            self.assertEqual(blast_xref.get("Database"), "Entrez Gene")
            self.assertEqual(blast_xref.get("ID"), "1")


if __name__ == "__main__":
    unittest.main()
