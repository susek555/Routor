import numpy as np

from src.generate_routes.data.map import Map

DEFAULT_SEED_BOOST_FACTOR = 1.5


class EdgePheromoneRegistry:
    """Manages dense 1D pheromone arrays mapped to undirected graph edges."""

    def __init__(self, stage_graphs: list[Map], initial_pheromone: float = 1.0):
        self.initial_pheromone = initial_pheromone
        self.edge_to_id: dict[frozenset[int], int] = {}
        self._build_index(stage_graphs)

        num_edges = len(self.edge_to_id)
        self.pheromones = np.full(num_edges, initial_pheromone, dtype=np.float64)

    def _build_index(self, stage_graphs: list[Map]) -> None:
        """Indexes undirected edges into contiguous zero-based integer identifiers."""
        curr_id = 0
        for graph in stage_graphs:
            for u, v in graph.edges():
                if u == v:
                    continue
                edge_key = frozenset((u, v))
                if edge_key not in self.edge_to_id:
                    self.edge_to_id[edge_key] = curr_id
                    curr_id += 1

    def get_edge_id(self, u: int, v: int) -> int | None:
        """Returns the contiguous 1D array index for undirected edge {u, v}."""
        if u == v:
            return None
        return self.edge_to_id.get(frozenset((u, v)))

    def get_pheromone(self, u: int, v: int) -> float:
        """Retrieves pheromone concentration for edge {u, v}."""
        edge_id = self.get_edge_id(u, v)
        if edge_id is None:
            return self.initial_pheromone
        return float(self.pheromones[edge_id])

    def seed_path_pheromones(
        self,
        path: list[int],
        boost_factor: float = DEFAULT_SEED_BOOST_FACTOR,
    ) -> None:
        """Seeds initial pheromones along a baseline shortest path to guide ant convergence."""
        target_pheromone = self.initial_pheromone * boost_factor

        for i in range(len(path) - 1):
            u, v = path[i], path[i + 1]
            edge_id = self.get_edge_id(u, v)
            if edge_id is not None:
                self.pheromones[edge_id] = max(self.pheromones[edge_id], target_pheromone)

    def create_empty_deposit_buffer(self) -> np.ndarray:
        """Allocates a zeroed accumulation array for iteration deposits."""
        return np.zeros(len(self.pheromones), dtype=np.float64)

    def evaporate(self, evaporation_rate: float) -> None:
        """Vectorized evaporation: tau <- (1 - rho) * tau."""
        self.pheromones *= 1.0 - evaporation_rate

    def apply_deposits(self, iteration_deposits: np.ndarray) -> None:
        """Applies accumulated iteration deposits to the global pheromone vector."""
        self.pheromones += iteration_deposits
