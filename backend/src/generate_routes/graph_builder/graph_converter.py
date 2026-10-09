from dataclasses import dataclass, field

import networkx as nx
from shapely.geometry import LineString

from src.database.geo_point import GeoPoint
from src.generate_routes.data.map import Map


@dataclass
class GraphConverter:
    original_map: Map
    simplified_map: Map = field(init=False, default=None)
    MIN_DEAD_END_LENGTH_METERS: float = 50.0
    FAKE_JUNCTION_DEGREE: int = 2
    MIN_NODE_CHAIN_TO_PRESERVE: int = 2

    def convert_graph_to_algorithm(self, protected_nodes: set[int] | None = None) -> Map:
        protected_nodes = protected_nodes or set()
        working_graph: Map = self.original_map.copy()

        # Step 1: Remove private vehicle driveways and parking aisles
        drop_edge_keys = [
            (source_node, target_node, edge_key)
            for source_node, target_node, edge_key, edge_attrs in working_graph.edges(keys=True, data=True)
            if edge_attrs.get("service") in {"driveway", "parking_aisle"}
        ]
        for source_node, target_node, edge_key in drop_edge_keys:
            working_graph.remove_edge(source_node, target_node, key=edge_key)

        # Step 2: Contract degree-2 corridors into macro-edges
        working_graph = self._contract_degree_two(working_graph, protected_nodes)

        # Step 3: Prune dead-ends AFTER contraction (omija protected_nodes)
        self._prune_dead_ends(working_graph, self.MIN_DEAD_END_LENGTH_METERS, protected_nodes)

        # Step 4: Retain the largest connected component
        self.simplified_map = self._keep_largest_component(working_graph)
        return self.simplified_map

    def _contract_degree_two(self, graph_to_contract: Map, protected_nodes: set[int]) -> Map:
        """Contracts linear chains of degree-2 nodes into single edges tracking node IDs."""
        junction_nodes = self._find_junction_nodes(graph_to_contract, protected_nodes)
        contracted_graph = self._init_simplified_graph(graph_to_contract, junction_nodes)
        visited_edges: set[tuple[int, int, any]] = set()

        for start_junction in junction_nodes:
            for _, first_corridor_step, edge_key, initial_edge_attrs in graph_to_contract.out_edges(
                start_junction, keys=True, data=True
            ):
                edge_id = (start_junction, first_corridor_step, edge_key)
                if edge_id in visited_edges:
                    continue
                visited_edges.add(edge_id)

                end_junction, corridor_length, corridor_node_chain = self._trace_corridor(
                    graph_to_contract,
                    start_junction,
                    first_corridor_step,
                    initial_edge_attrs,
                    junction_nodes,
                    visited_edges,
                )

                if end_junction in junction_nodes and len(corridor_node_chain) >= self.MIN_NODE_CHAIN_TO_PRESERVE:
                    self._add_or_update_macro_edge(
                        contracted_graph,
                        start_junction,
                        end_junction,
                        corridor_length,
                        corridor_node_chain,
                    )

        return contracted_graph

    def _find_junction_nodes(self, graph: Map, protected_nodes: set[int]) -> set[int]:
        undirected_graph = nx.Graph(graph)
        junctions = {node_id for node_id, degree in undirected_graph.degree() if degree != self.FAKE_JUNCTION_DEGREE}
        return junctions | protected_nodes

    @classmethod
    def _prune_dead_ends(cls, graph: Map, max_dead_end_length: float, protected_nodes: set[int] | None = None) -> None:
        """
        Recursively prunes dead-end stubs after contraction.
        Removes tip nodes having only one unique topological neighbor if total edge length < max_dead_end_length.
        Never prunes nodes specified in protected_nodes.
        """
        protected = protected_nodes or set()
        has_changed = True
        while has_changed:
            has_changed = False
            dead_end_candidates = [
                node_id
                for node_id in list(graph.nodes)
                if node_id not in protected
                and len(set(graph.predecessors(node_id)) | set(graph.successors(node_id))) == 1
            ]

            for candidate_node in dead_end_candidates:
                if candidate_node not in graph:
                    continue

                incident_edges = list(graph.in_edges(candidate_node, data=True)) + list(
                    graph.out_edges(candidate_node, data=True)
                )
                if not incident_edges:
                    graph.remove_node(candidate_node)
                    has_changed = True
                    continue

                max_incident_length = max(edge_attrs.get("length", 0.0) for _, _, edge_attrs in incident_edges)
                if max_incident_length < max_dead_end_length:
                    graph.remove_node(candidate_node)
                    has_changed = True

    @staticmethod
    def _init_simplified_graph(source_graph: Map, junction_nodes: set[int]) -> Map:
        new_simplified_graph = nx.MultiDiGraph()
        new_simplified_graph.graph.update(source_graph.graph)
        for node_id in junction_nodes:
            new_simplified_graph.add_node(node_id, **source_graph.nodes[node_id])
        return new_simplified_graph

    @staticmethod
    def _find_next_step(graph: Map, current_node: int, previous_node: int) -> tuple[int, any, dict] | None:
        outgoing_candidates = [
            (next_node, edge_key, edge_attrs)
            for _, next_node, edge_key, edge_attrs in graph.out_edges(current_node, keys=True, data=True)
            if next_node != previous_node
        ]
        return outgoing_candidates[0] if outgoing_candidates else None

    def _trace_corridor(  # noqa: PLR0913
        self,
        graph: Map,
        start_junction: int,
        first_step_node: int,
        initial_edge_attrs: dict,
        junction_nodes: set[int],
        visited_edges: set[tuple[int, int, any]],
    ) -> tuple[int, float, list[int]]:
        node_chain = [start_junction, first_step_node]
        total_corridor_length = initial_edge_attrs.get("length", 0.0)
        previous_node, current_node = start_junction, first_step_node
        visited_nodes_in_path = {start_junction, current_node}

        while current_node not in junction_nodes:
            next_step = self._find_next_step(graph, current_node, previous_node)
            if not next_step:
                break

            next_node, edge_key, edge_attrs = next_step
            visited_edges.add((current_node, next_node, edge_key))
            node_chain.append(next_node)
            total_corridor_length += edge_attrs.get("length", 0.0)

            if next_node in visited_nodes_in_path:
                current_node = next_node
                break

            visited_nodes_in_path.add(next_node)
            previous_node, current_node = current_node, next_node

        return current_node, total_corridor_length, node_chain

    @staticmethod
    def _add_or_update_macro_edge(
        target_graph: Map,
        source_node: int,
        target_node: int,
        total_length: float,
        node_chain: list[int],
    ) -> None:
        macro_edge_attrs = {
            "length": total_length,
            "path_nodes": node_chain,
        }

        if source_node == target_node or not target_graph.has_edge(source_node, target_node):
            target_graph.add_edge(source_node, target_node, **macro_edge_attrs)
            return

        existing_edges = target_graph.get_edge_data(source_node, target_node)
        first_edge_key = next(iter(existing_edges.keys()))
        if total_length < existing_edges[first_edge_key].get("length", float("inf")):
            target_graph.remove_edge(source_node, target_node, key=first_edge_key)
            target_graph.add_edge(source_node, target_node, **macro_edge_attrs)

    @classmethod
    def _keep_largest_component(cls, graph: Map) -> Map:
        """Keeps only the largest weakly connected component."""
        if not graph or len(graph.nodes) == 0:
            return graph
        largest_component_nodes = max(nx.weakly_connected_components(graph), key=len)
        return graph.subgraph(largest_component_nodes).copy()

    def reconstruct_route_from_node_ids(self, simplified_node_path: list[int]) -> list[GeoPoint]:
        """
        Reconstructs high-fidelity map geometry from simplified graph node IDs in O(K) time:
        1. Expands macro-edges into the full sequence of original graph node IDs.
        2. Retrieves the exact LineString geometry directly from original_map edges.
        """
        if len(simplified_node_path) < self.MIN_NODE_CHAIN_TO_PRESERVE:
            return [
                GeoPoint(
                    latitude=self.original_map.nodes[node_id]["y"],
                    longitude=self.original_map.nodes[node_id]["x"],
                )
                for node_id in simplified_node_path
            ]

        graph_to_lookup = self.simplified_map if self.simplified_map is not None else self.original_map

        # Step 1: Expand simplified edges into the complete chain of original nodes
        full_node_chain: list[int] = []
        for segment_start, segment_end in zip(simplified_node_path[:-1], simplified_node_path[1:], strict=False):
            macro_edge_variants = graph_to_lookup.get_edge_data(segment_start, segment_end)
            if not macro_edge_variants:
                continue

            shortest_macro_variant = min(macro_edge_variants.values(), key=lambda edge: edge.get("length", 0.0))
            intermediate_nodes = shortest_macro_variant.get("path_nodes", [segment_start, segment_end])

            if not full_node_chain:
                full_node_chain.extend(intermediate_nodes)
            else:
                full_node_chain.extend(intermediate_nodes[1:])

        # Step 2: Fetch exact road bend geometry from original graph edges
        full_coordinates: list[tuple[float, float]] = []
        original_graph = self.original_map

        for step_start, step_end in zip(full_node_chain[:-1], full_node_chain[1:], strict=False):
            edge_data_variants = original_graph.get_edge_data(step_start, step_end)
            if not edge_data_variants:
                segment_points = [
                    (original_graph.nodes[step_start]["y"], original_graph.nodes[step_start]["x"]),
                    (original_graph.nodes[step_end]["y"], original_graph.nodes[step_end]["x"]),
                ]
            else:
                shortest_original_edge = min(edge_data_variants.values(), key=lambda edge: edge.get("length", 0.0))
                geometry = shortest_original_edge.get("geometry")

                if isinstance(geometry, LineString):
                    segment_points = [(lat, lon) for lon, lat in geometry.coords]
                else:
                    segment_points = [
                        (original_graph.nodes[step_start]["y"], original_graph.nodes[step_start]["x"]),
                        (original_graph.nodes[step_end]["y"], original_graph.nodes[step_end]["x"]),
                    ]

            if not full_coordinates:
                full_coordinates.extend(segment_points)
            else:
                full_coordinates.extend(segment_points[1:])

        return [GeoPoint(latitude=lat, longitude=lon) for lat, lon in full_coordinates]
