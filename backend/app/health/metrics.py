"""Phase 4 Health & Risk Intelligence - Core Metrics and Analysis."""

from typing import Dict
import networkx as nx

from app.models.schemas import AnalysisResult
from app.architecture.schemas import ArchitectureResult
from app.health.schemas import (
    DependencyMetrics,
    CouplingMetrics,
    CentralityMetrics,
    ComplexityMetrics,
    APIMetrics,
    DependencyConcentrationMetrics,
)


class HealthMetricsCalculator:
    """Calculates all health metrics for the architecture."""

    def __init__(
        self,
        analysis: AnalysisResult,
        graph: nx.MultiDiGraph,
        architecture: ArchitectureResult,
    ):
        self.analysis = analysis
        self.graph = graph
        self.architecture = architecture
        self.components_map = {c.id: c for c in architecture.components}

    def calculate_dependency_metrics(self) -> DependencyMetrics:
        """Calculate dependency metrics including cycles."""
        from app.health.cycles import CycleDetector

        detector = CycleDetector(self.graph)
        cycle_count, cycles = detector.detect_cycles()

        # Calculate dependency depth
        max_depth = self._calculate_max_depth()
        avg_depth = self._calculate_avg_depth()

        return DependencyMetrics(
            total_dependencies=self.graph.number_of_edges(),
            circular_dependency_count=cycle_count,
            circular_dependencies=cycles,
            max_dependency_depth=max_depth,
            average_dependency_depth=round(avg_depth, 2),
        )

    def calculate_coupling_metrics(self) -> CouplingMetrics:
        """Calculate coupling metrics."""
        from app.health.coupling import CouplingAnalyzer

        analyzer = CouplingAnalyzer(self.graph, self.architecture.components)
        return analyzer.analyze_coupling()

    def calculate_centrality_metrics(self) -> CentralityMetrics:
        """Calculate centralization and bottleneck metrics."""
        highly_central = []

        if self.graph.number_of_nodes() > 0:
            # Simple in-degree centrality
            in_degrees = {}
            for node in self.graph.nodes():
                in_degrees[node] = self.graph.in_degree(node)

            if in_degrees:
                avg_in_degree = sum(in_degrees.values()) / len(in_degrees)
                high_centrality_threshold = avg_in_degree * 1.5

                for node, degree in in_degrees.items():
                    if node in self.components_map and degree > high_centrality_threshold:
                        comp = self.components_map[node]
                        highly_central.append({
                            "component": node,
                            "component_name": comp.name,
                            "in_degree": degree,
                            "reason": f"High in-degree ({degree}) indicates potential bottleneck",
                        })

        return CentralityMetrics(highly_central_components=highly_central)

    def calculate_complexity_metrics(self) -> ComplexityMetrics:
        """Calculate size and complexity metrics."""
        modules_by_size = []

        for module in self.analysis.modules:
            # module.classes and module.functions are lists of IDs (strings)
            # Look up the actual objects from analysis
            loc = 0
            for class_id in module.classes:
                cls_obj = next((c for c in self.analysis.classes if c.id == class_id), None)
                if cls_obj:
                    loc += len(cls_obj.methods) * 3

            for func_id in module.functions:
                func_obj = next((f for f in self.analysis.functions if f.id == func_id), None)
                if func_obj:
                    loc += getattr(func_obj, "lines_of_code", 1)

            modules_by_size.append({
                "module": module.id,
                "module_name": module.path,
                "lines_of_code": loc,
                "class_count": len(module.classes),
                "function_count": len(module.functions),
            })

        # Sort by size
        modules_by_size.sort(key=lambda x: x["lines_of_code"], reverse=True)

        # Largest classes
        largest_classes = []
        for cls in self.analysis.classes[:10]:
            largest_classes.append({
                "class": cls.id,
                "class_name": cls.name,
                "method_count": len(cls.methods),
            })

        # Largest functions
        largest_functions = []
        for func in sorted(self.analysis.functions, key=lambda f: getattr(f, "lines_of_code", 1), reverse=True)[:10]:
            largest_functions.append({
                "function": func.id,
                "function_name": func.name,
                "lines_of_code": getattr(func, "lines_of_code", 1),
            })

        return ComplexityMetrics(
            largest_modules=modules_by_size[:10],
            largest_classes=largest_classes,
            largest_functions=largest_functions,
        )

    def calculate_api_metrics(self) -> APIMetrics:
        """Calculate API surface metrics."""
        routes_by_module: Dict[str, int] = {}
        http_methods: Dict[str, int] = {}

        for route in self.analysis.routes:
            method = getattr(route, "method", "GET")
            http_methods[method] = http_methods.get(method, 0) + 1

            # Group by module
            module_id = getattr(route, "file_path", getattr(route, "module_id", "unknown"))
            routes_by_module[module_id] = routes_by_module.get(module_id, 0) + 1

        return APIMetrics(
            total_routes=len(self.analysis.routes),
            routes_per_module=routes_by_module,
            http_method_distribution=http_methods,
        )

    def calculate_dependency_concentration(self) -> DependencyConcentrationMetrics:
        """Calculate external dependency concentration."""
        modules_with_ext_deps = set()
        external_deps = set()

        for module in self.analysis.modules:
            for imp in module.imports:
                if self._is_external_import(imp.module):
                    modules_with_ext_deps.add(module.id)
                    external_deps.add(imp.module)

        total_modules = len(self.analysis.modules) if self.analysis.modules else 1
        concentration = len(modules_with_ext_deps) / total_modules if total_modules > 0 else 0

        return DependencyConcentrationMetrics(
            total_external_dependencies=len(external_deps),
            modules_with_external_deps=len(modules_with_ext_deps),
            external_dependency_concentration=round(concentration, 2),
        )

    def _calculate_max_depth(self) -> int:
        """Calculate maximum dependency depth."""
        if self.graph.number_of_nodes() == 0:
            return 0

        max_depth = 0
        try:
            for node in list(self.graph.nodes())[:20]:  # Sample to avoid timeout
                visited = set()
                queue = [(node, 0)]
                while queue:
                    current, depth = queue.pop(0)
                    if current not in visited:
                        visited.add(current)
                        max_depth = max(max_depth, depth)
                        for succ in list(self.graph.successors(current))[:5]:
                            if succ not in visited:
                                queue.append((succ, depth + 1))
        except Exception:
            pass

        return max_depth

    def _calculate_avg_depth(self) -> float:
        """Calculate average dependency depth."""
        if self.graph.number_of_nodes() == 0:
            return 0.0

        total_depth = 0
        count = 0

        try:
            for node in list(self.graph.nodes())[:20]:
                visited = set()
                queue = [(node, 0)]
                while queue:
                    current, depth = queue.pop(0)
                    if current not in visited:
                        visited.add(current)
                        total_depth += depth
                        count += 1
                        for succ in list(self.graph.successors(current))[:5]:
                            if succ not in visited:
                                queue.append((succ, depth + 1))
        except Exception:
            pass

        return total_depth / count if count > 0 else 0.0

    @staticmethod
    def _is_external_import(module_name: str) -> bool:
        """Check if a module is an external import."""
        return not module_name.startswith("module:")

