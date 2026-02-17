#!/usr/bin/env python3
"""
GLB Mesh Analyzer for Weight Transfer Diagnostics

Analyzes GLB files for common issues that cause weight transfer crumpling:
1. Mesh topology (degenerate triangles, non-manifold geometry)
2. Scale and bounds
3. Vertex density distribution
4. Compatibility with body mesh

Usage:
    python scripts/analyze_glb.py comfyui_generated_mesh/1764637457/clothing_mesh.glb
    python scripts/analyze_glb.py --body models/lowpoly_rigged_full_v1.glb --clothing comfyui_generated_mesh/*/clothing_mesh.glb
"""

import json
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import argparse

try:
    import numpy as np
    import trimesh
except ImportError as e:
    print(f"Missing dependency: {e}")
    print("Install with: pip install numpy trimesh")
    sys.exit(1)


class GLBAnalyzer:
    """Analyzes GLB mesh files for weight transfer compatibility."""

    def __init__(self, filepath: str):
        self.filepath = Path(filepath)
        self.mesh = None
        self.stats = {}
        self.issues = []
        self.warnings = []

    def load(self) -> bool:
        """Load the GLB file using trimesh."""
        try:
            print(f"Loading {self.filepath}...")
            self.mesh = trimesh.load(self.filepath, force='mesh')
            print(f"  ✓ Loaded: {len(self.mesh.vertices)} vertices, {len(self.mesh.faces)} faces")
            return True
        except Exception as e:
            print(f"  ✗ Failed to load: {e}")
            return False

    def analyze_topology(self) -> Dict:
        """Analyze mesh topology for issues."""
        if self.mesh is None:
            return {}

        stats = {}

        # Count degenerate faces (zero area)
        face_areas = self.mesh.area_faces
        degenerate_faces = np.sum(face_areas < 1e-10)
        stats['degenerate_faces'] = int(degenerate_faces)
        stats['total_faces'] = len(self.mesh.faces)

        if degenerate_faces > 0:
            self.warnings.append(f"Found {degenerate_faces} degenerate (zero-area) faces")

        # Check for duplicate vertices
        unique_vertices = np.unique(self.mesh.vertices, axis=0)
        duplicate_vertices = len(self.mesh.vertices) - len(unique_vertices)
        stats['duplicate_vertices'] = int(duplicate_vertices)

        if duplicate_vertices > len(self.mesh.vertices) * 0.1:
            self.warnings.append(f"High duplicate vertex count: {duplicate_vertices}")

        # Vertex-face connectivity
        vertex_face_count = np.bincount(self.mesh.faces.flatten(), minlength=len(self.mesh.vertices))
        stats['isolated_vertices'] = int(np.sum(vertex_face_count == 0))
        stats['avg_faces_per_vertex'] = float(np.mean(vertex_face_count))

        if stats['isolated_vertices'] > 0:
            self.warnings.append(f"Found {stats['isolated_vertices']} isolated vertices")

        # Face aspect ratio (elongated triangles)
        face_edges = self.mesh.edges_face
        edge_lengths = np.linalg.norm(
            self.mesh.vertices[face_edges[:, 1]] - self.mesh.vertices[face_edges[:, 0]],
            axis=1
        ).reshape(-1, 3)

        # Aspect ratio = longest edge / shortest edge
        aspect_ratios = np.max(edge_lengths, axis=1) / (np.min(edge_lengths, axis=1) + 1e-10)
        stats['avg_aspect_ratio'] = float(np.mean(aspect_ratios))
        stats['max_aspect_ratio'] = float(np.max(aspect_ratios))

        if stats['max_aspect_ratio'] > 100:
            self.warnings.append(f"Very elongated faces detected (max aspect ratio: {stats['max_aspect_ratio']:.1f})")

        self.stats['topology'] = stats
        return stats

    def analyze_bounds(self) -> Dict:
        """Analyze mesh bounds and scale."""
        if self.mesh is None:
            return {}

        bounds = self.mesh.bounds
        extents = bounds[1] - bounds[0]
        center = (bounds[1] + bounds[0]) / 2

        stats = {
            'bounds_min': bounds[0].tolist(),
            'bounds_max': bounds[1].tolist(),
            'center': center.tolist(),
            'extents': extents.tolist(),
            'total_bounding_box_volume': float(np.prod(extents)),
            'surface_area': float(self.mesh.area),
            'volume': float(self.mesh.volume) if self.mesh.is_watertight else 0,
        }

        # Check for extreme scales
        max_extent = np.max(extents)
        min_extent = np.min(extents)

        if max_extent > 10:
            self.warnings.append(f"Very large mesh (max extent: {max_extent:.2f})")
        if max_extent < 0.01:
            self.warnings.append(f"Very small mesh (max extent: {max_extent:.4f})")
        if max_extent / (min_extent + 1e-10) > 100:
            self.warnings.append(f"Very flat/elongated mesh (aspect ratio: {max_extent/min_extent:.1f})")

        self.stats['bounds'] = stats
        return stats

    def analyze_vertex_distribution(self) -> Dict:
        """Analyze vertex density distribution."""
        if self.mesh is None:
            return {}

        # Compute vertex density using nearest neighbors
        try:
            from scipy.spatial import cKDTree

            tree = cKDTree(self.mesh.vertices)
            distances, _ = tree.query(self.mesh.vertices, k=2)  # 2 includes self
            nearest_neighbor_distances = distances[:, 1]  # Exclude self (distance 0)

            stats = {
                'min_vertex_spacing': float(np.min(nearest_neighbor_distances)),
                'max_vertex_spacing': float(np.max(nearest_neighbor_distances)),
                'avg_vertex_spacing': float(np.mean(nearest_neighbor_distances)),
                'median_vertex_spacing': float(np.median(nearest_neighbor_distances)),
            }

            # Check for uneven distribution
            spacing_ratio = stats['max_vertex_spacing'] / (stats['min_vertex_spacing'] + 1e-10)
            stats['spacing_ratio'] = float(spacing_ratio)

            if spacing_ratio > 1000:
                self.warnings.append(f"Very uneven vertex distribution (ratio: {spacing_ratio:.1f})")

            self.stats['vertex_distribution'] = stats
            return stats
        except ImportError:
            self.stats['vertex_distribution'] = {'error': 'scipy not available'}
            return self.stats['vertex_distribution']

    def check_compatibility(self, body_mesh_path: str) -> Dict:
        """Check compatibility with body mesh for weight transfer."""
        try:
            body = trimesh.load(body_mesh_path, force='mesh')
        except Exception as e:
            print(f"  Could not load body mesh: {e}")
            return {}

        if self.mesh is None:
            return {}

        stats = {}

        # Compare bounds
        clothing_bounds = self.mesh.bounds
        body_bounds = body.bounds

        clothing_center = (clothing_bounds[1] + clothing_bounds[0]) / 2
        body_center = (body_bounds[1] + body_bounds[0]) / 2
        center_offset = np.linalg.norm(clothing_center - body_center)

        clothing_size = clothing_bounds[1] - clothing_bounds[0]
        body_size = body_bounds[1] - body_bounds[0]

        size_ratios = clothing_size / (body_size + 1e-10)

        stats['center_offset'] = float(center_offset)
        stats['size_ratios'] = size_ratios.tolist()
        stats['max_size_ratio'] = float(np.max(size_ratios))

        # Warnings
        if center_offset > 1.0:
            self.warnings.append(f"Large center offset from body: {center_offset:.3f} units")
        if np.max(size_ratios) > 2.0 or np.min(size_ratios) < 0.5:
            self.warnings.append(f"Significant size mismatch with body (ratio: {np.max(size_ratios):.2f})")

        # Estimate vertex count ratio
        vertex_ratio = len(self.mesh.vertices) / len(body.vertices)
        stats['vertex_count_ratio'] = float(vertex_ratio)

        if vertex_ratio > 10:
            self.warnings.append(f"Clothing has {vertex_ratio:.1f}x more vertices than body (may slow transfer)")

        self.stats['compatibility'] = stats
        return stats

    def export_report(self, output_path: Optional[str] = None) -> str:
        """Export analysis report to JSON."""
        report = {
            'file': str(self.filepath),
            'stats': self.stats,
            'warnings': self.warnings,
            'issues': self.issues,
            'recommendations': self._generate_recommendations()
        }

        if output_path:
            with open(output_path, 'w') as f:
                json.dump(report, f, indent=2)
            print(f"\nReport saved to: {output_path}")

        return json.dumps(report, indent=2)

    def _generate_recommendations(self) -> List[str]:
        """Generate recommendations based on analysis."""
        recommendations = []

        if not self.stats:
            return recommendations

        # Topology recommendations
        if self.stats.get('topology', {}).get('degenerate_faces', 0) > 0:
            recommendations.append("Clean degenerate faces in Blender: Edit Mode > Mesh > Clean Up > Degenerate Dissolve")

        if self.stats.get('topology', {}).get('duplicate_vertices', 0) > 0:
            recommendations.append("Merge duplicate vertices: Edit Mode > Mesh > Clean Up > Merge By Distance")

        # Scale recommendations
        if self.stats.get('compatibility', {}).get('max_size_ratio', 1) > 2:
            recommendations.append("Normalize mesh scale before weight transfer")

        if self.stats.get('compatibility', {}).get('center_offset', 0) > 1.0:
            recommendations.append("Center clothing mesh on body before weight transfer")

        # Vertex count
        if self.stats.get('compatibility', {}).get('vertex_count_ratio', 1) > 5:
            recommendations.append("Consider decimating clothing mesh for faster weight transfer")

        return recommendations

    def print_summary(self):
        """Print a summary of the analysis."""
        print("\n" + "="*60)
        print(f"Analysis Summary: {self.filepath.name}")
        print("="*60)

        if self.stats.get('bounds'):
            b = self.stats['bounds']
            print(f"\n📐 Bounds:")
            print(f"  Center: ({b['center'][0]:.3f}, {b['center'][1]:.3f}, {b['center'][2]:.3f})")
            print(f"  Size: {b['extents'][0]:.3f} x {b['extents'][1]:.3f} x {b['extents'][2]:.3f}")

        if self.stats.get('topology'):
            t = self.stats['topology']
            print(f"\n🔧 Topology:")
            print(f"  Vertices: {len(self.mesh.vertices)}")
            print(f"  Faces: {t['total_faces']}")
            print(f"  Degenerate faces: {t['degenerate_faces']}")
            print(f"  Isolated vertices: {t['isolated_vertices']}")
            print(f"  Avg faces/vertex: {t['avg_faces_per_vertex']:.2f}")

        if self.stats.get('compatibility'):
            c = self.stats['compatibility']
            print(f"\n⚖️  Body Compatibility:")
            print(f"  Center offset: {c['center_offset']:.3f}")
            print(f"  Size ratio: {c['max_size_ratio']:.2f}")
            print(f"  Vertex ratio: {c['vertex_count_ratio']:.2f}")

        if self.warnings:
            print(f"\n⚠️  Warnings ({len(self.warnings)}):")
            for w in self.warnings:
                print(f"  - {w}")

        recommendations = self._generate_recommendations()
        if recommendations:
            print(f"\n💡 Recommendations:")
            for r in recommendations:
                print(f"  - {r}")

        print("="*60)


def main():
    parser = argparse.ArgumentParser(description='Analyze GLB mesh for weight transfer compatibility')
    parser.add_argument('mesh', help='Path to clothing mesh GLB file')
    parser.add_argument('--body', help='Path to body mesh GLB for compatibility check')
    parser.add_argument('--output', '-o', help='Output JSON report path')
    parser.add_argument('--quiet', '-q', action='store_true', help='Minimal output')

    args = parser.parse_args()

    analyzer = GLBAnalyzer(args.mesh)

    if not analyzer.load():
        sys.exit(1)

    analyzer.analyze_topology()
    analyzer.analyze_bounds()
    analyzer.analyze_vertex_distribution()

    if args.body:
        analyzer.check_compatibility(args.body)

    if not args.quiet:
        analyzer.print_summary()

    report = analyzer.export_report(args.output)

    if args.quiet:
        print(report)

    # Return non-zero if warnings exist
    sys.exit(len(analyzer.warnings))


if __name__ == '__main__':
    main()
