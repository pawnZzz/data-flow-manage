"""部署用：对配置的 Neo4j 施加约束与索引。运行：python -m scripts.init_neo4j_constraints"""
from app.db.neo4j import close_driver, get_driver
from app.db.neo4j_constraints import init_constraints


def main() -> None:
    driver = get_driver()
    init_constraints(driver)
    print("Neo4j 约束与索引已就绪")
    close_driver()


if __name__ == "__main__":
    main()
