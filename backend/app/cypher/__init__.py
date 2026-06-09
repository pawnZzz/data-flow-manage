from app.config import get_settings


def inline_depth(cypher: str) -> str:
    """把 Cypher 里的 __DEPTH__ 占位符替换为 config 的 max_traversal_depth。

    变长路径上界 `*1..N` 的 N 不能用 Cypher 参数，只能拼串；N 来自可信 config，
    非用户输入，无注入风险。
    """
    return cypher.replace("__DEPTH__", str(get_settings().max_traversal_depth))
