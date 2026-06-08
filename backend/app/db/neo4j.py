from neo4j import Driver, GraphDatabase

from app.config import get_settings

_driver: Driver | None = None


def get_driver() -> Driver:
    global _driver
    if _driver is None:
        s = get_settings()
        _driver = GraphDatabase.driver(s.neo4j_uri, auth=(s.neo4j_user, s.neo4j_password))
    return _driver


def ping() -> bool:
    """验证 Neo4j 可连通；连不上抛异常。"""
    get_driver().verify_connectivity()
    return True


def close_driver() -> None:
    global _driver
    if _driver is not None:
        _driver.close()
        _driver = None
