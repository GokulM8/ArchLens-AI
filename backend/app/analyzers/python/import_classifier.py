"""Import classifier — determines whether imports are internal, external, or stdlib.

Classifies each import in a module as one of:
- INTERNAL: refers to another module within the analyzed repository
- EXTERNAL: a third-party package installed via pip
- STANDARD_LIBRARY: part of Python's standard library

Also provides technology-domain categorization for known external packages.
"""

from __future__ import annotations

import sys
from typing import Optional


# Python standard library module names (3.9+)
# This is a conservative subset; we check sys.stdlib_module_names at runtime if available
_STDLIB_FALLBACK: frozenset[str] = frozenset({
    "abc", "aifc", "argparse", "array", "ast", "asynchat", "asyncio",
    "asyncore", "atexit", "audioop", "base64", "bdb", "binascii",
    "binhex", "bisect", "builtins", "bz2", "calendar", "cgi", "cgitb",
    "chunk", "cmath", "cmd", "code", "codecs", "codeop", "collections",
    "colorsys", "compileall", "concurrent", "configparser", "contextlib",
    "contextvars", "copy", "copyreg", "cProfile", "crypt", "csv",
    "ctypes", "curses", "dataclasses", "datetime", "dbm", "decimal",
    "difflib", "dis", "distutils", "doctest", "email", "encodings",
    "enum", "errno", "faulthandler", "fcntl", "filecmp", "fileinput",
    "fnmatch", "fractions", "ftplib", "functools", "gc", "getopt",
    "getpass", "gettext", "glob", "grp", "gzip", "hashlib", "heapq",
    "hmac", "html", "http", "idlelib", "imaplib", "imghdr", "imp",
    "importlib", "inspect", "io", "ipaddress", "itertools", "json",
    "keyword", "lib2to3", "linecache", "locale", "logging", "lzma",
    "mailbox", "mailcap", "marshal", "math", "mimetypes", "mmap",
    "modulefinder", "multiprocessing", "netrc", "nis", "nntplib",
    "numbers", "operator", "optparse", "os", "ossaudiodev",
    "pathlib", "pdb", "pickle", "pickletools", "pipes", "pkgutil",
    "platform", "plistlib", "poplib", "posix", "posixpath", "pprint",
    "profile", "pstats", "pty", "pwd", "py_compile", "pyclbr",
    "pydoc", "queue", "quopri", "random", "re", "readline", "reprlib",
    "resource", "rlcompleter", "runpy", "sched", "secrets", "select",
    "selectors", "shelve", "shlex", "shutil", "signal", "site",
    "smtpd", "smtplib", "sndhdr", "socket", "socketserver", "sqlite3",
    "ssl", "stat", "statistics", "string", "stringprep", "struct",
    "subprocess", "sunau", "symtable", "sys", "sysconfig", "syslog",
    "tabnanny", "tarfile", "telnetlib", "tempfile", "termios", "test",
    "textwrap", "threading", "time", "timeit", "tkinter", "token",
    "tokenize", "tomllib", "trace", "traceback", "tracemalloc", "tty",
    "turtle", "turtledemo", "types", "typing", "unicodedata",
    "unittest", "urllib", "uu", "uuid", "venv", "warnings", "wave",
    "weakref", "webbrowser", "winreg", "winsound", "wsgiref",
    "xdrlib", "xml", "xmlrpc", "zipapp", "zipfile", "zipimport",
    "zlib", "_thread", "__future__", "typing_extensions",
})


def _get_stdlib_modules() -> frozenset[str]:
    """Get Python standard library module names."""
    if hasattr(sys, "stdlib_module_names"):
        return frozenset(sys.stdlib_module_names)
    return _STDLIB_FALLBACK


STDLIB_MODULES = _get_stdlib_modules()


# Known external package categories
PACKAGE_CATEGORIES: dict[str, str] = {
    # Web frameworks
    "fastapi": "Web/API",
    "flask": "Web/API",
    "django": "Web/API",
    "starlette": "Web/API",
    "tornado": "Web/API",
    "aiohttp": "Web/API",
    "sanic": "Web/API",
    "bottle": "Web/API",
    "falcon": "Web/API",
    "litestar": "Web/API",
    "uvicorn": "ASGI Server",
    "gunicorn": "WSGI Server",
    "hypercorn": "ASGI Server",

    # Database / ORM
    "sqlalchemy": "Database/ORM",
    "alembic": "Database/Migration",
    "peewee": "Database/ORM",
    "tortoise": "Database/ORM",
    "mongoengine": "Database/ODM",
    "pymongo": "Database/Driver",
    "motor": "Database/Driver",
    "psycopg2": "Database/Driver",
    "asyncpg": "Database/Driver",
    "mysql": "Database/Driver",
    "sqlite3": "Database/Driver",
    "databases": "Database/Driver",
    "prisma": "Database/ORM",

    # Data processing
    "pandas": "Data Processing",
    "polars": "Data Processing",
    "dask": "Data Processing",
    "vaex": "Data Processing",
    "arrow": "Data Processing",

    # Numerical / Scientific
    "numpy": "Numerical Computing",
    "scipy": "Scientific Computing",
    "sympy": "Symbolic Math",

    # Machine learning
    "sklearn": "Machine Learning",
    "scikit_learn": "Machine Learning",
    "torch": "Machine Learning/Deep Learning",
    "pytorch": "Machine Learning/Deep Learning",
    "tensorflow": "Machine Learning/Deep Learning",
    "keras": "Machine Learning/Deep Learning",
    "xgboost": "Machine Learning",
    "lightgbm": "Machine Learning",
    "catboost": "Machine Learning",
    "transformers": "Machine Learning/NLP",
    "spacy": "Machine Learning/NLP",
    "nltk": "Machine Learning/NLP",
    "gensim": "Machine Learning/NLP",
    "langchain": "LLM/AI",
    "openai": "LLM/AI",
    "anthropic": "LLM/AI",

    # Caching
    "redis": "Cache/Store",
    "aioredis": "Cache/Store",
    "memcache": "Cache/Store",

    # Task queue / messaging
    "celery": "Task Queue",
    "rq": "Task Queue",
    "dramatiq": "Task Queue",
    "huey": "Task Queue",
    "kombu": "Messaging",
    "pika": "Messaging",
    "kafka": "Messaging",

    # HTTP / networking
    "requests": "HTTP Client",
    "httpx": "HTTP Client",
    "urllib3": "HTTP Client",
    "websockets": "WebSocket",

    # Authentication / security
    "jwt": "Auth/Security",
    "pyjwt": "Auth/Security",
    "passlib": "Auth/Security",
    "bcrypt": "Auth/Security",
    "cryptography": "Auth/Security",
    "authlib": "Auth/Security",
    "python_jose": "Auth/Security",

    # Testing
    "pytest": "Testing",
    "unittest": "Testing",
    "hypothesis": "Testing",
    "mock": "Testing",
    "faker": "Testing",
    "factory_boy": "Testing",
    "coverage": "Testing",

    # Validation / serialization
    "pydantic": "Validation",
    "marshmallow": "Validation",
    "cerberus": "Validation",
    "attrs": "Data Class",

    # Logging / monitoring
    "loguru": "Logging",
    "structlog": "Logging",
    "sentry_sdk": "Monitoring",
    "prometheus_client": "Monitoring",
    "opentelemetry": "Monitoring/Tracing",

    # CLI
    "click": "CLI",
    "typer": "CLI",
    "rich": "CLI/Display",
    "tqdm": "CLI/Display",

    # Config
    "dotenv": "Config",
    "python_dotenv": "Config",
    "pyyaml": "Config",
    "toml": "Config",
    "dynaconf": "Config",

    # File / image processing
    "pillow": "Image Processing",
    "pil": "Image Processing",
    "opencv": "Computer Vision",
    "cv2": "Computer Vision",
    "matplotlib": "Visualization",
    "seaborn": "Visualization",
    "plotly": "Visualization",
    "bokeh": "Visualization",

    # Cloud
    "boto3": "AWS",
    "botocore": "AWS",
    "google_cloud": "GCP",
    "azure": "Azure",

    # Misc
    "jinja2": "Templating",
    "networkx": "Graph/Network",
}


class ImportClassifier:
    """Classifies imports as internal, external, or standard library.

    Uses the set of Python modules within the analyzed repository to
    determine internal imports. Everything else is classified using the
    stdlib module list and heuristics.
    """

    def __init__(self, internal_module_names: set[str]):
        """Initialize the classifier.

        Args:
            internal_module_names: Set of dotted module paths that exist
                within the analyzed repository (e.g., {"app.models", "app.services"}).
        """
        self._internal_modules = internal_module_names
        self._internal_top_level = {m.split(".")[0] for m in internal_module_names}

    def classify(self, module: str) -> str:
        """Classify an import as internal, external, or standard_library.

        Args:
            module: The imported module path (e.g., "os.path", "app.models.user").

        Returns:
            One of "internal", "external", or "standard_library".
        """
        if not module:
            return "external"

        # Relative imports are always internal
        if module.startswith("."):
            return "internal"

        top_level = module.split(".")[0]

        # Check against known internal modules
        if module in self._internal_modules:
            return "internal"
        if top_level in self._internal_top_level:
            return "internal"

        # Check standard library
        if top_level in STDLIB_MODULES:
            return "standard_library"

        return "external"

    @staticmethod
    def categorize_package(package_name: str) -> Optional[str]:
        """Get the technology category for a known external package.

        Args:
            package_name: The package name (e.g., "fastapi", "numpy").

        Returns:
            Category string or None if not recognized.
        """
        normalized = package_name.lower().replace("-", "_")
        return PACKAGE_CATEGORIES.get(normalized)
