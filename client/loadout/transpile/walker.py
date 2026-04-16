"""ESTree → Python source walker.

Handles the subset of ES2022 used by the loadout calculation files:
- FunctionDeclaration, ArrowFunctionExpression (expression + block body)
- const/let/var, object/array destructuring with defaults
- if/else, for..of, return, expression statements
- object/array literals with spread and computed properties
- template literals, regex literals
- optional chaining (ChainExpression) + nullish coalescing (??)
- logical &&/|| with JS-truthy semantics via `js_logical_and/or`
- CallExpression / NewExpression with dispatch to runtime shim
- MemberExpression — always emitted through `js_get`/`js_optional`

Unknown node types raise `UnsupportedNode` so the pipeline can decide
whether to escalate to the LLM fallback.
"""

from __future__ import annotations

import keyword
from dataclasses import dataclass, field
from typing import Any

from .codegen import CodeBuilder


class UnsupportedNode(RuntimeError):
    def __init__(self, node_type: str, function_name: str | None, detail: str = ""):
        self.node_type = node_type
        self.function_name = function_name
        self.detail = detail
        super().__init__(
            f"unsupported {node_type!r} inside {function_name or '<module>'}"
            + (f": {detail}" if detail else "")
        )


# Identifiers that are legal in JS but reserved in Python
_PY_RESERVED = set(keyword.kwlist) | {"None", "True", "False", "match", "case"}

# JS global namespace methods/properties we map to runtime helpers
_GLOBAL_MAP = {
    ("Math", "max"): "js_math_max",
    ("Math", "min"): "js_math_min",
    ("Math", "floor"): "js_math_floor",
    ("Math", "ceil"): "js_math_ceil",
    ("Math", "round"): "js_math_round",
    ("Math", "abs"): "js_math_abs",
    ("Math", "sqrt"): "js_math_sqrt",
    ("Math", "pow"): "js_math_pow",
    ("Math", "imul"): "js_math_imul",
    ("Math", "random"): "js_math_random",
    ("Array", "isArray"): "js_is_array",
    ("Array", "from"): "js_array_from",
    ("Array", "of"): "js_array_of",
    ("Object", "keys"): "js_object_keys",
    ("Object", "values"): "js_object_values",
    ("Object", "entries"): "js_object_entries",
    ("Object", "fromEntries"): "js_object_from_entries",
    ("Object", "assign"): "js_object_assign",
    ("Number", "isFinite"): "js_is_finite",
    ("Number", "isNaN"): "js_is_nan",
    ("Number", "parseFloat"): "js_number",
    ("Number", "parseInt"): "__PARSE_INT__",
    ("JSON", "stringify"): "__JSON_STRINGIFY__",
    ("JSON", "parse"): "__JSON_PARSE__",
}

_GLOBAL_CONSTANTS = {
    ("Math", "PI"): "math.pi",
    ("Math", "E"): "math.e",
    ("Number", "MAX_SAFE_INTEGER"): "9007199254740991",
    ("Number", "MIN_SAFE_INTEGER"): "-9007199254740991",
    ("Number", "POSITIVE_INFINITY"): "float('inf')",
    ("Number", "NEGATIVE_INFINITY"): "float('-inf')",
    ("Number", "NaN"): "float('nan')",
}

def _collect_assigned_free_names(body_stmts: list) -> set[str]:
    """Walk the body AST (without descending into nested functions) and
    return identifier names that are the target of an AssignmentExpression
    but never declared via `var`/`let`/`const` at any depth in the same
    function scope.
    """
    declared: set[str] = set()
    assigned: set[str] = set()

    def collect_pattern_ids(target: dict, out: set[str]) -> None:
        t = target.get("type")
        if t == "Identifier":
            out.add(target["name"])
        elif t == "ObjectPattern":
            for prop in target.get("properties", []):
                if prop["type"] == "RestElement":
                    collect_pattern_ids(prop["argument"], out)
                else:
                    value = prop["value"]
                    if value["type"] == "AssignmentPattern":
                        value = value["left"]
                    collect_pattern_ids(value, out)
        elif t == "ArrayPattern":
            for elem in target.get("elements", []) or []:
                if elem is None:
                    continue
                if elem["type"] == "RestElement":
                    collect_pattern_ids(elem["argument"], out)
                elif elem["type"] == "AssignmentPattern":
                    collect_pattern_ids(elem["left"], out)
                else:
                    collect_pattern_ids(elem, out)
        elif t == "AssignmentPattern":
            collect_pattern_ids(target["left"], out)

    def walk(node):
        if isinstance(node, dict):
            t = node.get("type")
            if t in ("FunctionDeclaration", "FunctionExpression", "ArrowFunctionExpression"):
                # Don't descend into nested function bodies.
                if t == "FunctionDeclaration" and node.get("id"):
                    declared.add(node["id"]["name"])
                return
            if t == "VariableDeclarator":
                collect_pattern_ids(node["id"], declared)
                walk(node.get("init"))
                return
            if t == "AssignmentExpression":
                collect_pattern_ids(node["left"], assigned)
                walk(node["right"])
                return
            for k, v in node.items():
                if k in ("loc", "start", "end"):
                    continue
                walk(v)
        elif isinstance(node, list):
            for item in node:
                walk(item)

    for stmt in body_stmts:
        walk(stmt)
    return assigned - declared


_NEW_MAP = {
    "Set": "JsSet",
    "Map": "JsMap",
    "RegExp": "JsRegExp",
    "Error": "Exception",
    "TypeError": "TypeError",
    "RangeError": "ValueError",
}


@dataclass
class ParamPrelude:
    tmp: str
    pattern: dict | None = None
    default_guard: str | None = None


@dataclass
class Scope:
    """Track which identifiers are declared in the current function/block.

    Used to decide whether an identifier reference resolves to a local or
    a module-level import.
    """

    parent: "Scope | None" = None
    names: set[str] = field(default_factory=set)
    is_function: bool = False

    def declare(self, name: str) -> None:
        self.names.add(name)

    def has(self, name: str) -> bool:
        s: "Scope | None" = self
        while s is not None:
            if name in s.names:
                return True
            s = s.parent
        return False


@dataclass
class ModuleContext:
    """Per-file state collected while walking."""

    module_name: str
    exported: list[str] = field(default_factory=list)
    imports: dict[str, str] = field(default_factory=dict)  # local_name -> source module
    namespace_imports: dict[str, str] = field(default_factory=dict)  # alias -> module


class Walker:
    def __init__(self, module_name: str, import_map: dict[str, str]):
        """`import_map` maps JS relative paths to Python module basenames."""
        self.ctx = ModuleContext(module_name=module_name)
        self.import_map = import_map
        self.cb = CodeBuilder()
        self.root_scope = Scope(is_function=False)
        self.current_scope = self.root_scope
        self.current_function: str | None = None
        self._helper_counter = 0
        self._loop_vars_stack: list[list[str]] = []

    # ---------- entry ----------

    def walk(self, program: dict) -> str:
        self._emit_header()
        for node in program.get("body", []):
            self._emit_statement(node)
            self.cb.line()
        self._emit_exports()
        return self.cb.render()

    def _emit_header(self) -> None:
        self.cb.line('"""Auto-generated from JavaScript. Do not edit by hand."""')
        self.cb.line("# ruff: noqa")
        self.cb.line("from __future__ import annotations")
        self.cb.line("import math")
        self.cb.line("from ._runtime import (")
        self.cb.line("    UNDEFINED, JsMap, JsRegExp, JsSet,")
        self.cb.line("    is_nullish, is_undefined, js_add, js_array, js_call,")
        self.cb.line("    js_coalesce, js_concat, js_div, js_every, js_filter, js_find,")
        self.cb.line("    js_find_index, js_for_each, js_get, js_includes,")
        self.cb.line("    js_index_of, js_is_array, js_is_finite, js_is_nan,")
        self.cb.line("    js_logical_and, js_logical_or, js_map, js_math_abs,")
        self.cb.line("    js_math_ceil, js_math_floor, js_math_max, js_math_min,")
        self.cb.line("    js_math_pow, js_math_random, js_math_round, js_math_imul,")
        self.cb.line("    js_math_sqrt, js_mod, js_mul, js_number,")
        self.cb.line("    js_array_from, js_array_of,")
        self.cb.line("    js_object_assign, js_object_entries,")
        self.cb.line("    js_object_from_entries, js_object_keys, js_object_values,")
        self.cb.line("    js_optional, js_pow, js_slice, js_some, js_sort,")
        self.cb.line("    js_spread_array, js_spread_object, js_string_includes,")
        self.cb.line("    js_string_match, js_string_replace, js_string_split, js_sub,")
        self.cb.line("    js_template, js_truthy, js_typeof,")
        self.cb.line(")")
        self.cb.line()

    def _emit_exports(self) -> None:
        if not self.ctx.exported:
            return
        self.cb.line()
        names = ", ".join(repr(n) for n in self.ctx.exported)
        self.cb.line(f"__all__ = [{names}]")

    # ---------- statements ----------

    def _emit_statement(self, node: dict) -> None:
        t = node["type"]
        method = getattr(self, f"_stmt_{t}", None)
        if method is None:
            raise UnsupportedNode(t, self.current_function)
        method(node)

    def _stmt_ImportDeclaration(self, node: dict) -> None:
        source = node["source"]["value"]
        py_module = self._resolve_import(source)
        if py_module is None:
            self.cb.line(f"# import skipped: {source}")
            return
        spec_names: list[tuple[str, str]] = []
        for spec in node.get("specifiers", []):
            st = spec["type"]
            if st == "ImportSpecifier":
                imported = spec["imported"]["name"]
                local = spec["local"]["name"]
                spec_names.append((imported, local))
                self.ctx.imports[local] = py_module
                self.root_scope.declare(local)
            elif st == "ImportNamespaceSpecifier":
                alias = spec["local"]["name"]
                self.ctx.namespace_imports[alias] = py_module
                self.root_scope.declare(alias)
                self.cb.line(f"from . import {py_module} as {alias}")
                return
            elif st == "ImportDefaultSpecifier":
                local = spec["local"]["name"]
                self.ctx.imports[local] = py_module
                self.root_scope.declare(local)
                self.cb.line(f"from .{py_module} import {local}")
                return
        if spec_names:
            items = ", ".join(
                f"{imp}" if imp == local else f"{imp} as {local}"
                for imp, local in spec_names
            )
            self.cb.line(f"from .{py_module} import {items}")

    def _stmt_ExportNamedDeclaration(self, node: dict) -> None:
        decl = node.get("declaration")
        if decl is not None:
            # Track names, then emit the underlying declaration
            if decl["type"] == "FunctionDeclaration":
                self.ctx.exported.append(decl["id"]["name"])
            elif decl["type"] == "VariableDeclaration":
                for d in decl["declarations"]:
                    if d["id"]["type"] == "Identifier":
                        self.ctx.exported.append(d["id"]["name"])
            self._emit_statement(decl)
            return
        # `export { a, b }` — no declaration, just tracking
        for spec in node.get("specifiers", []):
            self.ctx.exported.append(spec["exported"]["name"])

    def _stmt_FunctionDeclaration(self, node: dict) -> None:
        name = self._ident(node["id"]["name"])
        params_src, param_names, preludes = self._emit_params(node.get("params", []))
        self.current_scope.declare(name)
        is_nested = self.current_scope is not self.root_scope
        self.cb.line(f"def {name}({params_src}):")
        self.cb.indent()
        prev_fn, self.current_function = self.current_function, name
        prev_scope = self.current_scope
        self.current_scope = Scope(parent=prev_scope, is_function=True)
        for p in param_names:
            self.current_scope.declare(p)
        body = node["body"]
        body_stmts = body.get("body", [])
        if is_nested:
            self._emit_nonlocal_decls(body_stmts, param_names)
        self._emit_preludes(preludes)
        if not body_stmts and not preludes:
            self.cb.line("pass")
        for stmt in body_stmts:
            self._emit_statement(stmt)
        self.cb.dedent()
        self.current_scope = prev_scope
        self.current_function = prev_fn

    def _stmt_VariableDeclaration(self, node: dict) -> None:
        for decl in node["declarations"]:
            self._emit_declarator(decl)

    def _emit_declarator(self, decl: dict) -> None:
        target = decl["id"]
        init = decl.get("init")
        init_expr = self._expr(init) if init is not None else "UNDEFINED"
        self._emit_assignment_target(target, init_expr)

    def _emit_assignment_target(self, target: dict, value_expr: str) -> None:
        t = target["type"]
        if t == "Identifier":
            name = self._ident(target["name"])
            self.current_scope.declare(name)
            self.cb.line(f"{name} = {value_expr}")
            return
        if t == "ObjectPattern":
            tmp = self._fresh_tmp()
            self.cb.line(f"{tmp} = {value_expr}")
            for prop in target["properties"]:
                if prop["type"] == "RestElement":
                    raise UnsupportedNode("ObjectPattern rest", self.current_function)
                key_node = prop["key"]
                if prop.get("computed"):
                    key_expr = self._expr(key_node)
                    key_ref = key_expr
                else:
                    key_name = key_node["name"] if key_node["type"] == "Identifier" else key_node["value"]
                    key_ref = repr(key_name)
                value_node = prop["value"]
                default_expr = None
                if value_node["type"] == "AssignmentPattern":
                    default_expr = self._expr(value_node["right"])
                    value_node = value_node["left"]
                if default_expr is not None:
                    getter = f"(lambda _v: {default_expr} if is_undefined(_v) else _v)(js_get({tmp}, {key_ref}))"
                else:
                    getter = f"js_get({tmp}, {key_ref})"
                self._emit_assignment_target(value_node, getter)
            return
        if t == "ArrayPattern":
            tmp = self._fresh_tmp()
            self.cb.line(f"{tmp} = js_array({value_expr})")
            for i, elem in enumerate(target["elements"]):
                if elem is None:
                    continue
                if elem["type"] == "RestElement":
                    rest_expr = f"{tmp}[{i}:]"
                    self._emit_assignment_target(elem["argument"], rest_expr)
                    continue
                default_expr = None
                value_node = elem
                if elem["type"] == "AssignmentPattern":
                    default_expr = self._expr(elem["right"])
                    value_node = elem["left"]
                if default_expr is not None:
                    getter = f"(lambda _v: {default_expr} if is_undefined(_v) else _v)(js_get({tmp}, {i}))"
                else:
                    getter = f"js_get({tmp}, {i})"
                self._emit_assignment_target(value_node, getter)
            return
        if t == "MemberExpression":
            # e.g. `obj.prop = value` (used as an assignment target)
            obj_expr = self._expr(target["object"])
            if target.get("computed"):
                key_expr = self._expr(target["property"])
            else:
                key_expr = repr(target["property"]["name"])
            self.cb.line(f"{obj_expr}[{key_expr}] = {value_expr}")
            return
        raise UnsupportedNode(f"assignment target {t}", self.current_function)

    def _stmt_ExpressionStatement(self, node: dict) -> None:
        expr = node["expression"]
        if expr["type"] == "AssignmentExpression":
            self._emit_assignment_expression(expr, as_statement=True)
            return
        self.cb.line(self._expr(expr))

    def _stmt_IfStatement(self, node: dict) -> None:
        test = self._expr(node["test"])
        self.cb.line(f"if js_truthy({test}):")
        self.cb.indent()
        self._emit_block_body(node["consequent"])
        self.cb.dedent()
        alt = node.get("alternate")
        while alt is not None and alt["type"] == "IfStatement":
            test2 = self._expr(alt["test"])
            self.cb.line(f"elif js_truthy({test2}):")
            self.cb.indent()
            self._emit_block_body(alt["consequent"])
            self.cb.dedent()
            alt = alt.get("alternate")
        if alt is not None:
            self.cb.line("else:")
            self.cb.indent()
            self._emit_block_body(alt)
            self.cb.dedent()

    def _stmt_ForOfStatement(self, node: dict) -> None:
        left = node["left"]
        if left["type"] == "VariableDeclaration":
            target = left["declarations"][0]["id"]
        else:
            target = left
        iter_expr = self._expr(node["right"])
        loop_var_names: list[str] = []
        if target["type"] == "Identifier":
            name = self._ident(target["name"])
            self.current_scope.declare(name)
            loop_var_names.append(name)
            self.cb.line(f"for {name} in js_array({iter_expr}):")
            self.cb.indent()
        else:
            tmp = self._fresh_tmp()
            self.cb.line(f"for {tmp} in js_array({iter_expr}):")
            self.cb.indent()
            self._emit_assignment_target(target, tmp)
            loop_var_names.append(tmp)
        self._loop_vars_stack.append(loop_var_names)
        self._emit_block_body(node["body"])
        self._loop_vars_stack.pop()
        self.cb.dedent()

    def _stmt_ReturnStatement(self, node: dict) -> None:
        arg = node.get("argument")
        if arg is None:
            self.cb.line("return UNDEFINED")
        else:
            self.cb.line(f"return {self._expr(arg)}")

    def _stmt_BlockStatement(self, node: dict) -> None:
        self._emit_block_body(node)

    def _emit_block_body(self, node: dict) -> None:
        if node["type"] != "BlockStatement":
            self._emit_statement(node)
            return
        body = node.get("body") or []
        if not body:
            self.cb.line("pass")
            return
        for stmt in body:
            self._emit_statement(stmt)

    # ---------- assignment ----------

    def _emit_assignment_expression(self, node: dict, as_statement: bool = False) -> str:
        op = node["operator"]
        target = node["left"]
        value = self._expr(node["right"])
        if op == "=":
            pass
        elif op in ("+=", "-=", "*=", "/=", "%=", "**="):
            current = self._expr(target)
            helper = {
                "+=": "js_add",
                "-=": "js_sub",
                "*=": "js_mul",
                "/=": "js_div",
                "%=": "js_mod",
                "**=": "js_pow",
            }[op]
            value = f"{helper}({current}, {value})"
        else:
            raise UnsupportedNode(f"assignment op {op}", self.current_function)
        if not as_statement:
            # Inline assignment (rare). Emit as walrus if identifier.
            if target["type"] == "Identifier":
                return f"({self._ident(target['name'])} := {value})"
            raise UnsupportedNode("inline assignment to non-identifier", self.current_function)
        self._emit_assignment_target(target, value)
        return ""

    # ---------- expressions ----------

    def _expr(self, node: dict | None) -> str:
        if node is None:
            return "UNDEFINED"
        t = node["type"]
        method = getattr(self, f"_expr_{t}", None)
        if method is None:
            raise UnsupportedNode(t, self.current_function)
        return method(node)

    def _expr_Identifier(self, node: dict) -> str:
        name = node["name"]
        if name == "undefined":
            return "UNDEFINED"
        if name == "null":
            return "None"
        if name == "true":
            return "True"
        if name == "false":
            return "False"
        if name == "NaN":
            return "float('nan')"
        if name == "Infinity":
            return "float('inf')"
        # Bare references to JS global constructors used as predicates/coercers.
        # Only translate if not shadowed by a local declaration.
        if not self.current_scope.has(name):
            if name == "Boolean":
                return "js_truthy"
            if name == "Number":
                return "js_number"
            if name == "String":
                return "str"
        return self._ident(name)

    def _expr_Literal(self, node: dict) -> str:
        if "regex" in node:
            pattern = node["regex"]["pattern"]
            flags = node["regex"]["flags"]
            return f"JsRegExp({pattern!r}, {flags!r})"
        value = node["value"]
        if value is None:
            return "None"
        if isinstance(value, bool):
            return "True" if value else "False"
        if isinstance(value, (int, float)):
            if isinstance(value, float) and value.is_integer() and abs(value) < 1e15:
                return repr(int(value)) + ".0" if "." in node.get("raw", "") or "e" in node.get("raw", "").lower() else repr(int(value))
            return repr(value)
        if isinstance(value, str):
            return repr(value)
        raise UnsupportedNode(f"literal type {type(value).__name__}", self.current_function)

    def _expr_TemplateLiteral(self, node: dict) -> str:
        # Interleave quasis (TemplateElements) with expressions in source order.
        parts: list[str] = []
        quasis = node["quasis"]
        exprs = node["expressions"]
        for i, q in enumerate(quasis):
            cooked = q["value"]["cooked"]
            parts.append(repr(cooked))
            if i < len(exprs):
                parts.append(self._expr(exprs[i]))
        return f"js_template({', '.join(parts)})"

    def _expr_ArrayExpression(self, node: dict) -> str:
        elements = node["elements"]
        has_spread = any(e is not None and e.get("type") == "SpreadElement" for e in elements)
        if not has_spread:
            items = [self._expr(e) if e is not None else "None" for e in elements]
            return f"[{', '.join(items)}]"
        parts = []
        for e in elements:
            if e is None:
                parts.append("None")
            elif e["type"] == "SpreadElement":
                parts.append(self._expr(e["argument"]))
            else:
                parts.append(f"[{self._expr(e)}]")
        return f"js_spread_array({', '.join(parts)})"

    def _expr_ObjectExpression(self, node: dict) -> str:
        props = node["properties"]
        has_spread = any(p.get("type") == "SpreadElement" for p in props)
        if not has_spread:
            items = []
            for p in props:
                items.append(self._emit_property(p))
            return "{" + ", ".join(items) + "}"
        # Interleave regular props and spreads via js_spread_object
        parts: list[str] = []
        buffer: list[str] = []
        for p in props:
            if p["type"] == "SpreadElement":
                if buffer:
                    parts.append("{" + ", ".join(buffer) + "}")
                    buffer = []
                parts.append(self._expr(p["argument"]))
            else:
                buffer.append(self._emit_property(p))
        if buffer:
            parts.append("{" + ", ".join(buffer) + "}")
        return f"js_spread_object({', '.join(parts)})"

    def _emit_property(self, prop: dict) -> str:
        key_node = prop["key"]
        if prop.get("computed"):
            key_expr = self._expr(key_node)
        elif key_node["type"] == "Identifier":
            key_expr = repr(key_node["name"])
        elif key_node["type"] == "Literal":
            key_expr = repr(key_node["value"])
        else:
            key_expr = self._expr(key_node)
        if prop.get("shorthand"):
            value_expr = self._expr(key_node)
        else:
            value_expr = self._expr(prop["value"])
        return f"{key_expr}: {value_expr}"

    def _expr_SpreadElement(self, node: dict) -> str:
        # Only reachable outside of ArrayExpression/ObjectExpression/CallExpression.
        raise UnsupportedNode("SpreadElement in unexpected position", self.current_function)

    def _expr_BinaryExpression(self, node: dict) -> str:
        op = node["operator"]
        left = self._expr(node["left"])
        right = self._expr(node["right"])
        if op == "===":
            return f"({left} == {right})"
        if op == "!==":
            return f"({left} != {right})"
        if op == "==":
            return f"({left} == {right})"
        if op == "!=":
            return f"({left} != {right})"
        if op == "+":
            return f"js_add({left}, {right})"
        if op == "-":
            return f"js_sub({left}, {right})"
        if op == "*":
            return f"js_mul({left}, {right})"
        if op == "/":
            return f"js_div({left}, {right})"
        if op == "%":
            return f"js_mod({left}, {right})"
        if op == "**":
            return f"js_pow({left}, {right})"
        if op in ("<", ">", "<=", ">="):
            return f"(js_number({left}) {op} js_number({right}))"
        if op == "in":
            return f"({left} in {right})"
        if op == "instanceof":
            return f"isinstance({left}, {right})"
        if op in ("&", "|", "^"):
            return f"({left} {op} {right})"
        if op in ("<<", ">>"):
            return f"({left} {op} {right})"
        if op == ">>>":
            return f"(({left} & 0xFFFFFFFF) >> {right})"
        raise UnsupportedNode(f"binary op {op}", self.current_function)

    def _expr_LogicalExpression(self, node: dict) -> str:
        op = node["operator"]
        left = self._expr(node["left"])
        right = self._expr(node["right"])
        if op == "&&":
            return f"js_logical_and({left}, {right})"
        if op == "||":
            return f"js_logical_or({left}, {right})"
        if op == "??":
            return f"js_coalesce({left}, {right})"
        raise UnsupportedNode(f"logical op {op}", self.current_function)

    def _expr_UnaryExpression(self, node: dict) -> str:
        op = node["operator"]
        arg = self._expr(node["argument"])
        if op == "!":
            return f"(not js_truthy({arg}))"
        if op == "-":
            return f"(-js_number({arg}))"
        if op == "+":
            return f"js_number({arg})"
        if op == "typeof":
            return f"js_typeof({arg})"
        if op == "void":
            return "UNDEFINED"
        if op == "~":
            return f"(~{arg})"
        raise UnsupportedNode(f"unary op {op}", self.current_function)

    def _expr_UpdateExpression(self, node: dict) -> str:
        # i++/++i/i--/--i — none in the loadout files per the node-type census,
        # but support them trivially in case.
        op = node["operator"]
        arg = node["argument"]
        if arg["type"] != "Identifier":
            raise UnsupportedNode("update on non-identifier", self.current_function)
        name = self._ident(arg["name"])
        delta = "+ 1" if op == "++" else "- 1"
        # Use walrus so the expression has a value (post/pre: we approximate post as pre).
        return f"({name} := {name} {delta})"

    def _expr_ConditionalExpression(self, node: dict) -> str:
        test = self._expr(node["test"])
        cons = self._expr(node["consequent"])
        alt = self._expr(node["alternate"])
        return f"({cons} if js_truthy({test}) else {alt})"

    def _expr_AssignmentExpression(self, node: dict) -> str:
        return self._emit_assignment_expression(node, as_statement=False)

    def _expr_SequenceExpression(self, node: dict) -> str:
        parts = [self._expr(e) for e in node["expressions"]]
        return f"({', '.join(parts)})[-1]"

    def _expr_ChainExpression(self, node: dict) -> str:
        # Optional chain: the child carries `optional: true` on the relevant links.
        return self._expr(node["expression"])

    def _expr_MemberExpression(self, node: dict) -> str:
        obj_node = node["object"]
        obj_expr = self._expr(obj_node)
        optional = node.get("optional", False)
        # Global namespace constants: Math.PI, Number.MAX_SAFE_INTEGER, etc.
        if (
            obj_node.get("type") == "Identifier"
            and not node.get("computed")
            and node["property"].get("type") == "Identifier"
        ):
            pair = (obj_node["name"], node["property"]["name"])
            if pair in _GLOBAL_CONSTANTS:
                return _GLOBAL_CONSTANTS[pair]
            # Namespace imports (e.g. `LoadoutCalc.foo`) become `foo` from the
            # imported module — we leave the attribute access alone since the
            # walker imports the module as `LoadoutCalc` at file top.
        if node.get("computed"):
            key_expr = self._expr(node["property"])
        else:
            key_expr = repr(node["property"]["name"])
        if optional:
            return f"js_optional({obj_expr}, {key_expr})"
        return f"js_get({obj_expr}, {key_expr})"

    def _expr_CallExpression(self, node: dict) -> str:
        callee = node["callee"]
        args = node.get("arguments", [])
        optional = node.get("optional", False)
        # Handle spreads in arg list
        has_spread = any(a["type"] == "SpreadElement" for a in args)
        rendered_args = self._render_args(args, has_spread)

        # 1) Identifier — direct call to function or imported helper
        if callee["type"] == "Identifier":
            name = callee["name"]
            if name == "Number":
                return f"js_number({rendered_args})" if not has_spread else f"js_number(*{rendered_args})"
            if name == "String":
                return f"str({rendered_args})"
            if name == "Boolean":
                return f"js_truthy({rendered_args})"
            if name == "Array":
                # Array(n) creates length-n list; not commonly used — warn
                return f"[None] * int({rendered_args})"
            resolved = self._ident(name)
            if has_spread:
                return f"{resolved}(*{rendered_args})"
            return f"{resolved}({rendered_args})"

        # 2) MemberExpression — method call
        if callee["type"] == "MemberExpression":
            obj_node = callee["object"]
            prop = callee["property"]
            computed = callee.get("computed", False)
            m_optional = callee.get("optional", False)
            # Namespace-imported module calls: e.g. LoadoutCalc.foo(args)
            if (
                obj_node.get("type") == "Identifier"
                and obj_node["name"] in self.ctx.namespace_imports
                and not computed
            ):
                module_alias = obj_node["name"]
                fn = prop["name"]
                return f"{module_alias}.{fn}({rendered_args})"
            # Global helper mapping: Math.max, Number.isFinite, etc.
            if (
                obj_node.get("type") == "Identifier"
                and not computed
                and (obj_node["name"], prop.get("name")) in _GLOBAL_MAP
            ):
                pair = (obj_node["name"], prop["name"])
                mapped = _GLOBAL_MAP[pair]
                if mapped == "__JSON_STRINGIFY__":
                    return f"__import__('json').dumps({rendered_args}, default=str)"
                if mapped == "__JSON_PARSE__":
                    return f"__import__('json').loads({rendered_args})"
                if mapped == "__PARSE_INT__":
                    return f"int(js_number({rendered_args}))"
                if has_spread:
                    return f"{mapped}(*{rendered_args})"
                return f"{mapped}({rendered_args})"
            # Wrapper-class method (JsSet/JsMap/JsRegExp literal) — route through js_call
            # General fallback: js_call(receiver, "method", *args)
            obj_expr = self._expr(obj_node)
            method_name = prop["name"] if not computed else f"({self._expr(prop)})"
            if computed:
                # Dynamic method name — rarer path
                if has_spread:
                    return f"js_call({obj_expr}, {self._expr(prop)}, *{rendered_args})"
                return f"js_call({obj_expr}, {self._expr(prop)}, {rendered_args})"
            if m_optional or optional:
                # obj?.method(args) — short-circuit if obj is nullish
                if has_spread:
                    return (
                        f"(UNDEFINED if is_nullish({obj_expr}) "
                        f"else js_call({obj_expr}, {method_name!r}, *{rendered_args}))"
                    )
                return (
                    f"(UNDEFINED if is_nullish({obj_expr}) "
                    f"else js_call({obj_expr}, {method_name!r}, {rendered_args}))"
                )
            if has_spread:
                return f"js_call({obj_expr}, {method_name!r}, *{rendered_args})"
            if rendered_args:
                return f"js_call({obj_expr}, {method_name!r}, {rendered_args})"
            return f"js_call({obj_expr}, {method_name!r})"

        # 3) Other callees (arrow, parenthesised expr, etc.)
        callee_expr = self._expr(callee)
        if has_spread:
            return f"({callee_expr})(*{rendered_args})"
        return f"({callee_expr})({rendered_args})"

    def _render_args(self, args: list, has_spread: bool) -> str:
        if has_spread:
            parts = []
            for a in args:
                if a["type"] == "SpreadElement":
                    parts.append(self._expr(a["argument"]))
                else:
                    parts.append(f"[{self._expr(a)}]")
            return f"js_spread_array({', '.join(parts)})"
        return ", ".join(self._expr(a) for a in args)

    def _expr_NewExpression(self, node: dict) -> str:
        callee = node["callee"]
        args = ", ".join(self._expr(a) for a in node.get("arguments", []))
        if callee["type"] == "Identifier":
            name = callee["name"]
            mapped = _NEW_MAP.get(name)
            if mapped:
                return f"{mapped}({args})"
            return f"{self._ident(name)}({args})"
        return f"({self._expr(callee)})({args})"

    def _expr_ArrowFunctionExpression(self, node: dict) -> str:
        params_src, param_names, preludes = self._emit_params(node.get("params", []))
        body = node["body"]
        if body["type"] != "BlockStatement" and not preludes:
            # Expression body with simple params — lambda, with outer loop
            # vars bound as defaults to dodge Python's late-binding closure bug.
            captured = self._current_loop_var_bindings()
            prev_scope = self.current_scope
            self.current_scope = Scope(parent=prev_scope, is_function=True)
            for p in param_names:
                self.current_scope.declare(p)
            body_expr = self._expr(body)
            self.current_scope = prev_scope
            all_params = params_src
            if captured:
                cap_parts = ", ".join(f"{n}={n}" for n in captured)
                all_params = f"{params_src}, {cap_parts}" if params_src else cap_parts
            return f"(lambda {all_params}: {body_expr})"
        # Block body or preludes needed — hoist as a nested def.
        fn_name = self._fresh_tmp(prefix="_arrow")
        captured = self._current_loop_var_bindings()
        cap_suffix = ", " + ", ".join(f"{n}={n}" for n in captured) if captured else ""
        self.cb.line(f"def {fn_name}({params_src}{cap_suffix}):")
        self.cb.indent()
        prev_fn, self.current_function = self.current_function, fn_name
        prev_scope = self.current_scope
        self.current_scope = Scope(parent=prev_scope, is_function=True)
        for p in param_names:
            self.current_scope.declare(p)
        body_stmts = body.get("body", []) if body["type"] == "BlockStatement" else []
        if body["type"] == "BlockStatement":
            self._emit_nonlocal_decls(body_stmts, list(param_names) + list(captured))
        self._emit_preludes(preludes)
        if body["type"] == "BlockStatement":
            if not body_stmts and not preludes:
                self.cb.line("pass")
            for stmt in body_stmts:
                self._emit_statement(stmt)
        else:
            self.cb.line(f"return {self._expr(body)}")
        self.cb.dedent()
        self.current_scope = prev_scope
        self.current_function = prev_fn
        return fn_name

    def _expr_FunctionExpression(self, node: dict) -> str:
        # Treat like arrow with block body
        node_copy = dict(node)
        node_copy["type"] = "ArrowFunctionExpression"
        return self._expr_ArrowFunctionExpression(node_copy)

    def _expr_ThisExpression(self, node: dict) -> str:
        raise UnsupportedNode("this", self.current_function, "no class/method context")

    # ---------- params ----------

    def _emit_params(self, params: list) -> tuple[str, list[str], list["ParamPrelude"]]:
        parts: list[str] = []
        names: list[str] = []
        preludes: list[ParamPrelude] = []
        for p in params:
            src, name, prelude = self._emit_param(p)
            parts.append(src)
            if name:
                names.append(name)
            if prelude is not None:
                preludes.append(prelude)
        return ", ".join(parts), names, preludes

    def _emit_param(self, p: dict) -> tuple[str, str | None, "ParamPrelude | None"]:
        t = p["type"]
        if t == "Identifier":
            name = self._ident(p["name"])
            return name, name, None
        if t == "AssignmentPattern":
            left = p["left"]
            right = p["right"]
            if left["type"] == "Identifier":
                name = self._ident(left["name"])
                if self._is_mutable_default(right):
                    default_expr = self._expr(right)
                    return f"{name}=None", name, ParamPrelude(
                        tmp=name, default_guard=default_expr
                    )
                default_expr = self._expr(right)
                return f"{name}={default_expr}", name, None
            tmp = self._fresh_tmp(prefix="_arg")
            default_expr = self._expr(right)
            if self._is_mutable_default(right):
                return (
                    f"{tmp}=None",
                    tmp,
                    ParamPrelude(tmp=tmp, pattern=left, default_guard=default_expr),
                )
            return (
                f"{tmp}={default_expr}",
                tmp,
                ParamPrelude(tmp=tmp, pattern=left),
            )
        if t == "ObjectPattern":
            tmp = self._fresh_tmp(prefix="_arg")
            return tmp, tmp, ParamPrelude(tmp=tmp, pattern=p)
        if t == "ArrayPattern":
            tmp = self._fresh_tmp(prefix="_arg")
            return tmp, tmp, ParamPrelude(tmp=tmp, pattern=p)
        if t == "RestElement":
            name = self._ident(p["argument"]["name"])
            return f"*{name}", name, None
        raise UnsupportedNode(f"param {t}", self.current_function)

    @staticmethod
    def _is_mutable_default(node: dict) -> bool:
        t = node.get("type")
        return t in ("ObjectExpression", "ArrayExpression")

    def _emit_nonlocal_decls(self, body_stmts: list, param_names: list[str]) -> None:
        """Emit `nonlocal` declarations for names assigned in the body that
        live in an enclosing (non-module) function scope.

        Without this, Python treats any assignment as creating a new local,
        which silently breaks JS-style closures like
            `let total = 0; arr.forEach(x => { total += x })`.
        """
        assigned = _collect_assigned_free_names(body_stmts)
        assigned -= set(param_names)
        nonlocal_names: list[str] = []
        for name in sorted(assigned):
            py_name = self._ident(name)
            # Walk up from the parent scope; root_scope is module-level (no nonlocal).
            scope: Scope | None = self.current_scope.parent
            while scope is not None and scope is not self.root_scope:
                if py_name in scope.names:
                    nonlocal_names.append(py_name)
                    break
                scope = scope.parent
        if nonlocal_names:
            self.cb.line(f"nonlocal {', '.join(nonlocal_names)}")

    def _emit_preludes(self, preludes: list["ParamPrelude"]) -> None:
        for pre in preludes:
            if pre.default_guard is not None:
                self.cb.line(
                    f"{pre.tmp} = {pre.default_guard} if {pre.tmp} is None else {pre.tmp}"
                )
            if pre.pattern is not None:
                self._emit_assignment_target(pre.pattern, pre.tmp)

    # ---------- helpers ----------

    def _current_loop_var_bindings(self) -> list[str]:
        out: list[str] = []
        for level in self._loop_vars_stack:
            out.extend(level)
        return out

    def _fresh_tmp(self, prefix: str = "_tmp") -> str:
        self._helper_counter += 1
        return f"{prefix}{self._helper_counter}"

    def _ident(self, name: str) -> str:
        if name in _PY_RESERVED:
            return name + "_"
        return name

    def _resolve_import(self, js_path: str) -> str | None:
        """Map a JS import path to a Python module basename."""
        return self.import_map.get(js_path)
