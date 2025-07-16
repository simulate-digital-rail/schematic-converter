from __future__ import annotations
from math import sqrt

from yaramo.node import Node as YaramoNode
from yaramo.edge import Edge as YaramoEdge
from yaramo.track import Track as YaramoTrack, TrackType
from yaramo.signal import Signal as YaramoSignal, SignalDirection
from yaramo.geo_node import EuclideanGeoNode


class HelperNode:
    def __init__(self, yaramo_node: YaramoNode):
        self.yaramo_node: YaramoNode = yaramo_node
        self.new_x: float = self.original_x
        self.new_y: float = self.original_y
        self.depth: int = None
        self.height: int = None
        self._tracks: set[YaramoTrack] = set()
        self._connected_edges: set[HelperEdge] = set()
        self._predecessors: list[HelperNode] = list()
        self._successors: list[HelperNode] = list()
        self._reachable_start_nodes: set[HelperNode] = set()

    @property
    def uuid(self) -> str:
        return self.yaramo_node.uuid

    @property
    def name(self) -> str:
        return self.yaramo_node.name

    @property
    def original_x(self) -> str:
        return self.yaramo_node.geo_node.x

    @original_x.setter
    def original_x(self, x) -> str:
        self.yaramo_node.geo_node.x = x

    @property
    def original_y(self) -> str:
        return self.yaramo_node.geo_node.y

    @original_y.setter
    def original_y(self, y) -> str:
        self.yaramo_node.geo_node.y = y

    @property
    def original_coords(self) -> tuple[float, float]:
        return (self.original_x, self.original_y)

    @property
    def tracks(self) -> set[YaramoTrack]:
        return self._tracks

    def add_track(self, track: YaramoTrack) -> None:
        if self.is_part_of_main_track and track.track_type == TrackType.Durchgehendes_Hauptgleis:
            raise ValueError("Current implementation does not allow nodes that are part of two main tracks.")
        self._tracks.add(track)

    @property
    def main_track(self) -> bool:
        main_tracks = [track for track in self.tracks if track.track_type == TrackType.Durchgehendes_Hauptgleis]
        return main_tracks[0] if main_tracks else None

    @property
    def is_part_of_main_track(self) -> bool:
        return bool(self.main_track)

    @property
    def connected_edges(self) -> set:
        return self._connected_edges

    def add_connected_edge(self, connected_edge) -> None:
        assert len(self._connected_edges) < 3, "A node can only have a maximum of 3 connected edges."
        self._connected_edges.add(connected_edge)

    @property
    def connected_nodes(self) -> set:
        return {edge.connected_node(self) for edge in self.connected_edges}

    @property
    def predecessors(self) -> list[HelperNode]:
        return self._predecessors

    def add_predecessor(self, predecessor) -> None:
        assert self.num_predecessors < 2, "A node can only have a maximum of 2 predecessors."
        self._predecessors.append(predecessor)

    @property
    def num_predecessors(self) -> int:
        return len(self._predecessors)

    @property
    def successors(self) -> list[HelperNode]:
        return self._successors

    def add_successor(self, successor) -> None:
        assert self.num_successors < 2, "A node can only have a maximum of 2 successors."
        self._successors.append(successor)

    @property
    def num_successors(self) -> int:
        return len(self._successors)

    @property
    def reachable_start_nodes(self) -> list[HelperNode]:
        return self._reachable_start_nodes

    def add_reachable_start_node(self, start_node) -> None:
        self._reachable_start_nodes.add(start_node)

    @property
    def is_start_node(self) -> bool:
        return self.num_predecessors == 0

    @property
    def is_end_node(self) -> bool:
        return self.num_successors == 0    

    def get_edge_to(self, other_node) -> HelperEdge:
        for edge in self.connected_edges:
            if edge.source == other_node or edge.target == other_node:
                return edge
        raise ValueError("Given nodes are not directly connected to each other.")

    def slope_to(self, other_node) -> float:
        if self.original_x == other_node.original_x:
            raise ValueError("Current implementation does not support connected nodes that have the same y axis position.")
        return (other_node.original_y - self.original_y) / (other_node.original_x - self.original_x)


class HelperEdge:
    def __init__(
        self,
        yaramo_edge: YaramoEdge,
        helper_node_a: HelperNode,
        helper_node_b: HelperNode
    ):
        self.yaramo_edge: YaramoEdge = yaramo_edge
        self.source, self.target = sorted((helper_node_a, helper_node_b), key=lambda node: node.original_x)
        self.signals_in: set[YaramoSignal] = {
            signal for signal in self.yaramo_edge.signals
            if (signal.direction == SignalDirection.IN and self.source.yaramo_node == self.yaramo_edge.node_a) or
               (signal.direction == SignalDirection.GEGEN and self.source.yaramo_node == self.yaramo_edge.node_b)
        }
        self.signals_against: set[YaramoSignal] = {
            signal for signal in self.yaramo_edge.signals
            if (signal.direction == SignalDirection.GEGEN and self.source.yaramo_node == self.yaramo_edge.node_a) or
               (signal.direction == SignalDirection.IN and self.source.yaramo_node == self.yaramo_edge.node_b)
        }
        yaramo_edge.intermediate_geo_nodes = []

    @property
    def uuid(self) -> str:
        return self.yaramo_edge.uuid

    @property
    def name(self) -> str:
        return self.yaramo_edge.name

    @property
    def max_num_signals(self) -> int:
        return max(len(self.signals_in), len(self.signals_against))

    @property
    def intermediate_geo_node(self) -> EuclideanGeoNode:
        return self.yaramo_edge.intermediate_geo_nodes[0] if self.yaramo_edge.intermediate_geo_nodes else None

    @intermediate_geo_node.setter
    def intermediate_geo_node(self, node: EuclideanGeoNode):
        self.yaramo_edge.intermediate_geo_nodes = []
        self.yaramo_edge.intermediate_geo_nodes.append(node)

    @property
    def is_straight(self) -> bool:
        return bool(self.intermediate_geo_node)

    @property
    def horizontal_length(self) -> float:
        return abs(self.target.new_x - self.source.new_x)

    @property
    def horizontal_only_length(self) -> float:
        return abs(self.source.new_x - self.target.new_x) - abs(self.source.new_y - self.target.new_y)

    def connected_node(self, node: HelperNode) -> HelperNode:
        if node not in (self.source, self.target):
            raise ValueError(f"Given node is not connected to this edge.")
        return self.target if node == self.source else self.source

    def intersects_strictly(self, other_edge) -> bool:
        def direction(a, b, c):
            def cross(a, b):
                return a[0]*b[1] - a[1]*b[0]
            
            def subtract(a, b):
                return (a[0] - b[0], a[1] - b[1])
            
            return cross(subtract(c, a), subtract(b, a))

        if self == other_edge:
            return False

        e1_source = self.source.original_coords
        e1_target = self.target.original_coords
        e2_source = other_edge.source.original_coords
        e2_target = other_edge.target.original_coords

        dir1 = direction(e1_source, e1_target, e2_source)
        dir2 = direction(e1_source, e1_target, e2_target)
        dir3 = direction(e2_source, e2_target, e1_source)
        dir4 = direction(e2_source, e2_target, e1_target)

        return (dir1 * dir2 < 0) and (dir3 * dir4 < 0)

    def set_signal_position(self, signal: YaramoSignal, relative_distance: float) -> None:
        if signal not in self.yaramo_edge.signals:
            raise ValueError(f"Given signal {signal.name} not found in edge {self.yaramo_edge.uuid[-5:]}.")
        if not 0 <= relative_distance <= 1:
            raise ValueError(f"Parameter 'relative_distance' has to be in range between 0 and 1.")
        if self.is_straight:
            if self.source.new_y == self.intermediate_geo_node.y:
                signal.distance_edge = relative_distance * abs(self.source.new_x - self.intermediate_geo_node.x)
                if self.yaramo_edge.node_a == self.target.yaramo_node:
                    signal.distance_edge = signal.distance_edge + (self.horizontal_length - self.horizontal_only_length)
            elif self.target.new_y == self.intermediate_geo_node.y:
                signal.distance_edge = relative_distance * abs(self.target.new_x - self.intermediate_geo_node.x)
                if self.yaramo_edge.node_a == self.source.yaramo_node:
                    signal.distance_edge = signal.distance_edge + (self.horizontal_length - self.horizontal_only_length)
            else:
                raise ValueError("Detected breakpoint that is not aligned properly.")
        else:
            signal.distance_edge = relative_distance * abs(self.source.new_x - self.target.new_x)
