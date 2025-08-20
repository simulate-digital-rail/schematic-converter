from yaramo.geo_node import EuclideanGeoNode

from ..datastructures import SchematicGraph, SchematicNode
from ..utils import get_generation_direction


def generate_vertical_positions(yaramo_graph: SchematicGraph):
    for start_node in yaramo_graph.get_start_nodes_in_order():
        vertical_idx = max(
            [max(node.new_y for node in yaramo_graph.visited) if yaramo_graph.visited else -1] +
            [max(breakpoint.y for breakpoint in yaramo_graph.breakpoints) if yaramo_graph.breakpoints else -1]
        )
        _generate_from_node(yaramo_graph, start_node, 0, vertical_idx + 1)

    yaramo_graph.reset_generation_helpers()
    yaramo_graph.reset_intermediate_geo_nodes()



def _generate_from_node(yaramo_graph: SchematicGraph, node: SchematicNode, horizontal_idx: int, vertical_idx: int) -> None:
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
            pred_dist = abs(pred.new_y - vertical_idx) + yaramo_graph.get_min_schematic_node_dist(pred, node)
        horizontal_idx = max(horizontal_idx, pred.new_x + pred_dist)

    for pred in node.predecessors:
        both_are_part_of_main_track = pred.is_part_of_main_track and node.is_part_of_main_track
        if pred.new_y != vertical_idx and not both_are_part_of_main_track:
            if not yaramo_graph.get_edge(pred, node).intermediate_geo_node:
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
            horizontal_idx += yaramo_graph.get_min_schematic_node_dist(node, next_node)
            if any(yaramo_graph.get_edge(p, next_node).intermediate_geo_node for p in next_node.predecessors):
                vertical_idx -= 1
            _generate_from_node(yaramo_graph, next_node, horizontal_idx, vertical_idx)

    if node.num_successors == 2:
        n0, n1 = node.successors
        higher_node, lower_node = (n0, n1) if node.slope_to(n0) < node.slope_to(n1) else (n1, n0)
        first_node, second_node = get_generation_direction(node, higher_node, lower_node)
        dy = -1 if first_node == higher_node else 1

        if first_node not in yaramo_graph.visited:
            if node.is_part_of_main_track and first_node.is_part_of_main_track:
                horizontal_offset = yaramo_graph.get_min_schematic_node_dist(node, first_node) - 1
                vertical_offset = dy * (horizontal_offset)
            else:
                horizontal_offset = yaramo_graph.get_min_schematic_node_dist(node, first_node) + 1
                vertical_offset = dy
                if horizontal_idx < yaramo_graph.max_horizontal_idxs[vertical_idx + vertical_offset]:
                    shift_existing_nodes(vertical_idx + vertical_offset)
                yaramo_graph.set_breakpoint(horizontal_idx + 1, vertical_idx + vertical_offset, node, first_node)
            _generate_from_node(yaramo_graph, first_node, horizontal_idx + horizontal_offset, vertical_idx + vertical_offset)

        if second_node not in yaramo_graph.visited:
            horizontal_idx += yaramo_graph.get_min_schematic_node_dist(node, second_node)
            _generate_from_node(yaramo_graph, second_node, horizontal_idx, vertical_idx)
