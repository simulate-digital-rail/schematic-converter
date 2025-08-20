from ..datastructures import SchematicEdge, SchematicGraph, SchematicNode


def stretch_main_tracks(yaramo_graph: SchematicGraph) -> None:
    min_x = min([node.new_x for node in yaramo_graph.nodes])
    max_x = max([node.new_x for node in yaramo_graph.nodes])
    for node in yaramo_graph.nodes:
        if node.is_part_of_main_track and node.is_start_node:
            node.new_x = min_x
        if node.is_part_of_main_track and node.is_end_node:
            node.new_x = max_x



def shorten_normal_tracks(yaramo_graph: SchematicGraph) -> None:
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
            cc_has_cycle = edge.target in connected_component
            if not cc_has_cycle and not cc_is_part_of_main_track:
                for node in connected_component:
                    node.new_x += overhang_dist
                    for e in node.successor_edges:
                        if e.intermediate_geo_node and (e != edge or e.intermediate_geo_node.y != node.new_y):
                            e.intermediate_geo_node.x += overhang_dist
