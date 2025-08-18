import numpy as np
from scipy.optimize import linear_sum_assignment

from yaramo.geo_node import EuclideanGeoNode
from yaramo.model import Topology
from yaramo.signal import Signal

from .helper import SchematicGraph, SchematicNode, SchematicEdge


def convert(topology: Topology, scale_factor: float = 4.5, remove_non_ks_signals: bool = False) -> Topology:
    yaramo_graph = SchematicGraph(topology, remove_non_ks_signals)

    for start_node in yaramo_graph.get_start_nodes_in_order():
        vertical_idx = max(
            [max(node.new_y for node in yaramo_graph.visited) if yaramo_graph.visited else -1] +
            [max(breakpoint.y for breakpoint in yaramo_graph.breakpoints) if yaramo_graph.breakpoints else -1]
        )
        _generate_from_node(yaramo_graph, start_node, 0, vertical_idx + 1)

    _shorten_normal_tracks(yaramo_graph)
    _stretch_main_tracks(yaramo_graph)
    _process_signals(yaramo_graph)
    _normalize_nodes(yaramo_graph, scale_factor)

    for node in yaramo_graph.nodes:
        node.yaramo_node.geo_node = EuclideanGeoNode(node.new_x, node.new_y)

    return topology



def _generate_from_node(
    yaramo_graph: SchematicGraph,
    node: SchematicNode,
    horizontal_idx: int,
    vertical_idx: int
) -> None:
    def get_min_node_dist(node_a: SchematicNode, node_b: SchematicNode) -> int:
        return max(2, yaramo_graph.get_max_num_signals(node_a, node_b) + 1)

    def get_generation_direction(
        node: SchematicNode,
        higher_node: SchematicNode,
        lower_node: SchematicNode
    ) -> tuple[int, SchematicNode, SchematicNode]:
        if node.is_part_of_main_track:
            if node.main_track == higher_node.main_track:
                return 1, lower_node, higher_node
            if node.main_track == lower_node.main_track:
                return -1, higher_node, lower_node

        if yaramo_graph.get_edge(node, higher_node).intermediate_geo_node:
            return -1, higher_node, lower_node
        if yaramo_graph.get_edge(node, lower_node).intermediate_geo_node:
            return 1, lower_node, higher_node

        if higher_node.height >= lower_node.height:
            return 1, lower_node, higher_node
        return -1, higher_node, lower_node

    def shift_existing_nodes(vertical_idx_threshold: int) -> None:
        adjusted_breakpoints: set[EuclideanGeoNode] = set()
        for node in yaramo_graph.visited:
            if node.new_y <= vertical_idx_threshold:
                node.new_y -= 1

                for edge in node.connected_edges:
                    breakpoint = edge.intermediate_geo_node
                    if breakpoint and breakpoint.y <= vertical_idx_threshold and breakpoint not in adjusted_breakpoints:
                        adjusted_breakpoints.add(breakpoint)
                        breakpoint.y -= 1

    if not all(pred in yaramo_graph.visited for pred in node.predecessors):
        yaramo_graph.max_horizontal_idxs[vertical_idx] = float('inf')
        return

    if node.num_predecessors == 2:
        if all(node.original_y <= pred.original_y for pred in node.predecessors):
            vertical_idx = min(node.predecessors[0].new_y, node.predecessors[1].new_y)
        if all(node.original_y >= pred.original_y for pred in node.predecessors):
            vertical_idx = max(node.predecessors[0].new_y, node.predecessors[1].new_y)
        for pred in node.predecessors:
            breakpoint = yaramo_graph.get_edge(pred, node).intermediate_geo_node
            if breakpoint:
                vertical_idx = breakpoint.y

    for pred in node.predecessors:
        if pred.is_part_of_main_track and node.is_part_of_main_track and pred.main_track != node.main_track:
            pred_dist = abs(pred.new_y - vertical_idx)
        else:
            pred_dist = abs(pred.new_y - vertical_idx) + get_min_node_dist(pred, node)
        horizontal_idx = max(horizontal_idx, pred.new_x + pred_dist)

    for pred in node.predecessors:
        both_are_part_of_main_track = pred.is_part_of_main_track and node.is_part_of_main_track
        breakpoint = yaramo_graph.get_edge(pred, node).intermediate_geo_node
        if pred.new_y != vertical_idx and not both_are_part_of_main_track:
            if breakpoint:
                breakpoint.x += abs(vertical_idx - breakpoint.y)
                breakpoint.y = vertical_idx
            else:
                yaramo_graph.set_breakpoint(horizontal_idx - abs(pred.new_y - vertical_idx), pred.new_y, pred, node)
                yaramo_graph.max_horizontal_idxs[pred.new_y] = horizontal_idx - abs(pred.new_y - vertical_idx)


    node.new_x = horizontal_idx
    node.new_y = vertical_idx
    yaramo_graph.add_visited_node(node)


    if node.num_successors == 0:
        return


    if node.num_successors == 1:
        next_node = node.successors[0]
        if next_node not in yaramo_graph.visited:
            horizontal_idx += get_min_node_dist(node, next_node)
            if any(yaramo_graph.get_edge(p, next_node).intermediate_geo_node for p in next_node.predecessors):
                vertical_idx -= 1
            _generate_from_node(yaramo_graph, next_node, horizontal_idx, vertical_idx)


    if node.num_successors == 2:
        n0, n1 = node.successors
        higher_node, lower_node = (n0, n1) if node.slope_to(n0) < node.slope_to(n1) else (n1, n0)
        dy, first_node, second_node = get_generation_direction(node, higher_node, lower_node)

        if first_node not in yaramo_graph.visited:
            if node.is_part_of_main_track and first_node.is_part_of_main_track:
                horizontal_offset = get_min_node_dist(node, first_node) - 1
                vertical_offset = dy * (horizontal_offset)
            else:
                horizontal_offset = get_min_node_dist(node, first_node) + 1
                vertical_offset = dy
                if horizontal_idx < yaramo_graph.max_horizontal_idxs[vertical_idx + vertical_offset]:
                    shift_existing_nodes(vertical_idx + dy)
                yaramo_graph.set_breakpoint(horizontal_idx + 1, vertical_idx + vertical_offset, node, first_node)
            _generate_from_node(yaramo_graph, first_node, horizontal_idx + horizontal_offset, vertical_idx + vertical_offset)

        if second_node not in yaramo_graph.visited:
            horizontal_idx += get_min_node_dist(node, second_node)
            _generate_from_node(yaramo_graph, second_node, horizontal_idx, vertical_idx)



def _stretch_main_tracks(yaramo_graph: SchematicGraph) -> None:
    min_x = min([node.new_x for node in yaramo_graph.nodes])
    max_x = max([node.new_x for node in yaramo_graph.nodes])
    for node in yaramo_graph.nodes:
        if node.is_part_of_main_track and node.is_start_node:
            node.new_x = min_x
        if node.is_part_of_main_track and node.is_end_node:
            node.new_x = max_x


def _shorten_normal_tracks(yaramo_graph: SchematicGraph) -> None:
    def get_default_node_dist(node_a: SchematicNode, node_b: SchematicNode) -> int:
        return max(2, yaramo_graph.get_max_num_signals(node_a, node_b) + 1) + abs(node_a.new_y - node_b.new_y)

    def get_connected_component_without_edge(start: SchematicNode, excluded_edge: SchematicEdge) -> set[SchematicNode]:
        visited: set[SchematicNode] = set()
        stack: list[SchematicNode] = [start]

        while stack:
            node= stack.pop()
            if node not in visited:
                visited.add(node)
                stack.extend(
                    edge.connected_node(node) for edge in node.connected_edges
                    if edge != excluded_edge and edge.connected_node(node) not in visited
                )

        return visited

    for edge in yaramo_graph.edges:
        actual_dist = edge.target.new_x - edge.source.new_x
        overhang_dist = actual_dist - get_default_node_dist(edge.source, edge.target)
        if overhang_dist > 0:
            connected_component = get_connected_component_without_edge(edge.source, edge)
            cc_is_part_of_main_track = any(node.is_part_of_main_track for node in connected_component)
            cc_has_circle = edge.target in connected_component
            if not cc_has_circle and not cc_is_part_of_main_track:
                for n in connected_component:
                    n.new_x += overhang_dist
                    for e in n.successor_edges:
                        if e.intermediate_geo_node and (e != edge or e.intermediate_geo_node.y != n.new_y):
                            e.intermediate_geo_node.x += overhang_dist



def _normalize_nodes(yaramo_graph: SchematicGraph, scale_factor: int):
    min_x = min([node.new_x for node in yaramo_graph.nodes])
    min_y = min([node.new_y for node in yaramo_graph.nodes])
    old_edge_lens = {edge: edge.horizontal_length for edge in yaramo_graph.edges}

    for node in yaramo_graph.nodes:
        node.new_x = (node.new_x - min_x) / (2 * scale_factor)
        node.new_y = (node.new_y - min_y) / scale_factor

    for intermediate_node in [node for edge in yaramo_graph.edges for node in edge.yaramo_edge.intermediate_geo_nodes]:
        intermediate_node.x = (intermediate_node.x - min_x) / (2 * scale_factor)
        intermediate_node.y = (intermediate_node.y - min_y) / scale_factor

    for edge in yaramo_graph.edges:
        for signal in edge.yaramo_edge.signals:
            signal.distance_edge = signal.distance_edge * (edge.horizontal_length / old_edge_lens[edge])


def _process_signals(yaramo_graph: SchematicGraph):
    def _compute_edge_positions(edge: SchematicEdge, signals: list[Signal]):
        if not signals:
            return []

        if edge.horizontal_only_length > 0:
            epsilon = 1 / edge.horizontal_only_length
            available_positions = np.linspace(epsilon, 1 - epsilon, edge.horizontal_only_length - 1)
        else:
            epsilon = 1 / (edge.horizontal_length + 1)
            available_positions = np.linspace(epsilon, 1 - epsilon, edge.horizontal_length + 2)

        positions_input = np.array([signal.distance_edge / edge.yaramo_edge.length for signal in signals])
        cost_matrix = np.abs(positions_input[:, None] - available_positions[None, :])
        row_ind, col_ind = linear_sum_assignment(cost_matrix)
        sorted_indices = np.argsort(row_ind)
        assignment = col_ind[sorted_indices]
        return available_positions[assignment]

    for edge in yaramo_graph.edges:
        signal_positions_against = sorted(_compute_edge_positions(edge, edge.signals_against))
        for idx, signal in enumerate(sorted(edge.signals_against, key=lambda signal: signal.distance_edge)):
            edge.set_signal_position(signal, float(signal_positions_against[idx]))

        signal_positions_in = sorted(_compute_edge_positions(edge, edge.signals_in))
        for idx, signal in enumerate(sorted(edge.signals_in, key=lambda signal: signal.distance_edge)):
            edge.set_signal_position(signal, float(signal_positions_in[idx]))
