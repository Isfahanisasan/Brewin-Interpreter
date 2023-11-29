import copy
from enum import Enum

from brewparse import parse_program
from env_v3 import EnvironmentManager
from intbase import InterpreterBase, ErrorType
from type_valuev3 import Closure, Type, Value, create_value, get_printable, ObjectInstance


class ExecStatus(Enum):
    CONTINUE = 1
    RETURN = 2


# Main interpreter class
class Interpreter(InterpreterBase):
    # constants
    NIL_VALUE = create_value(InterpreterBase.NIL_DEF)
    TRUE_VALUE = create_value(InterpreterBase.TRUE_DEF)
    BIN_OPS = {"+", "-", "*", "/", "==", "!=", ">", ">=", "<", "<=", "||", "&&"}

    # methods
    def __init__(self, console_output=True, inp=None, trace_output=False):
        super().__init__(console_output, inp)
        self.trace_output = trace_output
        self.__setup_ops()

    # run a program that's provided in a string
    # usese the provided Parser found in brewparse.py to parse the program
    # into an abstract syntax tree (ast)
    def run(self, program):
        ast = parse_program(program)
        # print(ast)
        self.__set_up_function_table(ast)
        self.env = EnvironmentManager()
        main_func = self.__get_func_by_name("main", 0)
        if main_func is None:
            super().error(ErrorType.NAME_ERROR, f"Function main not found")
        self.__run_statements(main_func.func_ast.get("statements"))
    
    #initialized the function table
    #in which each function_name maps to another dictionary 
    #in which number of parameters (different overloaded versions) maps to a closure
    #which holds the func_def and the environemnt they capture which is the empty 
    #environement in the beginning!
    def __set_up_function_table(self, ast):
        self.func_name_to_ast = {}
        empty_env = EnvironmentManager()
        for func_def in ast.get("functions"):
            func_name = func_def.get("name")
            num_params = len(func_def.get("args"))
            if func_name not in self.func_name_to_ast:
                self.func_name_to_ast[func_name] = {}
            self.func_name_to_ast[func_name][num_params] = Closure(func_def, empty_env)
    
    #first checks if function name is not in the function table
    #it is a lambda call
    #So it retrievs the lambda closure from environement table
    #also if wanna get a function name without any params which is the case where
    #a funciton is assigned to a var, an error is generated for ambiguity 
    #otherwise if the right function called wiht right num_of_params, the closue is returned
    def __get_func_by_name(self, name, num_params):
        if name not in self.func_name_to_ast:
            closure_val_obj = self.env.get(name)
            if closure_val_obj is None:
                return None
            #this prevents if for example an int variable is called as if it's a 
            #lambda closure
            if closure_val_obj.type() != Type.CLOSURE:
                super().error(
                    ErrorType.TYPE_ERROR, "Trying to call function with non-closure"
                )
            closure = closure_val_obj.value()
            num_formal_params = len(closure.func_ast.get("args"))
            if num_formal_params != num_params:
                super().error(ErrorType.TYPE_ERROR, "Invalid # of args to lambda")
            return closure_val_obj.value()
        #here it returns the dict associated to each function name
        #which itself is a dict that maps num of params to a Closure obj 
        candidate_funcs = self.func_name_to_ast[name]
        if num_params is None:
            # case where we want assign variable to func_name and we don't have
            # a way to specify the # of arguments for the function, so we generate
            # an error if there's more than one function with that name
            if len(candidate_funcs) > 1:
                super().error(
                    ErrorType.NAME_ERROR,
                    f"Function {name} has multiple overloaded versions",
                )
            num_args = next(iter(candidate_funcs))
            closure = candidate_funcs[num_args]
            return closure

        if num_params not in candidate_funcs:
            super().error(
                ErrorType.NAME_ERROR,
                f"Function {name} taking {num_params} params not found",
            )
        return candidate_funcs[num_params]
    #runs statements inside each block of code which has its own 
    #scope. Execstatus is for when the block should be continued or not
    def __run_statements(self, statements):
        self.env.push()
        for statement in statements:
            if self.trace_output:
                print(statement)
            status = ExecStatus.CONTINUE
            if statement.elem_type == InterpreterBase.FCALL_DEF:
                self.__call_func(statement)
            elif statement.elem_type == "=":
                self.__assign(statement)
            elif statement.elem_type == InterpreterBase.RETURN_DEF:
                status, return_val = self.__do_return(statement)
            elif statement.elem_type == Interpreter.IF_DEF:
                status, return_val = self.__do_if(statement)
            elif statement.elem_type == Interpreter.WHILE_DEF:
                status, return_val = self.__do_while(statement)
            elif statement.elem_type == Interpreter.MCALL_DEF: 
                self.__eval_mcall(statement)

            if status == ExecStatus.RETURN:
                self.env.pop()
                #pop the environement and return from function. 
                return (status, return_val)

        self.env.pop()
        return (ExecStatus.CONTINUE, Interpreter.NIL_VALUE)


    def __call_func(self, call_ast):
        func_name = call_ast.get("name")
        if func_name == "print":
            return self.__call_print(call_ast)
        if func_name == "inputi":
            return self.__call_input(call_ast)
        if func_name == "inputs":
            return self.__call_input(call_ast)

        # print(call_ast)
        actual_args = call_ast.get("args")
        target_closure = self.__get_func_by_name(func_name, len(actual_args))
        if target_closure == None:
            super().error(ErrorType.NAME_ERROR, f"Function {func_name} not found")
        if target_closure.type != Type.CLOSURE:
            super().error(ErrorType.TYPE_ERROR, f"Function {func_name} is changed to non-function type.")
        target_ast = target_closure.func_ast

        new_env = {}
        self.__prepare_env_with_closed_variables(target_closure, new_env)
        self.__prepare_params(target_ast,call_ast, new_env)
        self.env.push(new_env)
        _, return_val = self.__run_statements(target_ast.get("statements"))
        self.env.pop()
        return return_val

    def __prepare_env_with_closed_variables(self, target_closure, temp_env):
        # print(target_closure.type(), target_closure.value())
        for var_name, value in target_closure.captured_env:

            # Updated here - ignore updates to the scope if we
            #   altered a parameter, or if the argument is a similarly named variable
            temp_env[var_name] = value

    def __prepare_params(self, target_ast, call_ast, temp_env):
        actual_args = call_ast.get("args")
        formal_args = target_ast.get("args")
        if len(actual_args) != len(formal_args):
            super().error(
                ErrorType.NAME_ERROR,
                f"Function {target_ast.get('name')} with {len(actual_args)} args not found",
            )

        for formal_ast, actual_ast in zip(formal_args, actual_args):
            if formal_ast.elem_type == InterpreterBase.REFARG_DEF:
                result = self.__eval_expr(actual_ast)
            else:
                result = copy.deepcopy(self.__eval_expr(actual_ast))
            arg_name = formal_ast.get("name")
            temp_env[arg_name] = result

    def __call_print(self, call_ast):
        output = ""
        for arg in call_ast.get("args"):
            result = self.__eval_expr(arg)  # result is a Value object
            output = output + get_printable(result)
        super().output(output)
        return Interpreter.NIL_VALUE

    def __call_input(self, call_ast):
        args = call_ast.get("args")
        if args is not None and len(args) == 1:
            result = self.__eval_expr(args[0])
            super().output(get_printable(result))
        elif args is not None and len(args) > 1:
            super().error(
                ErrorType.NAME_ERROR, "No inputi() function that takes > 1 parameter"
            )
        inp = super().get_input()
        if call_ast.get("name") == "inputi":
            return Value(Type.INT, int(inp))
        if call_ast.get("name") == "inputs":
            return Value(Type.STRING, inp)

    def __assign(self, assign_ast):
        var_name = assign_ast.get("name")
        # print(self.__eval_expr(assign_ast.get("expression")).type(), 0)
        src_value_obj = copy.copy(self.__eval_expr(assign_ast.get("expression")))
        #in case of assigning to an object's field or method 
        if '.' in var_name:
            obj_var, field_name = var_name.split('.', 1)
            obj_value_obj = self.env.get(obj_var)

            
            if field_name == 'proto':
                # print(src_value_obj.type())
                
                if src_value_obj.type() != Type.OBJECT:
                    # print(src_value_obj.type())
                    
                    if src_value_obj.type() == Type.NIL:
                        obj_value_obj.value().prototype = None
                    else: 
                        super().error(ErrorType.TYPE_ERROR, "Prototype must be an object")
            # print(src_value_obj.value(), 1)
                obj_value_obj.value().prototype = src_value_obj.value()

            if obj_value_obj.type() != Type.OBJECT:
                super().error(ErrorType.TYPE_ERROR, f"{obj_var} is not an object")
            if obj_value_obj is None:
                #later you should follow the prototype chain to get the value, 
                #maybe handle the chain of prototypes and error handlings in 
                #type module? easier 
                super().error(ErrorType.NAME_ERROR, f"{obj_var} is not an object")

            if src_value_obj.type() == Type.CLOSURE:
                #not pointing to a deep or shallow copy of the closure, 
                #rather it directly points to the closure
                closure_of_method = self.__eval_expr(assign_ast.get("expression"))
                # print(closure_of_method.type())
                obj_value_obj.value().add_method(field_name, closure_of_method)
            else: 
                obj_value_obj.value().set_field(field_name, src_value_obj)
        else: 
            target_value_obj = self.env.get(var_name)
            if target_value_obj is None:
                self.env.set(var_name, src_value_obj)
            else:
                # if a close is changed to another type such as int, we cannot make function calls on it any more 
                if target_value_obj.t == Type.CLOSURE and src_value_obj.t != Type.CLOSURE:
                    target_value_obj.v.type = src_value_obj.t
                target_value_obj.set(src_value_obj)

    def __eval_expr(self, expr_ast):
        # print(expr_ast.elem_type, 4)
        if expr_ast.elem_type == InterpreterBase.NIL_DEF:
            # print(Interpreter.NIL_VALUE.type(), "whaat?")
            return Interpreter.NIL_VALUE
        if expr_ast.elem_type == InterpreterBase.INT_DEF:
            return Value(Type.INT, expr_ast.get("val"))
        if expr_ast.elem_type == InterpreterBase.STRING_DEF:
            return Value(Type.STRING, expr_ast.get("val"))
        if expr_ast.elem_type == InterpreterBase.BOOL_DEF:
            return Value(Type.BOOL, expr_ast.get("val"))
        if expr_ast.elem_type == InterpreterBase.VAR_DEF:
            return self.__eval_name(expr_ast)
        if expr_ast.elem_type == InterpreterBase.FCALL_DEF:
            return self.__call_func(expr_ast)
        if expr_ast.elem_type in Interpreter.BIN_OPS:
            return self.__eval_op(expr_ast)
        if expr_ast.elem_type == Interpreter.NEG_DEF:
            return self.__eval_unary(expr_ast, Type.INT, lambda x: -1 * x)
        if expr_ast.elem_type == Interpreter.NOT_DEF:
            return self.__eval_unary(expr_ast, Type.BOOL, lambda x: not x)
        if expr_ast.elem_type == Interpreter.LAMBDA_DEF:
            return Value(Type.CLOSURE, Closure(expr_ast, self.env))
        if expr_ast.elem_type == Interpreter.OBJ_DEF: 
            return Value(Type.OBJECT, ObjectInstance())
        if expr_ast.elem_type == Interpreter.MCALL_DEF: 
            return self.__eval_mcall(expr_ast)
        
    def __eval_mcall(self, mcall_ast): 
        obj_ref = mcall_ast.get('objref')
        obj = self.env.get(obj_ref)
        if obj is None:
            super().error(ErrorType.NAME_ERROR, f"{obj_ref} Does not exist.")
        elif obj.type() != Type.OBJECT: 
            super().error(ErrorType.TYPE_ERROR, f"{obj_ref} is not an object. It's something else.")


        method_name = mcall_ast.get('name')

        method_closure = obj.value().get_method(method_name)

        if method_closure is None: 
            #method name not found now should check if it is a field or what
            if obj.value().get_field(method_name): 
                super().error(ErrorType.TYPE_ERROR, f"{method_name} is not a method. It's a property")
            else: 
                super().error(ErrorType.NAME_ERROR, f"{method_name} is not a method. Does not exist.")



            

        # target_closure = obj.value().get_method(method_name).value()
        # print(method_closure.type(), method_closure.value().func_ast)
        method_closure = method_closure.value() 
        target_ast = method_closure.func_ast
        # evaluated_args = [self.__eval_expr(arg) for arg in mcall_ast.get('args')]

        # actual_args = mcall_ast.get('args')
        new_env = {}
        new_env['this'] = obj
        self.__prepare_env_with_closed_variables(method_closure, new_env)
        self.__prepare_params(target_ast, mcall_ast, new_env)

        # print(method_closure.type(), 1)
        # self.__prepare_env_with_closed_variables(method_closure, new_env)
        # self.__prepare_params(method_closure.func_ast, evaluated_args, new_env)

        self.env.push(new_env)
        _, return_val = self.__run_statements(method_closure.func_ast.get('statements'))
        self.env.pop() 

        return return_val
    

        


        

    #resolves var names either return a pure value or 
    #a closure where the var points to a closure 
    def __eval_name(self, name_ast):
        var_name = name_ast.get("name")
        if '.' in var_name: 
            obj_var, field_name = var_name.split('.', 1)
            obj_value_obj = self.env.get(obj_var)

            if obj_value_obj is None:
                super().error(ErrorType.NAME_ERROR, f"{obj_var} Doesn not exist.")

            if obj_value_obj.type() != Type.OBJECT:
                super().error(ErrorType.TYPE_ERROR, f"{obj_var} is not an object.")

            field_value = obj_value_obj.value().get_field(field_name)

            if field_value == None: 
                if obj_value_obj.value().get_method(field_name) is not None: 
                    super().error(ErrorType.TYPE_ERROR, f"Field {field_name} is not a field but a method")
                else: 
                    super().error(ErrorType.NAME_ERROR, f"Field {field_name} not found in {obj_var}")

            return field_value


        else:
            val = self.env.get(var_name)
            if val is not None:
                return val
            closure = self.__get_func_by_name(var_name, None)
            if closure is None:
                super().error(
                    ErrorType.NAME_ERROR, f"Variable/function {var_name} not found"
                )
            return Value(Type.CLOSURE, closure)

    

    def __eval_op(self, arith_ast):
        left_value_obj = self.__eval_expr(arith_ast.get("op1"))
        right_value_obj = self.__eval_expr(arith_ast.get("op2"))

        left_value_obj, right_value_obj = self.__bin_op_promotion(
            arith_ast.elem_type, left_value_obj, right_value_obj
        )

        if not self.__compatible_types(
            arith_ast.elem_type, left_value_obj, right_value_obj
        ):
            super().error(
                ErrorType.TYPE_ERROR,
                f"Incompatible types for {arith_ast.elem_type} operation",
            )
        if arith_ast.elem_type not in self.op_to_lambda[left_value_obj.type()]:
            super().error(
                ErrorType.TYPE_ERROR,
                f"Incompatible operator {arith_ast.elem_type} for type {left_value_obj.type()}",
            )
        f = self.op_to_lambda[left_value_obj.type()][arith_ast.elem_type]
        return f(left_value_obj, right_value_obj)

    # bool and int, int and bool for and/or/==/!= -> coerce int to bool
    # bool and int, int and bool for arithmetic ops, coerce true to 1, false to 0
    def __bin_op_promotion(self, operation, op1, op2):
        if operation in self.op_to_lambda[Type.BOOL]:  # && or ||
            
            # If this operation is still allowed in the ints, then continue
            if operation in self.op_to_lambda[Type.INT] and op1.type() == Type.INT \
                and op2.type() == Type.INT:
                pass
            else:
                if op1.type() == Type.INT:
                    op1 = Interpreter.__int_to_bool(op1)
                if op2.type() == Type.INT:
                    op2 = Interpreter.__int_to_bool(op2)
        if operation in self.op_to_lambda[Type.INT]:  # +, -, *, /
            if op1.type() == Type.BOOL:
                op1 = Interpreter.__bool_to_int(op1)
            if op2.type() == Type.BOOL:
                op2 = Interpreter.__bool_to_int(op2)
        return (op1, op2)

    def __unary_op_promotion(self, operation, op1):
        if operation == "!" and op1.type() == Type.INT:
            op1 = Interpreter.__int_to_bool(op1)
        return op1
    
    #this is used when no access to class attributes is needed 
    #functions that could also be just a function outside of class. 
    #no self is needed
    @staticmethod
    def __int_to_bool(value):
        return Value(Type.BOOL, value.value() != 0)

    @staticmethod
    def __bool_to_int(value):
        return Value(Type.INT, 1 if value.value() else 0)

    def __compatible_types(self, oper, obj1, obj2):
        # DOCUMENT: allow comparisons ==/!= of anything against anything
        if oper in ["==", "!="]:
            return True
        return obj1.type() == obj2.type()

    def __eval_unary(self, arith_ast, t, f):
        value_obj = self.__eval_expr(arith_ast.get("op1"))
        value_obj = self.__unary_op_promotion(arith_ast.elem_type, value_obj)

        if value_obj.type() != t:
            super().error(
                ErrorType.TYPE_ERROR,
                f"Incompatible type for {arith_ast.elem_type} operation",
            )
        return Value(t, f(value_obj.value()))

    def __setup_ops(self):
        self.op_to_lambda = {}
        # set up operations on integers
        self.op_to_lambda[Type.INT] = {}
        self.op_to_lambda[Type.INT]["+"] = lambda x, y: Value(
            x.type(), x.value() + y.value()
        )
        self.op_to_lambda[Type.INT]["-"] = lambda x, y: Value(
            x.type(), x.value() - y.value()
        )
        self.op_to_lambda[Type.INT]["*"] = lambda x, y: Value(
            x.type(), x.value() * y.value()
        )
        self.op_to_lambda[Type.INT]["/"] = lambda x, y: Value(
            x.type(), x.value() // y.value()
        )
        self.op_to_lambda[Type.INT]["=="] = lambda x, y: Value(
            Type.BOOL, x.value() == y.value()
        )
        self.op_to_lambda[Type.INT]["!="] = lambda x, y: Value(
            Type.BOOL, x.value() != y.value()
        )
        self.op_to_lambda[Type.INT]["<"] = lambda x, y: Value(
            Type.BOOL, x.value() < y.value()
        )
        self.op_to_lambda[Type.INT]["<="] = lambda x, y: Value(
            Type.BOOL, x.value() <= y.value()
        )
        self.op_to_lambda[Type.INT][">"] = lambda x, y: Value(
            Type.BOOL, x.value() > y.value()
        )
        self.op_to_lambda[Type.INT][">="] = lambda x, y: Value(
            Type.BOOL, x.value() >= y.value()
        )
        #  set up operations on strings
        self.op_to_lambda[Type.STRING] = {}
        self.op_to_lambda[Type.STRING]["+"] = lambda x, y: Value(
            x.type(), x.value() + y.value()
        )
        self.op_to_lambda[Type.STRING]["=="] = lambda x, y: Value(
            Type.BOOL, x.value() == y.value()
        )
        self.op_to_lambda[Type.STRING]["!="] = lambda x, y: Value(
            Type.BOOL, x.value() != y.value()
        )
        #  set up operations on bools
        self.op_to_lambda[Type.BOOL] = {}
        self.op_to_lambda[Type.BOOL]["&&"] = lambda x, y: Value(
            x.type(), x.value() and y.value()
        )
        self.op_to_lambda[Type.BOOL]["||"] = lambda x, y: Value(
            x.type(), x.value() or y.value()
        )
        self.op_to_lambda[Type.BOOL]["=="] = lambda x, y: Value(
            Type.BOOL, x.value() == y.value()
        )
        self.op_to_lambda[Type.BOOL]["!="] = lambda x, y: Value(
            Type.BOOL, x.value() != y.value()
        )

        #  set up operations on nil
        self.op_to_lambda[Type.NIL] = {}
        self.op_to_lambda[Type.NIL]["=="] = lambda x, y: Value(
            Type.BOOL, x.value() == y.value()
        )
        self.op_to_lambda[Type.NIL]["!="] = lambda x, y: Value(
            Type.BOOL, x.value() != y.value()
        )

        #  set up operations on closures
        self.op_to_lambda[Type.CLOSURE] = {}
        self.op_to_lambda[Type.CLOSURE]["=="] = lambda x, y: Value(
            Type.BOOL, x.value() == y.value()
        )
        self.op_to_lambda[Type.CLOSURE]["!="] = lambda x, y: Value(
            Type.BOOL, x.value() != y.value()
        )
        #  set up operations on objects: 
        self.op_to_lambda[Type.OBJECT] = {}
        self.op_to_lambda[Type.OBJECT]["=="] = lambda x, y: Value(
            Type.BOOL, id(x.value()) == id(y.value())
        )
        self.op_to_lambda[Type.OBJECT]["!="] = lambda x, y: Value(
            Type.BOOL, id(x.value()) != id(y.value())
        )
    def __do_if(self, if_ast):
        cond_ast = if_ast.get("condition")
        result = self.__eval_expr(cond_ast)
        if result.type() == Type.INT:
            result = Interpreter.__int_to_bool(result)
        if result.type() != Type.BOOL:
            super().error(
                ErrorType.TYPE_ERROR,
                "Incompatible type for if condition",
            )
        if result.value():
            statements = if_ast.get("statements")
            status, return_val = self.__run_statements(statements)
            return (status, return_val)
        else:
            else_statements = if_ast.get("else_statements")
            if else_statements is not None:
                status, return_val = self.__run_statements(else_statements)
                return (status, return_val)

        return (ExecStatus.CONTINUE, Interpreter.NIL_VALUE)

    def __do_while(self, while_ast):
        cond_ast = while_ast.get("condition")
        run_while = Interpreter.TRUE_VALUE
        while run_while.value():
            run_while = self.__eval_expr(cond_ast)
            if run_while.type() == Type.INT:
                run_while = Interpreter.__int_to_bool(run_while)
            if run_while.type() != Type.BOOL:
                super().error(
                    ErrorType.TYPE_ERROR,
                    "Incompatible type for while condition",
                )
            if run_while.value():
                statements = while_ast.get("statements")
                status, return_val = self.__run_statements(statements)
                if status == ExecStatus.RETURN:
                    return status, return_val

        return (ExecStatus.CONTINUE, Interpreter.NIL_VALUE)

    def __do_return(self, return_ast):
        expr_ast = return_ast.get("expression")
        if expr_ast is None:
            return (ExecStatus.RETURN, Interpreter.NIL_VALUE)
        value_obj = copy.deepcopy(self.__eval_expr(expr_ast))
        return (ExecStatus.RETURN, value_obj)
    



program_source = """
func foo(a){
    print("I'm foo" + a);
}
func main() {
    p = 5;
    p.f = 7;
}
"""
# Int_instance = Interpreter() 
# Int_instance.run(program_source)
# print(program_source)
# print(parse_program(program_source))