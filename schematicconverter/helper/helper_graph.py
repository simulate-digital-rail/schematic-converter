from collections import defaultdict, deque

from yaramo.model import Topology as YaramoTopology
from yaramo.signal import SignalSystem

from .helper_graph_elements import HelperNode, HelperEdge


class HelperGraph:
    def __init__(self, topology: YaramoTopology, remove_non_ks_signals: bool = True):
        self.topology: YaramoTopology = topology
        self.nodes: set[HelperNode] = set()
        self.edges: set[HelperEdge] = set()

        self._process_planpro_topology(remove_non_ks_signals=remove_non_ks_signals)
        self._compute_graph_properties()


    def add_node(self, node: HelperNode) -> None:
        self.nodes.add(node)

    def add_edge(self, edge: HelperEdge) -> None:
        edge.source.add_connected_edge(edge)
        edge.target.add_connected_edge(edge)
        self.edges.add(edge)

    @property
    def start_nodes(self) -> set[HelperNode]:
        return {node for node in self.nodes if len(node.predecessors) == 0}

    def get_element_by_id(self, uuid: str) -> HelperNode | HelperEdge | None:
        for object in set.union(self.nodes, self.edges):
            if object.uuid == uuid:
                return object
        return None

    def get_edge(self, node_a: HelperNode, node_b: HelperNode) -> HelperEdge | None:
        for edge in self.edges:
            if {edge.source, edge.target} == {node_a, node_b}:
                return edge
        return None

    def remove_edge(self, node_a: HelperNode, node_b: HelperNode) -> str:
        edge = self.get_edge(node_a, node_b)
        if edge is None:
            raise ValueError(f"Edge between the given nodes not found.")

        self.edges.remove(edge)
        edge.source.connected_edges.remove(edge)
        edge.target.connected_edges.remove(edge)

        return edge.uuid

    def get_max_num_signals(
        self,
        node_a: HelperNode,
        node_b: HelperNode,
    ) -> int:
        if node_b not in node_a.connected_nodes:
            raise ValueError(f"Edge between {node_a} and {node_b} not found.")
        return self.get_edge(node_a, node_b).max_num_signals
            


    def get_start_nodes_in_order(self):
        """
        It is very important that we know the correct subsequent order of the start nodes along the y-axis
        even before we start generating the schematic overview.
        """
        def get_cover_nodes():
            """
            Determine a minimum set of nodes so that all start nodes can reach at least one element from this set.
            """
            reachable_from_start = defaultdict(set)
            for sp in self.start_nodes:
                visited = set()
                stack = [sp]
                while stack:
                    curr = stack.pop()
                    if curr in visited:
                        continue
                    visited.add(curr)
                    reachable_from_start[sp].add(curr)

                    for succ in curr.successors:
                        edge: HelperEdge = curr.get_edge_to(succ)
                        if not any(edge.intersects_strictly(e) for e in self.edges):
                            stack.extend([succ])

            reached_by = defaultdict(set)
            for sp, nodes in reachable_from_start.items():
                for node in nodes:
                    reached_by[node].add(sp)

            start_set = set(self.start_nodes)
            full_cover_nodes: list[HelperNode] = [node for node, covered in reached_by.items() if covered == start_set]
            if full_cover_nodes:
                return [min(full_cover_nodes, key=lambda n: (n.depth, n.name))]

            uncovered = set(self.start_nodes)
            selected_nodes = []
            candidates = sorted(reached_by.items(), key=lambda x: (x[0].depth, x[0].name))

            while uncovered:
                best_node, best_coverage = None, set()
                for node, covers in candidates:
                    new_coverage = covers & uncovered
                    if len(new_coverage) > len(best_coverage) or (
                        len(new_coverage) == len(best_coverage) and best_node and
                        (node.depth, node.name) < (best_node.depth, best_node.name)
                    ):
                        best_node, best_coverage = node, new_coverage
                if not best_node:
                    break
                selected_nodes.append(best_node)
                uncovered -= best_coverage

            return selected_nodes
        
        def _traverse_predecessors(node, visited, result):
            if node in visited:
                return
            visited.add(node)
            if node.num_predecessors == 0 and node not in result:
                result.append(node)
            for pred in sorted(node.predecessors, key=lambda pred: pred.slope_to(node), reverse=True):
                _traverse_predecessors(pred, visited, result)

        result = []
        for node in sorted(get_cover_nodes(), key=lambda node: node.original_y):
            visited = set()
            _traverse_predecessors(node, visited, result)
        
        return result


    def _process_planpro_topology(self, remove_non_ks_signals: bool) -> None:
        def _compute_nodes() -> None:
            for node in self.topology.nodes.values():
                self.add_node(HelperNode(node))
            
            min_x = min([node.original_x for node in self.nodes])
            max_x = max([node.original_x for node in self.nodes])
            min_y = min([node.original_y for node in self.nodes])
            max_y = max([node.original_y for node in self.nodes])
            for node in self.nodes:
                node.original_x = (node.original_x - min_x) / (max_x - min_x or 1)
                node.original_y = 1 - ((node.original_y - min_y) / (max_y - min_y or 1))
                node.new_x = node.original_x
                node.new_y = node.original_y

        def _compute_edges() -> None:
            for yaramo_edge in self.topology.edges.values():
                if remove_non_ks_signals:
                    for yaramo_signal in yaramo_edge.signals:
                        if yaramo_signal.system != SignalSystem.Ks:
                            yaramo_edge.signals.remove(yaramo_signal)
                            self.topology.signals.pop(yaramo_signal.uuid)
                self.add_edge(HelperEdge(
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
            def compute_height(node: HelperNode):
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

        # Check if this is necessary. Maybe useful when implementing the shorten_tracks() method
        def _compute_reachable_start_nodes():
            def dfs(node: HelperNode, start: HelperNode, visited: set[HelperNode]):
                if node in visited:
                    return
                visited.add(node)
                node.add_reachable_start_node(start)
                for succ in node.successors:
                    dfs(succ, start, visited)

            for start_node in self.start_nodes:
                visited = set()
                dfs(start_node, start_node, visited)


        _compute_predecessors_and_successors()
        _compute_heights()
        _compute_depths()
        _compute_reachable_start_nodes()
