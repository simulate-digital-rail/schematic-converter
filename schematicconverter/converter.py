from yaramo.geo_node import EuclideanGeoNode
from yaramo.model import Topology

from schematicconverter.helper import SchematicGraph
from schematicconverter.helper import generate_vertical_positions, generate_horizontal_positions
from schematicconverter.helper import shorten_normal_tracks, stretch_main_tracks
from schematicconverter.helper import process_signals


def convert(topology: Topology, scale_factor: float = 4.5, remove_non_ks_signals: bool = False) -> Topology:
    yaramo_graph = SchematicGraph(topology, remove_non_ks_signals)

    generate_vertical_positions(yaramo_graph)
    generate_horizontal_positions(yaramo_graph)

    shorten_normal_tracks(yaramo_graph)
    stretch_main_tracks(yaramo_graph)
    process_signals(yaramo_graph)
    _normalize_nodes(yaramo_graph, scale_factor)

    for node in yaramo_graph.nodes:
        node.yaramo_node.geo_node = EuclideanGeoNode(node.new_x, node.new_y)

    return topology




def _normalize_nodes(yaramo_graph: SchematicGraph, scale_factor: int):
    min_x = min([node.new_x for node in yaramo_graph.nodes])
    min_y = min([node.new_y for node in yaramo_graph.nodes])
    old_edge_lens = {edge: edge.horizontal_length for edge in yaramo_graph.edges}

    for node in yaramo_graph.nodes:
        node.new_x = (node.new_x - min_x) / scale_factor
        node.new_y = (node.new_y - min_y) / scale_factor

    for edge in filter(lambda edge: edge.intermediate_geo_node, yaramo_graph.edges):
        edge.intermediate_geo_node.x = (edge.intermediate_geo_node.x - min_x) / scale_factor
        edge.intermediate_geo_node.y = (edge.intermediate_geo_node.y - min_y) / scale_factor

    for edge in yaramo_graph.edges:
        for signal in edge.yaramo_edge.signals:
            signal.distance_edge = signal.distance_edge * (edge.horizontal_length / old_edge_lens[edge])
