from .ast import *
from .visitors import PatternVariableAssignmentVisitor, CopyVisitor, FreePatternVariableVisitor

"""
Utility functions on KORE AST
"""
class KoreUtils:
    @staticmethod
    def copy_pattern(module: Module, pattern: Pattern) -> Pattern:
        copied_pattern = pattern.visit(CopyVisitor())
        copied_pattern.resolve(module)
        return copied_pattern

    @staticmethod
    def copy_and_substitute(module: Module, pattern: Pattern, substitution: Mapping[Variable, Pattern]) -> Pattern:
        copied = KoreUtils.copy_pattern(module, pattern)
        return copied.visit(PatternVariableAssignmentVisitor(substitution))

    """
    Expand one pattern that uses an alias definition
    and return a new pattern
    """
    @staticmethod
    def expand_alias_def(application: Application, alias_def: AliasDefinition) -> Pattern:
        assert application.symbol.definition == alias_def.definition

        variables = alias_def.get_binding_variables()

        if len(application.arguments) != len(variables):
            application.error_with_position("unmatched number of arguments in the use of alias")

        assignment = { var: arg for var, arg in zip(variables, application.arguments) }
        assignment_visitor = PatternVariableAssignmentVisitor(assignment)
        
        copied_rhs = KoreUtils.copy_pattern(alias_def.get_parent(), alias_def.rhs)
        copied_rhs.visit(assignment_visitor)

        return copied_rhs

    @staticmethod
    def instantiate_one_alias_use(module: Module, alias_def: AliasDefinition):
        for user in alias_def.definition.users:
            parent = user.get_parent()
            
            if isinstance(parent, Application) or isinstance(parent, MLPattern):
                for i, arg in enumerate(parent.arguments):
                    if arg == user:
                        parent.arguments[i] = KoreUtils.expand_alias_def(arg, alias_def)
                        break
                else:
                    assert False, "unable to find corresponding child"
            elif isinstance(parent, AliasDefinition):
                if parent.rhs == user:
                    parent.rhs = KoreUtils.expand_alias_def(parent.rhs, alias_def)
            elif isinstance(parent, Axiom):
                assert parent.pattern == user
                parent.pattern = KoreUtils.expand_alias_def(parent.pattern, alias_def)
            else:
                user.error_with_position("unable to instantiate alias")

    """
    Replace all alias uses with their definition
    """
    @staticmethod
    def instantiate_all_alias_uses(module: Module):
        alias_defs = list(module.alias_map.values())
        for alias_def in alias_defs:
            KoreUtils.instantiate_one_alias_use(module, alias_def)

        for alias_def in alias_defs:
            module.remove_sentence(alias_def)

    """
    Quantify all free (pattern) variables in the axioms
    """
    @staticmethod
    def quantify_all_free_variables(module: Module):
        for axiom in module.axioms:
            free_vars = axiom.pattern.visit(FreePatternVariableVisitor())
            body = axiom.pattern

            for free_var in free_vars:
                # TODO: fix the output sort here
                body = MLPattern(MLPattern.FORALL, [], [ free_var, body ])

            axiom.pattern = body
