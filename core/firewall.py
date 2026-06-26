import ast
import math
from typing import Dict, Any


class FirewallViolation(Exception):
    """Raised when an expression contains disallowed AST nodes or access paths."""
    pass


class ASTSafeEvaluator(ast.NodeVisitor):
    """
    Compile-time AST whitelist inspector.
    Supports Python 3.8-3.14 (ast.Num removed in 3.12; only ast.Constant remains).
    """
    ALLOWED_NODE_TYPES = {
        ast.Expression, ast.BinOp, ast.Constant,
        ast.Add, ast.Sub, ast.Mult, ast.Div, ast.FloorDiv, ast.Pow,
        ast.UnaryOp, ast.USub, ast.UAdd, ast.Name, ast.Load, ast.Call,
    }
    ALLOWED_FUNCTIONS = {"ln", "log", "exp", "sqrt", "abs", "pow"}

    def generic_visit(self, node):
        if type(node) not in self.ALLOWED_NODE_TYPES:
            raise FirewallViolation(
                f"Disallowed structural AST node detected: {type(node).__name__}"
            )
        if isinstance(node, ast.Call):
            if not isinstance(node.func, ast.Name) or node.func.id not in self.ALLOWED_FUNCTIONS:
                raise FirewallViolation(
                    f"Unauthorized function execution attempt: {ast.dump(node.func)}"
                )
        super().generic_visit(node)


class DeterministicRuntime:
    """Handles safe expression evaluation over validated operational data vectors."""

    @staticmethod
    def get_safe_context() -> Dict[str, Any]:
        return {
            "ln":   math.log,
            "log":  math.log,
            "exp":  math.exp,
            "sqrt": math.sqrt,
            "abs":  abs,
            "pow":  pow,
        }

    @classmethod
    def evaluate_safely(cls, expression_str: str, variable_context: Dict[str, float]) -> float:
        try:
            parsed_ast = ast.parse(expression_str, mode="eval")
            inspector  = ASTSafeEvaluator()
            inspector.visit(parsed_ast)

            execution_scope = cls.get_safe_context()
            execution_scope.update(variable_context)

            compiled_code = compile(parsed_ast, filename="<llm_fallback_node>", mode="eval")
            return float(eval(compiled_code, {"__builtins__": None}, execution_scope))   # noqa: S307

        except FirewallViolation:
            raise
        except Exception as err:
            raise FirewallViolation(
                f"AST Evaluation engine compilation failure: {err}"
            ) from err
