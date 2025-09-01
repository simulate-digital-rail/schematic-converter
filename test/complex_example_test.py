from collections import defaultdict
from pathlib import Path
import pytest

from planpro_importer import PlanProVersion, import_planpro
from schematicconverter import convert
from yaramo.topology import Topology


@pytest.fixture(scope="module")
def processed_topology():
    topology = import_planpro(str(Path(__file__).parent / "complex-example.ppxml"), PlanProVersion.PlanPro19)
    convert(topology, scale_factor=1.0, remove_non_ks_signals=False)
    yield topology


def test_vertical_alignment(processed_topology: Topology):
    expected_vertical_positions: dict[float, set[str]] = {
        0.0: {
            "2b9e4590-ec47-4252-ab28-93cbb488e14c",
        },
        1.0: {
            "a4b176c5-69c1-455f-83bc-037b330fb749",
            "2e59afeb-8a51-47a6-a38e-129c185e641b",
            "b18b163f-0571-4783-a874-653eb0a80a8e",
        },
        2.0: {
            "c17471be-e09e-4561-8adc-e335f66aa303",
        },
        3.0: {
            "e7ca9a9f-95da-4528-b1bc-d60f757d6e07",
            "b035347a-8951-47a2-b639-7be9040d43f9",
            "49edaec3-18e8-4667-a499-03d7409fa9ea",
            "d2b70df6-f58e-43f8-8e1c-fde77fdfd73d",
            "6390484e-aaae-4453-b911-05b83f221b88",
        },
        4.0: {
            "e52d6c31-5d36-463e-97f4-c5339a6cfe02",
        },
        5.0: {
            "73bc1fe1-c587-49e8-a939-c7c0a28852bb",
        },
    }
    actual_vertical_positions: dict[float, set[str]] = defaultdict(set)
    for node in processed_topology.nodes.values():
        actual_vertical_positions[node.geo_node.y].add(node.uuid)

    assert dict(actual_vertical_positions) == expected_vertical_positions


def test_horizontal_alignment(processed_topology: Topology):
    for node in processed_topology.nodes.values():
        assert len(node.connected_edges) in (1, 3)
        if node.is_point():
            assert node.geo_node.x != node.connected_on_head.geo_node.x
            assert node.geo_node.x != node.connected_on_left.geo_node.x
            assert node.geo_node.x != node.connected_on_right.geo_node.x
            if node.connected_on_head.geo_node.x < node.geo_node.x:
                assert node.connected_on_left.geo_node.x > node.geo_node.x
                assert node.connected_on_right.geo_node.x > node.geo_node.x
            if node.connected_on_head.geo_node.x > node.geo_node.x:
                assert node.connected_on_left.geo_node.x < node.geo_node.x
                assert node.connected_on_right.geo_node.x < node.geo_node.x


def test_breakpoints(processed_topology: Topology):
    for edge in processed_topology.edges.values():
        assert len(edge.intermediate_geo_nodes) < 2
        a_x, a_y = edge.node_a.geo_node.x, edge.node_a.geo_node.y
        b_x, b_y = edge.node_b.geo_node.x, edge.node_b.geo_node.y
        if edge.intermediate_geo_nodes:
            brpt_x, brpt_y = edge.intermediate_geo_nodes[0].x, edge.intermediate_geo_nodes[0].y
            assert (brpt_y == a_y and abs(brpt_y - b_y) == abs(brpt_x - b_x)) or \
                   (brpt_y == b_y and abs(brpt_y - a_y) == abs(brpt_x - a_x))
        if a_y != b_y:
            assert edge.intermediate_geo_nodes      # Does only work for 'complex_example.ppxml' (no existing main tracks)


def test_edge_angles(processed_topology: Topology):
    for edge in processed_topology.edges.values():
        assert edge.node_a.geo_node.y == edge.node_b.geo_node.y or edge.intermediate_geo_nodes
        assert len(edge.intermediate_geo_nodes) < 2

        if edge.intermediate_geo_nodes:
            horizontal_length_a = abs(edge.node_a.geo_node.x - edge.intermediate_geo_nodes[0].x)
            vertical_length_a = abs(edge.node_a.geo_node.y - edge.intermediate_geo_nodes[0].y)
            horizontal_length_b = abs(edge.node_b.geo_node.x - edge.intermediate_geo_nodes[0].x)
            vertical_length_b = abs(edge.node_b.geo_node.y - edge.intermediate_geo_nodes[0].y)

            assert vertical_length_a == 0 or vertical_length_a == horizontal_length_a
            assert vertical_length_b == 0 or vertical_length_b == horizontal_length_b


def test_signal_positions(processed_topology: Topology):
    expected_signals: dict[str, set[str]] = {
        "88d820fc-95b4-408c-b418-a516877de139": {
            "60BS1", "60BS7"
        },
        "3c738175-43c6-4758-a0dd-612a8d494cb9": {
            "60ES1"
        },
        "293c5de6-a5c1-4847-bee5-f92025cb6d5c": {
            "60AS3"
        },
        "e9b773e1-3a4d-4be1-93a2-734a20ecd7fb": {
            "60AS4"
        },
        "e117e570-e2e6-48db-a462-10f5a473a70a": {
            "60AS1"
        },
        "658a6eab-b9d6-4c44-9d02-d67f07338f16": {
            "60AS2"
        },
        "b4315276-78c1-44a6-859f-1152c93bb5a5": {
            "60ES2"
        },
        "61d57b1b-2ae2-4637-897b-abbab41b8e69": {
            "60BS2", "60BS5", "60BS6"
        },
        "66adf559-7dd5-487f-bad7-8e256a8a8f44": {
            "60BS3", "60BS4"
        }
    }

    actual_signals: dict[str, set[str]] = {
        edge.uuid: {signal.name for signal in edge.signals}
        for edge in processed_topology.edges.values()
        if edge.signals
    }

    assert actual_signals == expected_signals