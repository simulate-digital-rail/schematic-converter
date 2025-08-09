import numpy as np
from scipy.optimize import linear_sum_assignment
from typing import Literal

from yaramo.geo_node import EuclideanGeoNode
from yaramo.model import Topology
from yaramo.signal import Signal

from .helper import SchematicGraph, SchematicNode, SchematicEdge


def convert(topology: Topology, scale_factor: float = 4.5, remove_non_ks_signals: bool = False) -> Topology:
    yaramo_graph = SchematicGraph(topology, remove_non_ks_signals)
    visited: set[SchematicNode] = set()

    # for start_node in yaramo_graph.get_start_nodes_in_order():
    #     vertical_idx = max(node.new_y for node in visited) + 1 if visited else 0
    #     _generate_from_node(yaramo_graph, start_node, 0, vertical_idx, visited)

    # # _shorten_normal_tracks()
    # _stretch_main_tracks(yaramo_graph)
    # _process_signals(yaramo_graph)
    # _normalize_nodes(yaramo_graph, scale_factor)

    # for node in yaramo_graph.nodes:
    #     node.yaramo_node.geo_node = EuclideanGeoNode(node.new_x, node.new_y)

    for node in yaramo_graph.nodes:
        print(node.yaramo_node.geo_node.x, node.yaramo_node.geo_node.y)
        node.yaramo_node.geo_node = EuclideanGeoNode(
            node.yaramo_node.geo_node.x * 3,
            node.yaramo_node.geo_node.y * 3
        )

    return topology



def _generate_from_node(
    yaramo_graph: SchematicGraph,
    node: SchematicNode,
    horizontal_idx: int,
    vertical_idx: int,
    visited: set[SchematicNode]
) -> None:
    def get_min_node_dist(node_a: SchematicNode, node_b: SchematicNode) -> int:
        return max(2, yaramo_graph.get_max_num_signals(node_a, node_b) + 1)

    def set_breakpoint(x: int, y: int, start_node: SchematicNode, end_node: SchematicNode) -> None:
        yaramo_graph.get_edge(start_node, end_node).intermediate_geo_node = EuclideanGeoNode(x, y)

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

        if higher_node.height >= lower_node.height:
            return 1, lower_node, higher_node
        return -1, higher_node, lower_node

    def shift_existing_nodes(vertical_idx_threshold: int, direction: Literal["higher", "lower"]) -> None:
        adjusted_breakpoints: set[EuclideanGeoNode] = set()
        y_shift = 1 if direction == "lower" else -1
        
        for node in visited:
            if (direction == "lower" and node.new_y >= vertical_idx_threshold) or \
               (direction == "higher" and node.new_y <= vertical_idx_threshold):
                node.new_x += 1
                node.new_y += y_shift

                for edge in node.connected_edges:
                    breakpoint = edge.intermediate_geo_node
                    if breakpoint and breakpoint not in adjusted_breakpoints:
                        adjusted_breakpoints.add(breakpoint)
                        breakpoint.x += 1
                        breakpoint.y += y_shift



    if not all(pred in visited for pred in node.predecessors):
        return

    if node.num_predecessors == 2:
        if all(node.original_y <= pred.original_y for pred in node.predecessors):
            vertical_idx = min(node.predecessors[0].new_y, node.predecessors[1].new_y)
        if all(node.original_y >= pred.original_y for pred in node.predecessors):
            vertical_idx = max(node.predecessors[0].new_y, node.predecessors[1].new_y)

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
                set_breakpoint(horizontal_idx - abs(pred.new_y - vertical_idx), pred.new_y, pred, node)

        # TODO: write this cleaner, there is a bug:
        # pred_breakpoint = yaramo_graph.get_edge(pred, node).intermediate_geo_node
        # print(yaramo_graph.get_edge(pred, node).uuid[-5:])
        # if pred_breakpoint and pred_breakpoint.y > pred.new_y and vertical_idx - pred_breakpoint.y > 0:
        #     pred_breakpoint.x += vertical_idx - pred_breakpoint.x
        #     pred_breakpoint.y = vertical_idx
        #     for abc in visited:
        #         if abc.new_x < pred_breakpoint.x and abc.new_y >= pred_breakpoint.y:
        #             abc.new_y += 1



    node.new_x = horizontal_idx
    node.new_y = vertical_idx
    visited.add(node)


    if node.num_successors == 0:
        return


    if node.num_successors == 1:
        next_node = node.successors[0]
        if next_node not in visited:
            horizontal_idx += get_min_node_dist(node, next_node)
            if any(yaramo_graph.get_edge(p, next_node).intermediate_geo_node for p in next_node.predecessors):
                vertical_idx -= 1
            _generate_from_node(yaramo_graph, next_node, horizontal_idx, vertical_idx, visited)


    if node.num_successors == 2:
        n0, n1 = node.successors
        higher_node, lower_node = (n0, n1) if node.slope_to(n0) < node.slope_to(n1) else (n1, n0)
        dy, first_node, second_node = get_generation_direction(node, higher_node, lower_node)

        if first_node not in visited:
            if node.is_part_of_main_track and first_node.is_part_of_main_track:
                horizontal_offset = get_min_node_dist(node, first_node) - 1
                vertical_offset = dy * (horizontal_offset)
            else:
                horizontal_offset = get_min_node_dist(node, first_node) + 1
                vertical_offset = dy
                if any(n.new_y == vertical_idx + dy for n in visited):
                    direction = "higher" if first_node == higher_node else "lower"
                    # shift_existing_nodes(vertical_idx + dy, direction)
                set_breakpoint(horizontal_idx + 1, vertical_idx + dy, node, first_node)
            _generate_from_node(
                yaramo_graph,
                first_node,
                horizontal_idx + horizontal_offset,
                vertical_idx + vertical_offset,
                visited
            )

        if second_node not in visited:
            horizontal_idx += get_min_node_dist(node, second_node)
            _generate_from_node(yaramo_graph, second_node, horizontal_idx, vertical_idx, visited)
























def _stretch_main_tracks(yaramo_graph: SchematicGraph) -> None:
    min_x = min([node.new_x for node in yaramo_graph.nodes])
    max_x = max([node.new_x for node in yaramo_graph.nodes])
    for node in yaramo_graph.nodes:
        if node.is_part_of_main_track and node.is_start_node:
            node.new_x = min_x
        if node.is_part_of_main_track and node.is_end_node:
            node.new_x = max_x

def _shorten_normal_tracks() -> None:
    # TODO: Fix this, there are many edge cases
    pass
    # overhang_nodes = {}
    # for node in self.nodes:
    #     for succ in node.successors:
    #         req_dist = max(2, self.get_max_num_signals(node, succ) + 1) + abs(node.y - succ.y)
    #         overhang = (succ.x - node.x) - req_dist
    #         if node in overhang_nodes:
    #             if overhang > overhang_nodes[node]:
    #                 overhang_nodes.update({node: overhang})
    #         else:
    #             if not (node.is_part_of_main_track and succ.is_part_of_main_track) and \
    #             not (node.corresponding_start_nodes == succ.corresponding_start_nodes):
    #                 overhang_nodes.update({node: overhang})

    # for overhang_node, overhang in overhang_nodes.items():
    #     for node in self.nodes:
    #         if node.corresponding_start_nodes <= overhang_node.corresponding_start_nodes:
    #             fixed_breakpoints = [
    #                 f"{overhang_node.id}-{succ.id}"
    #                 for succ in overhang_node.successors
    #                 if succ.corresponding_start_nodes > overhang_node.corresponding_start_nodes
    #             ]
    #             if not node.id in fixed_breakpoints:
    #                 node.x += overhang

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

        if edge.horizontal_only_length <= 0:
            if edge.max_num_signals > 1:
                raise ValueError("Current implementation only supports a maximum of one node per side on diagonal edges.")
            return [0.5]

        epsilon = 1 / (edge.horizontal_only_length)
        available_positions = np.linspace(epsilon, 1 - epsilon, edge.horizontal_only_length - 1)
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
