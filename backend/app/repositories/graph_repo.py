from typing import Any

from neo4j import Driver


class GraphRepo:
    """Neo4j 访问封装：统一开 session、参数化执行、record→dict。"""

    def __init__(self, driver: Driver):
        self._driver = driver

    def run_write(self, cypher: str, **params: Any) -> list[dict]:
        with self._driver.session() as session:
            result = session.execute_write(lambda tx: list(tx.run(cypher, **params)))
        return [r.data() for r in result]

    def run_read(self, cypher: str, **params: Any) -> list[dict]:
        with self._driver.session() as session:
            result = session.execute_read(lambda tx: list(tx.run(cypher, **params)))
        return [r.data() for r in result]
