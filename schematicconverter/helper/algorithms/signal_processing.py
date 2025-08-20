import numpy as np
import scipy.optimize

from yaramo.signal import Signal

from ..datastructures import SchematicEdge, SchematicGraph


def process_signals(yaramo_graph: SchematicGraph):
    def compute_edge_positions(edge: SchematicEdge, signals: list[Signal]):
        if not signals:
            return []

        if edge.horizontal_only_length > 0:
            epsilon = 1 / edge.horizontal_only_length
            available_positions = np.linspace(epsilon, 1 - epsilon, edge.horizontal_only_length - 1)
        else:
            epsilon = 1 / (edge.horizontal_length + 1)
            available_positions = np.linspace(epsilon, 1 - epsilon, edge.horizontal_length + 2)

        positions_input = np.array([signal.distance_edge / edge.yaramo_edge.length for signal in signals])
        cost_matrix = np.abs(positions_input[:, None] - available_positions[None, :])
        row_ind, col_ind = scipy.optimize.linear_sum_assignment(cost_matrix)
        sorted_indices = np.argsort(row_ind)
        assignment = col_ind[sorted_indices]
        return available_positions[assignment]

    for edge in yaramo_graph.edges:
        signal_positions_against = sorted(compute_edge_positions(edge, edge.signals_against))
        for idx, signal in enumerate(sorted(edge.signals_against, key=lambda signal: signal.distance_edge)):
            edge.set_signal_position(signal, float(signal_positions_against[idx]))

        signal_positions_in = sorted(compute_edge_positions(edge, edge.signals_in))
        for idx, signal in enumerate(sorted(edge.signals_in, key=lambda signal: signal.distance_edge)):
            edge.set_signal_position(signal, float(signal_positions_in[idx]))
