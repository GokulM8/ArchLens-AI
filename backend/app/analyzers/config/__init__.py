"""Configuration file analyzers for ArchLens AI."""

from app.analyzers.config.requirements_parser import parse_dependency_file

__all__ = [
    "parse_dependency_file",
]