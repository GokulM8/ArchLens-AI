"""Tests for the import classifier."""

from __future__ import annotations

from app.analyzers.python.import_classifier import ImportClassifier


class TestImportClassifier:
    """Tests for classifying imports as internal/external/stdlib."""

    def setup_method(self):
        self.classifier = ImportClassifier(
            internal_module_names={
                "app",
                "app.models",
                "app.models.user",
                "app.services",
                "app.services.auth",
                "app.routes",
            }
        )

    def test_python_package_import(self):
        assert self.classifier.classify("app.routes") == "internal"

    def test_module_import(self):
        assert self.classifier.classify("app.models.user") == "internal"

    def test_top_level_internal(self):
        assert self.classifier.classify("app.services.auth") == "internal"

    def test_external_import(self):
        assert self.classifier.classify("fastapi") == "external"

    def test_external_submodule(self):
        assert self.classifier.classify("sklearn.ensemble") == "external"

    def test_standard_library(self):
        assert self.classifier.classify("os") == "standard_library"

    def test_standard_library_submodule(self):
        assert self.classifier.classify("os.path") == "standard_library"

    def test_typing_standard_library(self):
        assert self.classifier.classify("typing") == "standard_library"

    def test_relative_import_internal(self):
        assert self.classifier.classify("..models") == "internal"

    def test_relative_import_internal_dot(self):
        assert self.classifier.classify(".user") == "internal"

    def test_future_import(self):
        assert self.classifier.classify("__future__") == "standard_library"

    def test_empty_module_is_external(self):
        assert self.classifier.classify("") == "external"

    def test_unknown_is_external(self):
        assert self.classifier.classify("some_unknown_library") == "external"


class TestCategorizePackage:
    """Tests for technology category detection."""

    def test_web_framework(self):
        assert ImportClassifier.categorize_package("fastapi") == "Web/API"
        assert ImportClassifier.categorize_package("flask") == "Web/API"

    def test_database(self):
        assert ImportClassifier.categorize_package("sqlalchemy") == "Database/ORM"

    def test_machine_learning(self):
        assert ImportClassifier.categorize_package("sklearn") == "Machine Learning"
        assert ImportClassifier.categorize_package("torch") == "Machine Learning/Deep Learning"

    def test_data_processing(self):
        assert ImportClassifier.categorize_package("pandas") == "Data Processing"
        assert ImportClassifier.categorize_package("numpy") == "Numerical Computing"

    def test_cache(self):
        assert ImportClassifier.categorize_package("redis") == "Cache/Store"

    def test_task_queue(self):
        assert ImportClassifier.categorize_package("celery") == "Task Queue"

    def test_underscore_normalization(self):
        assert ImportClassifier.categorize_package("scikit_learn") == "Machine Learning"
        assert ImportClassifier.categorize_package("python-dotenv") == "Config"

    def test_generic_package_not_found(self):
        assert ImportClassifier.categorize_package("completely-unknown-pkg") is None