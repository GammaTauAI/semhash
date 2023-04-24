# this program crates a semantic hash of a python function,
# such that two different functions with the same semantic hash
# are guaranteed to have the same semantic meaning.
import ast
from typing import List, Any
import z3


def get_first_function_decl(code: ast.AST) -> ast.FunctionDef | None:
    """
    Grabs the first function declaration in the given code.
    """
    for node in ast.walk(code):
        if isinstance(node, ast.FunctionDef):
            return node


# z3 datatype for python types
# TODO: we need to support way more types than this
Z3PyType = z3.Datatype("Z3PyValue")
Z3PyType.declare("int")
Z3PyType.declare("str")
Z3PyType.declare("bool")
Z3PyType.declare("list", ("type", Z3PyType))
Z3PyType.declare("none")
Z3PyType = Z3PyType.create()


def pytype_to_z3type(pytype: ast.AST) -> z3.DatatypeRef:
    if isinstance(pytype, ast.Name):
        match pytype.id:
            case "int":
                return Z3PyType.int
            case "str":
                return Z3PyType.str
            case "bool":
                return Z3PyType.bool
            case "list":
                raise NotImplementedError(
                    "list type without arg not implemented")
            case "None":
                return Z3PyType.none
            case _:
                raise NotImplementedError(f"Unimplemented type {pytype.id}")
    elif isinstance(pytype, ast.Subscript):
        # value should be a Name
        # slice should be a Name
        match pytype:
            case ast.Subscript(value=ast.Name(id="List"),
                               slice=_,
                               ctx=_):
                raise NotImplementedError(
                    "list type not yet implemented")
            case _:
                raise NotImplementedError(
                    f"Unimplemented subscript type {pytype}")
    else:
        raise ValueError(
            f"The given AST node is not a type annotation: {pytype}")


class SolverVisitor(ast.NodeVisitor):
    def __init__(self):
        self.solver = z3.Solver()
        self.solver.set("timeout", 1000)

        # toplevel function declaration
        self.fundecl: ast.FunctionDef | None = None

        self.z3_args = []
        self.z3_ret = None

        self.z3_func = None

        self.env = {}

    def check_solved(self) -> bool:
        return self.solver.check() == z3.sat

    #
    # visitor methods below
    #

    def generic_visit(self, node: ast.AST) -> Any:
        return super().generic_visit(node)

    def visit(self, node: ast.AST) -> Any:
        super().visit(node)
        return None

    def visit_FunctionDef(self, node: ast.FunctionDef) -> Any:
        if self.fundecl is not None:
            # TODO: generalize this to multiple function declarations
            raise ValueError("Only one function declaration is allowed")

        self.fundecl = node

        for arg in node.args.args:  # TODO: there are more types of arguments
            const = z3.BitVec(f"__arg_{arg.arg}", 64)
            self.z3_args.append(const)
            self.env[arg.arg] = const

        self.z3_ret = z3.BitVec("__ret", 64)

        fun_args = [z3.BitVecSort(64)] * (len(self.z3_args) + 1)
        self.z3_func = z3.Function(node.name, *fun_args)

        for stmt in node.body:
            super().visit(stmt)

    def visit_BinOp(self, node: ast.BinOp) -> Any:
        print(f"binop: {node.op.__class__.__name__}")
        return super().generic_visit(node)

    # assignment
    def visit_Assign(self, node: ast.Assign) -> Any:
        for target in node.targets:
            if isinstance(target, ast.Name):
                print(f"assign: {target.id}")
                self.env[target.id] = self.visit(node.value)
            else:
                raise NotImplementedError(
                    f"Unimplemented assignment target {target}")

        return None

    def visit_Name(self, node: ast.Name) -> Any:
        print(f"name: {node.id}")
        if node.id in self.env:
            return self.env[node.id]
        else:
            raise ValueError(f"Undefined variable {node.id}")

    def visit_Return(self, node: ast.Return) -> Any:
        print("return")
        return super().generic_visit(node)


if __name__ == "__main__":
    CODE1 = get_first_function_decl(ast.parse("""
def f(x: int) -> List[int]:
    x = 1
    y = 2
    return x + y
    """))
    assert CODE1 is not None

    # TODO we are not going to use CODE2 for now
    CODE2 = get_first_function_decl(ast.parse("""
def f(x: int) -> int:
    return x + 2
    """))
    assert CODE2 is not None

    print(ast.dump(CODE1, indent=4))

    res = SolverVisitor().visit(CODE1)
    print(res)
