from __future__ import annotations
from typing import TYPE_CHECKING

from yaramo.edge import Edge as YaramoEdge
from yaramo.signal import Signal as YaramoSignal, SignalDirection
from yaramo.geo_node import EuclideanGeoNode

if TYPE_CHECKING:
    from .schematic_node import SchematicNode


class SchematicEdge:
    def __init__(
        self,
        yaramo_edge: YaramoEdge,
        helper_node_a: SchematicNode,
        helper_node_b: SchematicNode
    ):
        self.yaramo_edge: YaramoEdge = yaramo_edge
        self.source, self.target = sorted(
            (helper_node_a, helper_node_b), key=lambda node: (node.original_x, node.original_y)
        )
        self.signals_in: set[YaramoSignal] = {
            signal for signal in self.yaramo_edge.signals
            if (signal.direction == SignalDirection.IN and self.source.yaramo_node == self.yaramo_edge.node_a) or
               (signal.direction == SignalDirection.GEGEN and self.source.yaramo_node == self.yaramo_edge.node_b)
        }
        self.signals_against: set[YaramoSignal] = {
            signal for signal in self.yaramo_edge.signals
            if (signal.direction == SignalDirection.IN and self.source.yaramo_node == self.yaramo_edge.node_b) or
               (signal.direction == SignalDirection.GEGEN and self.source.yaramo_node == self.yaramo_edge.node_a)
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
        # print(self.uuid[-5:], ": ",len(self.signals_in), ", ", len(self.signals_against))
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

    def connected_node(self, node: SchematicNode) -> SchematicNode:
        if node not in (self.source, self.target):
            raise ValueError(f"Given node is not connected to this edge.")
        return self.target if node == self.source else self.source

    def intersects_strictly(self, other_edge: SchematicEdge) -> bool:
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
