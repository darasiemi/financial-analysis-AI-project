# pylint: disable=import-outside-toplevel,unused-import


def test_backend_imports() -> None:
    import deployment.backend.main  # noqa: F401


def test_monitoring_imports() -> None:
    import monitoring.database  # noqa: F401
    import monitoring.judge  # noqa: F401


def test_rag_imports() -> None:
    import rag.pipeline  # noqa: F401


def test_agent_imports() -> None:
    import agent.pipeline  # noqa: F401
