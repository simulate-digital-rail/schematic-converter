from .datastructures import SchematicNode


def get_generation_direction(
    node: SchematicNode,
    higher_node: SchematicNode,
    lower_node: SchematicNode
) -> tuple[SchematicNode, SchematicNode]:
    if node.is_part_of_main_track:
        if node.main_track == higher_node.main_track:
            return lower_node, higher_node
        if node.main_track == lower_node.main_track:
            return higher_node, lower_node

    if higher_node.height >= lower_node.height:
        return lower_node, higher_node
    return higher_node, lower_node