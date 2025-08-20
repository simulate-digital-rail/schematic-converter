from ..datastructures import SchematicGraph, SchematicNode
from ..utils import get_generation_direction


def generate_horizontal_positions(yaramo_graph: SchematicGraph):
    for start_node in sorted(yaramo_graph.start_nodes, key=lambda node: node.new_y):
        _generate_from_node(yaramo_graph, start_node, 0)

    yaramo_graph.reset_generation_helpers()



def _generate_from_node(yaramo_graph: SchematicGraph, node: SchematicNode, horizontal_idx: int) -> None:
    if not all(pred in yaramo_graph.visited for pred in node.predecessors):
        return

    for pred in node.predecessors:
        if pred.is_part_of_main_track and node.is_part_of_main_track and pred.main_track != node.main_track:
            pred_dist = abs(pred.new_y - node.new_y)
        else:
            pred_dist = abs(pred.new_y - node.new_y) + yaramo_graph.get_min_schematic_node_dist(pred, node)
        horizontal_idx = max(horizontal_idx, pred.new_x + pred_dist)

    for pred in node.predecessors:
        both_are_part_of_main_track = pred.is_part_of_main_track and node.is_part_of_main_track
        if pred.new_y != node.new_y and not both_are_part_of_main_track:
            if not yaramo_graph.get_edge(pred, node).intermediate_geo_node:
                yaramo_graph.set_breakpoint(horizontal_idx - abs(pred.new_y - node.new_y), pred.new_y, pred, node)


    node.new_x = horizontal_idx
    yaramo_graph.add_visited_node(node)


    if node.num_successors == 0:
        return

    if node.num_successors == 1:
        next_node = node.successors[0]
        if next_node not in yaramo_graph.visited:
            horizontal_idx += yaramo_graph.get_min_schematic_node_dist(node, next_node)
            _generate_from_node(yaramo_graph, next_node, horizontal_idx)

    if node.num_successors == 2:
        n0, n1 = node.successors
        higher_node, lower_node = (n0, n1) if node.slope_to(n0) < node.slope_to(n1) else (n1, n0)
        first_node, second_node = get_generation_direction(node, higher_node, lower_node)

        if first_node not in yaramo_graph.visited:
            if node.is_part_of_main_track and first_node.is_part_of_main_track:
                horizontal_offset = yaramo_graph.get_min_schematic_node_dist(node, first_node) - 1
            else:
                y_dist = abs(node.new_y - first_node.new_y)
                horizontal_offset = yaramo_graph.get_min_schematic_node_dist(node, first_node) + y_dist
                yaramo_graph.set_breakpoint(horizontal_idx + y_dist, first_node.new_y, node, first_node)
            _generate_from_node(yaramo_graph, first_node, horizontal_idx + horizontal_offset)

        if second_node not in yaramo_graph.visited:
            horizontal_idx += yaramo_graph.get_min_schematic_node_dist(node, second_node)
            _generate_from_node(yaramo_graph, second_node, horizontal_idx)
