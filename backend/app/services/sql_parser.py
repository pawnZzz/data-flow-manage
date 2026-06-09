import sqlglot
from sqlglot import exp

_LINEAGE_STMTS = (exp.Insert, exp.Create, exp.Merge, exp.Update)


def _target_table(stmt: exp.Expression) -> str | None:
    """写入目标表的完整限定名。stmt.this 可能是 Table，或被 Schema(列定义) 包裹。"""
    node = stmt.this
    if isinstance(node, exp.Table):
        return node.sql()
    tbl = node.find(exp.Table) if node is not None else None
    return tbl.sql() if tbl is not None else None


def _source_tables(stmt: exp.Expression, target: str | None) -> list[str]:
    """FROM/JOIN/CTE 来源表，排除 target 自身与 CTE 中间名。"""
    cte_names = {c.alias for c in stmt.find_all(exp.CTE)}
    out: list[str] = []
    for t in stmt.find_all(exp.Table):
        name = t.sql()
        if name == target or name in cte_names:
            continue
        out.append(name)
    return list(dict.fromkeys(out))


def parse_sql(sql: str, dialect: str = "mysql") -> dict:
    """解析 SQL → {tables, dependencies, unrecognized}。

    语法错抛 sqlglot.errors.ParseError；未知 dialect 抛 ValueError。
    依赖方向：目标依赖源 → {source: 目标, target: 源}。
    """
    parsed = sqlglot.parse(sql, dialect=dialect)
    tables: list[str] = []
    dependencies: list[dict] = []
    unrecognized: list[str] = []
    for stmt in parsed:
        if stmt is None:
            continue
        if isinstance(stmt, _LINEAGE_STMTS):
            target = _target_table(stmt)
            sources = _source_tables(stmt, target)
            if target:
                tables.append(target)
            tables.extend(sources)
            for src in sources:
                if target and src != target:
                    dependencies.append(
                        {"source": target, "target": src, "edge_type": "data_flow"}
                    )
        else:
            unrecognized.append(stmt.sql(dialect=dialect))
    tables = list(dict.fromkeys(tables))
    return {"tables": tables, "dependencies": dependencies, "unrecognized": unrecognized}
