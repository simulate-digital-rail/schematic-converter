from collections import deque
from itertools import combinations
from statistics import mean

from yaramo.model import Topology as YaramoTopology
from yaramo.signal import SignalSystem

from .schematic_edge import SchematicEdge
from .schematic_node import SchematicNode


class SchematicGraph:
    def __init__(self, topology: YaramoTopology, remove_non_ks_signals: bool = True):
        self.topology: YaramoTopology = topology
        self.nodes: set[SchematicNode] = set()
        self.edges: set[SchematicEdge] = set()

        self._process_planpro_topology(remove_non_ks_signals=remove_non_ks_signals)
        self._compute_graph_properties()

    def add_node(self, node: SchematicNode) -> None:
        self.nodes.add(node)

    def add_edge(self, edge: SchematicEdge) -> None:
        edge.source.add_connected_edge(edge)
        edge.target.add_connected_edge(edge)
        self.edges.add(edge)

    @property
    def start_nodes(self) -> set[SchematicNode]:
        return {node for node in self.nodes if len(node.predecessors) == 0}

    def get_element_by_id(self, uuid: str) -> SchematicNode | SchematicEdge | None:
        for object in set.union(self.nodes, self.edges):
            if object.uuid == uuid:
                return object
        return None

    def get_edge(self, node_a: SchematicNode, node_b: SchematicNode) -> SchematicEdge | None:
        for edge in self.edges:
            if {edge.source, edge.target} == {node_a, node_b}:
                return edge
        return None

    def get_max_num_signals(self, node_a: SchematicNode, node_b: SchematicNode) -> int:
        if node_b not in node_a.connected_nodes:
            raise ValueError(f"Edge between {node_a.uuid} and {node_b.uuid} not found.")
        return self.get_edge(node_a, node_b).max_num_signals

    def get_start_nodes_in_order(self):
        """
        It is very important that we know the correct subsequent order of the start nodes along the y-axis
        even before we start generating the schematic overview.
        """
        def get_start_node_reachability() -> dict[SchematicNode, set[SchematicNode]]:
            reachable_nodes = {}

            for start in self.start_nodes:
                visited = set()
                reachable = set()
                stack = [start]

                while stack:
                    current = stack.pop()
                    for succ in current.successors:
                        edge = self.get_edge(current, succ)
                        if succ not in visited and not any(edge.intersects_strictly(e) for e in self.edges):
                            visited.add(succ)
                            reachable.add(succ)
                            stack.append(succ)

                reachable_nodes[start] = reachable

            return reachable_nodes

        def find_minimal_cover() -> list[SchematicNode]:
            """Finds a minimal set of nodes that can be reached from all start nodes."""
            reachable_nodes = get_start_node_reachability()
            reachable_sets = [reachable_nodes[start_node] for start_node in self.start_nodes]
            for size in range(1, len(self.start_nodes) + 1):
                for combo in combinations(self.nodes, size):
                    if all(set(combo) & reachable for reachable in reachable_sets):
                        return list(combo)


        def collect_predecessors(node: SchematicNode, visited: set[SchematicNode], result: list[SchematicNode]) -> None:
            """Recursively traverses predecessors in descending slope order and collects start nodes."""
            if node in visited:
                return
            visited.add(node)

            if node.is_start_node and node not in result:
                result.append(node)

            for pred in sorted(node.predecessors, key=lambda pred: node.slope_to(pred), reverse=True):
                edge = self.get_edge(pred, node)
                if not any(edge.intersects_strictly(e) for e in self.edges):
                    collect_predecessors(pred, visited, result)

        cover_nodes = sorted(
            find_minimal_cover(),
            key=lambda node: mean([n.original_y for n in node.reaching_nodes])
        )
        result = []
        for node in cover_nodes:
            collect_predecessors(node, set(), result)

        return result


    def _process_planpro_topology(self, remove_non_ks_signals: bool) -> None:
        def _compute_nodes() -> None:
            for node in self.topology.nodes.values():
                self.add_node(SchematicNode(node))
            
            xs = [node.original_x for node in self.nodes]
            ys = [node.original_y for node in self.nodes]
            min_x, max_x = min(xs), max(xs)
            min_y, max_y = min(ys), max(ys)

            for node in self.nodes:
                node.original_x = (node.original_x - min_x) / (max_x - min_x or 1)
                node.original_y = 1 - ((node.original_y - min_y) / (max_y - min_y or 1))
                node.new_x = node.original_x
                node.new_y = node.original_y

        def _compute_edges() -> None:
            for yaramo_edge in self.topology.edges.values():
                if remove_non_ks_signals:
                    for idx in reversed(range(len(yaramo_edge.signals))):
                        yaramo_signal = yaramo_edge.signals[idx]
                        if yaramo_signal.system != SignalSystem.Ks:
                            yaramo_edge.signals.pop(idx)
                            self.topology.signals.pop(yaramo_signal.uuid)
                self.add_edge(SchematicEdge(
                    yaramo_edge=yaramo_edge,
                    helper_node_a=self.get_element_by_id(yaramo_edge.node_a.uuid),
                    helper_node_b=self.get_element_by_id(yaramo_edge.node_b.uuid)
                ))

        def _compute_tracks():
            for yaramo_track in self.topology.tracks.values():
                for yaramo_node in yaramo_track.nodes:
                    self.get_element_by_id(yaramo_node.uuid).add_track(yaramo_track)


        _compute_nodes()
        _compute_edges()
        _compute_tracks()



    def _compute_graph_properties(self) -> None:
        def _compute_predecessors_and_successors():
            for node in self.nodes:
                for edge in node.connected_edges:
                    neighbor = edge.connected_node(node)
                    if (neighbor.original_x, neighbor.original_y) < (node.original_x, node.original_y):
                        node.add_predecessor(neighbor)
                    elif (neighbor.original_x, neighbor.original_y) > (node.original_x, node.original_y):
                        node.add_successor(neighbor)

        def _compute_heights():
            def compute_height(node: SchematicNode):
                if node.height is not None:
                    return node.height
                if not node.successors:
                    node.height = 0
                else:
                    node.height = 1 + max(compute_height(child) for child in node.successors)
                return node.height

            for node in self.nodes:
                compute_height(node)

        def _compute_depths():
            queue = deque()

            for start_node in self.start_nodes:
                start_node.depth = 0
                queue.append(start_node)

            while queue:
                current_node = queue.popleft()
                for neighbor in current_node.connected_nodes: # TODO: Check if only successors are enough 
                    if neighbor.depth is None and all(pred.depth is not None for pred in neighbor.predecessors):
                        neighbor.depth = current_node.depth + 1
                        queue.append(neighbor)

        def _compute_reachability():
            computed_reachability = {}

            def get_reachable_nodes(node: SchematicNode):
                if node in computed_reachability:
                    return computed_reachability[node]

                reachable = set()
                for successor in node.successors:
                    reachable.add(successor)
                    reachable.update(get_reachable_nodes(successor))

                computed_reachability[node] = reachable
                return reachable

            # Compute forward reachability
            for node in self.nodes:
                reachable_nodes = get_reachable_nodes(node)
                for reachable_node in reachable_nodes:
                    node.add_reachable_node(reachable_node)

            # Compute backward reachability
            for node in self.nodes:
                for reachable_node in node.reachable_nodes:
                    reachable_node.add_reaching_node(node)


        _compute_predecessors_and_successors()
        _compute_heights()
        _compute_depths()
        _compute_reachability()
