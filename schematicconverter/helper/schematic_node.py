from __future__ import annotations
from typing import TYPE_CHECKING

from yaramo.geo_node import EuclideanGeoNode
from yaramo.node import Node as YaramoNode
from yaramo.track import Track as YaramoTrack, TrackType

if TYPE_CHECKING:
    from .schematic_edge import SchematicEdge


class SchematicNode:
    def __init__(self, yaramo_node: YaramoNode):
        self.yaramo_node: YaramoNode = yaramo_node
        self.new_x: float = self.original_x
        self.new_y: float = self.original_y
        self.height: int = None
        self._tracks: set[YaramoTrack] = set()
        self._connected_edges: set[SchematicEdge] = set()
        self._predecessors: list[SchematicNode] = list()
        self._successors: list[SchematicNode] = list()
        self._reachable_nodes: set[SchematicNode] = set()
        self._reaching_nodes: set[SchematicNode] = set()

    @property
    def uuid(self) -> str:
        return self.yaramo_node.uuid

    @property
    def name(self) -> str:
        return self.yaramo_node.name

    @property
    def original_x(self) -> float:
        return self.yaramo_node.geo_node.x

    @original_x.setter
    def original_x(self, x) -> None:
        self.yaramo_node.geo_node.x = x

    @property
    def original_y(self) -> float:
        return self.yaramo_node.geo_node.y

    @original_y.setter
    def original_y(self, y) -> None:
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
    def main_track(self) -> YaramoTrack | None:
        main_tracks = [track for track in self.tracks if track.track_type == TrackType.Durchgehendes_Hauptgleis]
        return main_tracks[0] if main_tracks else None

    @property
    def is_part_of_main_track(self) -> bool:
        return bool(self.main_track)

    @property
    def connected_edges(self) -> set[SchematicEdge]:
        return self._connected_edges

    def add_connected_edge(self, connected_edge) -> None:
        assert len(self._connected_edges) < 3, "A node can only have a maximum of 3 connected edges."
        self._connected_edges.add(connected_edge)

    @property
    def connected_nodes(self) -> set[SchematicNode]:
        return {edge.connected_node(self) for edge in self.connected_edges}

    @property
    def predecessors(self) -> list[SchematicNode]:
        return self._predecessors

    def add_predecessor(self, predecessor) -> None:
        assert self.num_predecessors < 2, "A node can only have a maximum of 2 predecessors."
        self._predecessors.append(predecessor)

    @property
    def num_predecessors(self) -> int:
        return len(self._predecessors)

    @property
    def predecessor_edges(self) -> set[SchematicEdge]:
        return {e for e in self.connected_edges if e.target == self}

    @property
    def successors(self) -> list[SchematicNode]:
        return self._successors

    def add_successor(self, successor) -> None:
        assert self.num_successors < 2, "A node can only have a maximum of 2 successors."
        self._successors.append(successor)

    @property
    def num_successors(self) -> int:
        return len(self._successors)

    @property
    def successor_edges(self) -> set[SchematicEdge]:
        return {e for e in self.connected_edges if e.source == self}

    @property
    def reachable_nodes(self) -> set[SchematicNode]:
        return self._reachable_nodes

    def add_reachable_node(self, node) -> None:
        self._reachable_nodes.add(node)

    @property
    def reaching_nodes(self) -> set[SchematicNode]:
        return self._reaching_nodes

    def add_reaching_node(self, node) -> None:
        self._reaching_nodes.add(node)

    @property
    def is_start_node(self) -> bool:
        return self.num_predecessors == 0

    @property
    def is_end_node(self) -> bool:
        return self.num_successors == 0    

    def get_edge_to(self, other_node: SchematicNode) -> SchematicEdge:
        for edge in self.connected_edges:
            if other_node in (edge.source, edge.target):
                return edge
        raise ValueError("Given nodes are not directly connected to each other.")

    def slope_to(self, other_node: SchematicNode | EuclideanGeoNode) -> float:
        if isinstance(other_node, SchematicNode):
            x, y = other_node.original_x, other_node.original_y
        elif isinstance(other_node, EuclideanGeoNode):
            x, y = other_node.x, other_node.y
        else:
            raise ValueError("Provided invalid node.")

        if self.original_x == x:
            return 0

        return (y - self.original_y) / (x - self.original_x)
