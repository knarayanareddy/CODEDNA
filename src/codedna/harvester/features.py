"""Feature extraction for CodeDNA - 32-dimensional feature vector."""
import ast
import hashlib
from dataclasses import dataclass
from typing import List, Set, Tuple, Set as SetType

VECTOR_DIMS = 32


@dataclass
class FeatureVector:
    snake_case_ratio: float = 0.0
    single_char_var_rate: float = 0.0
    abbrev_rate: float = 0.0
    avg_function_length: float = 0.0
    nesting_depth: float = 0.0
    class_ratio: float = 0.0
    comprehension_rate: float = 0.0
    lambda_rate: float = 0.0
    decorator_rate: float = 0.0
    try_except_ratio: float = 0.0
    bare_except_rate: float = 0.0
    assert_rate: float = 0.0
    docstring_rate: float = 0.0
    inline_comment_density: float = 0.0
    todo_comment_rate: float = 0.0
    stdlib_ratio: float = 0.0
    relative_import_rate: float = 0.0
    star_import_rate: float = 0.0
    line_length_avg: float = 0.0
    line_length_max: float = 0.0
    blank_line_density: float = 0.0
    max_function_params: float = 0.0
    type_hint_rate: float = 0.0
    async_def_rate: float = 0.0
    yield_rate: float = 0.0
    match_case_rate: float = 0.0
    walrus_operator_rate: float = 0.0
    fstring_rate: float = 0.0
    list_append_in_loop: float = 0.0
    dict_get_rate: float = 0.0
    context_manager_rate: float = 0.0
    generator_rate: float = 0.0

    def to_list(self) -> List[float]:
        return [self.snake_case_ratio, self.single_char_var_rate, self.abbrev_rate,
                self.avg_function_length, self.nesting_depth, self.class_ratio,
                self.comprehension_rate, self.lambda_rate, self.decorator_rate,
                self.try_except_ratio, self.bare_except_rate, self.assert_rate,
                self.docstring_rate, self.inline_comment_density, self.todo_comment_rate,
                self.stdlib_ratio, self.relative_import_rate, self.star_import_rate,
                self.line_length_avg, self.line_length_max, self.blank_line_density,
                self.max_function_params, self.type_hint_rate, self.async_def_rate,
                self.yield_rate, self.match_case_rate, self.walrus_operator_rate,
                self.fstring_rate, self.list_append_in_loop, self.dict_get_rate,
                self.context_manager_rate, self.generator_rate]

    @classmethod
    def from_list(cls, data: List[float]) -> "FeatureVector":
        if len(data) != VECTOR_DIMS:
            raise ValueError(f"Expected {VECTOR_DIMS} dimensions, got {len(data)}")
        return cls(*data)


def compute_body_hash(content: str) -> str:
    return hashlib.sha256(content.encode()).hexdigest()


def is_snake_case(name: str) -> bool:
    if not name or not name.isidentifier():
        return False
    return name.islower() or '_' in name


def is_abbreviation(name: str) -> bool:
    if len(name) <= 2:
        return True
    if name.isupper() and len(name) <= 4:
        return True
    return False


def _get_nesting_depth(node: ast.AST, current_depth: int = 0) -> int:
    """Calculate the maximum nesting depth within a node.
    
    This is a recursive helper that calculates nesting depth by looking at
    block statements (if, for, while, with, try, except).
    """
    max_depth = current_depth
    
    for child in ast.iter_child_nodes(node):
        if isinstance(child, (ast.If, ast.For, ast.While, ast.With, ast.AsyncWith,
                               ast.Try, ast.ExceptHandler)):
            child_depth = _get_nesting_depth(child, current_depth + 1)
            max_depth = max(max_depth, child_depth)
        elif isinstance(child, ast.FunctionDef):
            # Functions start a new nesting scope, don't count internal blocks
            continue
        elif isinstance(child, ast.AsyncFunctionDef):
            continue
        elif isinstance(child, ast.ClassDef):
            # Classes don't increase nesting for code style analysis
            continue
        else:
            # Continue traversing for other block-like structures
            child_depth = _get_nesting_depth(child, current_depth)
            max_depth = max(max_depth, child_depth)
    
    return max_depth


def _find_direct_append_calls(node: ast.AST) -> SetType[int]:
    """
    Find .append() calls that are direct children of this node's body (not nested in inner blocks).
    
    Uses a set to track node IDs and avoid double-counting in nested structures.
    
    This is specifically designed for For/While loops where we want to count append
    calls in the loop body without counting those in nested loops inside the body.
    """
    append_node_ids = set()
    
    # Get the body attribute (for For, While, With, etc.)
    body = getattr(node, 'body', None)
    if not body:
        return append_node_ids
    
    # Only look at direct statements in the loop body
    for stmt in body:
        if isinstance(stmt, ast.Expr) and isinstance(stmt.value, ast.Call):
            call = stmt.value
            if isinstance(call.func, ast.Attribute) and call.func.attr == 'append':
                # Use id() to uniquely identify this node
                append_node_ids.add(id(call))
    
    return append_node_ids


class FeatureExtractor(ast.NodeVisitor):
    """
    Single-pass AST visitor that extracts all 32 features without nested walks.
    
    This avoids quadratic O(N^2) complexity of nested ast.walk() calls.
    
    Key fixes applied:
    - Nesting depth: Calculates per-function depth and averages them
    - List append tracking: Uses node ID tracking to avoid double counting
    """
    
    def __init__(self):
        # Identifier counts
        self.total_identifiers: int = 0
        self.snake_case_count: int = 0
        self.single_char_count: int = 0
        self.abbrev_count: int = 0
        
        # Function/class tracking
        self.functions: List[ast.FunctionDef] = []
        self.classes: List[ast.ClassDef] = []
        self.max_params: int = 0
        
        # Per-function nesting depths (for proper averaging)
        self.function_nesting_depths: List[int] = []
        
        # Syntax feature counts (using set to avoid double counting)
        self.comprehensions: int = 0
        self.lambdas: int = 0
        self.decorators: int = 0
        self.try_blocks: int = 0
        self.bare_excepts: int = 0
        self.asserts: int = 0
        self.type_hints: int = 0
        self.async_defs: int = 0
        self.yields: int = 0
        self.walrus_operators: int = 0
        self.fstrings: int = 0
        self.list_appends: SetType[int] = set()  # Use IDs to track unique append calls
        self.dict_gets: int = 0
        self.context_managers: int = 0
        self.generators: int = 0
        self.match_cases: int = 0
        
        # Docstring tracking
        self.docstrings: int = 0
        
        # Import tracking
        self.imports: List[str] = []
        self.relative_imports: int = 0
        self.star_imports: int = 0
    
    def visit_Name(self, node: ast.Name):
        if isinstance(node.ctx, ast.Store):
            self.total_identifiers += 1
            name = node.id
            if is_snake_case(name):
                self.snake_case_count += 1
            if len(name) == 1 and not name.startswith('_'):
                self.single_char_count += 1
            if is_abbreviation(name):
                self.abbrev_count += 1
        self.generic_visit(node)
    
    def visit_FunctionDef(self, node: ast.FunctionDef):
        self.functions.append(node)
        if node.decorator_list:
            self.decorators += len(node.decorator_list)
        self.max_params = max(self.max_params, len(node.args.args))
        
        # Calculate nesting depth for this function only
        # Start at depth 1 (function body itself counts)
        func_nesting = _get_nesting_depth(node, 1)
        self.function_nesting_depths.append(func_nesting)
        
        self.generic_visit(node)
    
    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef):
        self.functions.append(node)
        self.async_defs += 1
        if node.decorator_list:
            self.decorators += len(node.decorator_list)
        self.max_params = max(self.max_params, len(node.args.args))
        
        # Calculate nesting depth for this function
        func_nesting = _get_nesting_depth(node, 1)
        self.function_nesting_depths.append(func_nesting)
        
        self.generic_visit(node)
    
    def visit_ClassDef(self, node: ast.ClassDef):
        self.classes.append(node)
        self.generic_visit(node)
    
    def visit_ListComp(self, node: ast.ListComp):
        self.comprehensions += 1
        self.generic_visit(node)
    
    def visit_DictComp(self, node: ast.DictComp):
        self.comprehensions += 1
        self.generic_visit(node)
    
    def visit_SetComp(self, node: ast.SetComp):
        self.comprehensions += 1
        self.generic_visit(node)
    
    def visit_GeneratorExp(self, node: ast.GeneratorExp):
        self.comprehensions += 1
        self.generic_visit(node)
    
    def visit_Lambda(self, node: ast.Lambda):
        self.lambdas += 1
        self.generic_visit(node)
    
    def visit_NamedExpr(self, node: ast.NamedExpr):
        self.walrus_operators += 1
        self.generic_visit(node)
    
    def visit_Try(self, node: ast.Try):
        self.try_blocks += 1
        for handler in node.handlers:
            if handler.type is None:
                self.bare_excepts += 1
        self.generic_visit(node)
    
    def visit_Assert(self, node: ast.Assert):
        self.asserts += 1
        self.generic_visit(node)
    
    def visit_arg(self, node: ast.arg):
        if node.annotation:
            self.type_hints += 1
        self.generic_visit(node)
    
    def visit_JoinedStr(self, node: ast.JoinedStr):
        self.fstrings += 1
        self.generic_visit(node)
    
    def visit_Yield(self, node: ast.Yield):
        self.yields += 1
        self.generic_visit(node)
    
    def visit_YieldFrom(self, node: ast.YieldFrom):
        self.yields += 1
        self.generic_visit(node)
    
    def visit_Expr(self, node: ast.Expr):
        """Track docstrings (string literals as first statement in function/class/module)."""
        if isinstance(node.value, ast.Constant) and isinstance(node.value.value, str):
            if node.value.value.strip():
                self.docstrings += 1
        self.generic_visit(node)
    
    def visit_Import(self, node: ast.Import):
        for alias in node.names:
            self.imports.append(alias.name)
        self.generic_visit(node)
    
    def visit_ImportFrom(self, node: ast.ImportFrom):
        if node.level > 0:
            self.relative_imports += 1
        for alias in node.names:
            if alias.name == '*':
                self.star_imports += 1
        self.generic_visit(node)
    
    def visit_With(self, node: ast.With):
        self.context_managers += 1
        self.generic_visit(node)
    
    def visit_AsyncWith(self, node: ast.AsyncWith):
        self.context_managers += 1
        self.generic_visit(node)
    
    def visit_For(self, node: ast.For):
        # Track list.append calls inside this specific loop only
        # Using set to track node IDs prevents double counting in nested loops
        append_ids = _find_direct_append_calls(node)
        self.list_appends.update(append_ids)
        self.generic_visit(node)
    
    def visit_Call(self, node: ast.Call):
        if isinstance(node.func, ast.Attribute):
            if node.func.attr == 'get':
                self.dict_gets += 1
        self.generic_visit(node)
    
    def visit_Match(self, node: ast.Match):
        self.match_cases += 1
        self.generic_visit(node)
    
    def generic_visit(self, node: ast.AST):
        """Override to ensure single-pass traversal."""
        for _, child in ast.iter_fields(node):
            if isinstance(child, ast.AST):
                self.visit(child)
            elif isinstance(child, list):
                for item in child:
                    if isinstance(item, ast.AST):
                        self.visit(item)


def extract_features(source: str, file_path: str = "") -> FeatureVector:
    """
    Extract 32-dimensional feature vector from Python source code.
    
    Uses a single-pass AST visitor to avoid O(N^2) complexity from nested walks.
    
    Nesting depth is calculated as the average of per-function nesting depths,
    not the global maximum divided by function count.
    """
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return FeatureVector()
    
    total_lines = len(source.splitlines())
    lines = source.splitlines()
    line_lengths = [len(line) for line in lines]
    blank_lines = sum(1 for line in lines if not line.strip())
    
    # Count comment lines
    comments = 0
    todos = 0
    for line in lines:
        stripped = line.strip()
        if stripped.startswith('#'):
            comments += 1
            if 'todo' in stripped.lower() or 'fixme' in stripped.lower():
                todos += 1
    
    # Use single-pass visitor
    extractor = FeatureExtractor()
    extractor.visit(tree)
    
    total_defs = len(extractor.functions) + len(extractor.classes)
    total_ids = max(1, extractor.total_identifiers)
    num_functions = max(1, len(extractor.functions))
    
    # Compute function lengths
    function_lengths = []
    for func in extractor.functions:
        if func.end_lineno and func.lineno:
            function_lengths.append(func.end_lineno - func.lineno)
    
    avg_function_length = sum(function_lengths) / max(1, len(function_lengths)) if function_lengths else 0.0
    
    # Calculate average nesting depth across all functions
    # This is the correct mathematical approach: average of per-function depths
    if extractor.function_nesting_depths:
        avg_nesting = sum(extractor.function_nesting_depths) / len(extractor.function_nesting_depths)
    else:
        avg_nesting = 0.0
    
    return FeatureVector(
        snake_case_ratio=extractor.snake_case_count / total_ids,
        single_char_var_rate=extractor.single_char_count / total_ids,
        abbrev_rate=extractor.abbrev_count / total_ids,
        avg_function_length=avg_function_length,
        nesting_depth=avg_nesting,
        class_ratio=len(extractor.classes) / max(1, total_defs),
        comprehension_rate=extractor.comprehensions / max(1, total_defs),
        lambda_rate=extractor.lambdas / max(1, total_defs),
        decorator_rate=extractor.decorators / max(1, total_defs),
        try_except_ratio=extractor.try_blocks / max(1, total_defs),
        bare_except_rate=extractor.bare_excepts / max(1, extractor.try_blocks) if extractor.try_blocks > 0 else 0,
        assert_rate=extractor.asserts / max(1, total_defs),
        docstring_rate=extractor.docstrings / max(1, total_defs),
        inline_comment_density=comments / max(1, total_lines),
        todo_comment_rate=todos / max(1, comments) if comments > 0 else 0,
        stdlib_ratio=len(extractor.imports) / max(1, len(extractor.imports)) if extractor.imports else 0,
        relative_import_rate=extractor.relative_imports / max(1, len(extractor.imports)) if extractor.imports else 0,
        star_import_rate=extractor.star_imports / max(1, len(extractor.imports)) if extractor.imports else 0,
        line_length_avg=sum(line_lengths) / max(1, len(line_lengths)) if line_lengths else 0,
        line_length_max=max(line_lengths) if line_lengths else 0,
        blank_line_density=blank_lines / max(1, total_lines),
        max_function_params=extractor.max_params,
        type_hint_rate=extractor.type_hints / max(1, total_defs * 2),
        async_def_rate=extractor.async_defs / max(1, num_functions),
        yield_rate=extractor.yields / max(1, total_defs),
        match_case_rate=extractor.match_cases / max(1, total_defs),
        walrus_operator_rate=extractor.walrus_operators / max(1, total_defs),
        fstring_rate=extractor.fstrings / max(1, total_defs),
        list_append_in_loop=len(extractor.list_appends) / max(1, total_defs),
        dict_get_rate=extractor.dict_gets / max(1, total_defs),
        context_manager_rate=extractor.context_managers / max(1, total_defs),
        generator_rate=extractor.generators / max(1, total_defs),
    )