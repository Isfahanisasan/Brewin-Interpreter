from intbase import ErrorType
from copy import deepcopy
from brewparse import *
from type_valuev2 import *
from env_v2 import *

class Interpreter(InterpreterBase) :

    NIL_VALUE = create_value(InterpreterBase.NIL_DEF)
    BIN_OPS = {'+', '-', '*', '/'}
    BOOL_OPS = {'==', '<', '<=', '>', '>=', '!=', '&&', '||'}
    MAX_ITERATION = 200

    def __init__(self, console_output=True, inp=None, trace_output=False):

        super().__init__(console_output, inp)
        self.trace_output = trace_output
        self.setup_ops() 
        self.setup_bools()

    def run(self, program):
 
        ast = parse_program(program)  #returns the program node 
        self.set_up_function_table(ast)
        try:
            main_function_ast = self.get_func_by_name('main', 0)
        except NameError: 
            super().error(ErrorType.NAME_ERROR, "No main() function was found")
        self.env = EnvironmentManager()
        self.run_statements(main_function_ast.get('statements'))
  

    def set_up_function_table(self, ast):

        self.func_name_to_ast = {}
        for func_def in ast.get('functions'):
            func_name = func_def.get('name')
            num_args = len(func_def.get('args'))
            self.func_name_to_ast[(func_name, num_args)] = func_def

    def get_func_by_name(self, func_name, num_args):

        if (func_name, num_args) not in self.func_name_to_ast:
            super().error(ErrorType.NAME_ERROR, f'Function {func_name} not found or wrong number of parameters')
        return self.func_name_to_ast[(func_name, num_args)] #returns func ast

    def run_statements(self, statements): 

        return_value = Interpreter.NIL_VALUE
        for statement in statements: 
            # print(statement)
            if self.trace_output:
                print(statement)
            if statement.elem_type == InterpreterBase.FCALL_DEF:
                return_value = self.call_func(statement)
            elif statement.elem_type == '=':
                self.assign(statement)
            elif statement.elem_type == InterpreterBase.RETURN_DEF:
                return_value = self.return_statement(statement)
                return return_value
            elif statement.elem_type == InterpreterBase.IF_DEF:
                return_value = self.eval_if(statement)
                if return_value is not Interpreter.NIL_VALUE:
                    break
            elif statement.elem_type == InterpreterBase.WHILE_DEF:
                return_value = self.eval_while(statement)
        return return_value

    def eval_if(self, if_ast):
        return_value = Interpreter.NIL_VALUE
        condition = self.run_expression(if_ast.get('condition'))
    
        if condition.type() != Type.BOOL:
            super().error(ErrorType.TYPE_ERROR, f'condition must be a boolean.')
        if condition.value():
            self.env.open_scope()
            return_value = self.run_statements(if_ast.get('statements'))
            self.env.close_scope()
        else:
            if if_ast.get('else_statements') is not None:   
                self.env.open_scope()
                return_value = self.run_statements(if_ast.get('else_statements'))
                self.env.close_scope()

        return return_value
    
    def eval_while(self, while_ast):

        return_value = Interpreter.NIL_VALUE
        condition_ast = while_ast.get('condition')
        condition_obj = self.run_expression(condition_ast)
        if condition_obj.type() != Type.BOOL:
            super().error(ErrorType.TYPE_ERROR, f'condition must be a boolean.')
    
        self.iteration_count = 0
        runs_at_least_once = False

        if(condition_obj.value()):
            self.env.open_scope()
            runs_at_least_once = True 
        
        while True:
            condition_obj = self.run_expression(condition_ast)
            if not condition_obj.value():
                break 
            return_value = self.run_statements(while_ast.get('statements'))
            if return_value is not Interpreter.NIL_VALUE:  
                break

        if(runs_at_least_once):
            self.env.close_scope()
        return return_value


    def return_statement(self, statement):

        return_expression = statement.get('expression')
        if return_expression is None: 
            value_to_return = Interpreter.NIL_VALUE
        else:           
            value_to_return = self.run_expression(statement.get('expression'))
        return deepcopy(value_to_return)
    
        
    def call_func(self, call_node): 
        func_name = call_node.get('name')
  
        if func_name == 'print': 
            return self.call_print(call_node)
        elif func_name == 'inputi':
            return self.call_inputi(call_node)  
        elif func_name == 'inputs':
            return self.call_inputs(call_node)
        else: 
            return self.user_func(call_node)

    def user_func(self, call_node):
        num_args = 0
        self.env.open_scope()
        call_node_args = call_node.get('args') 
        if call_node_args:
            num_args = len(call_node_args)
        
        func_ast = self.get_func_by_name(call_node.get('name'), num_args)

        func_ast_args = func_ast.get('args')
        if(len(call_node_args) != len(func_ast_args)):
            super().error(ErrorType.NAME_ERROR, f"function {call_node.get('name')} called with wrong number of arguments.")

        arg_dict = {func_ast_args[i].get('name') : deepcopy(self.run_expression(call_node_args[i])) for i in range(len(func_ast_args))}
        self.env.set_func_argument(arg_dict)
        statements = func_ast.get('statements')
        return_value = self.run_statements(statements)

        self.env.close_scope()
        return return_value
    
    def call_inputs(self, call_ast):
        return self.call_inputi(call_ast)


    def call_inputi(self, call_ast):
        args = call_ast.get('args')
        if len(args) > 1:
            super().error(ErrorType.NAME_ERROR, "No inputi() function that takes > 1 parameter")
        if args is not None and len(args) == 1:
            result = self.run_expression(args[0])
            super().output(get_printable(result))
        user_input = super().get_input()
        if call_ast.get('name') == 'inputi':
            return Value(Type.INT, int(user_input))
        elif call_ast.get('name') == 'inputs':
            return Value(Type.STRING, str(user_input))

    def call_print(self, call_ast):
        output = ""
        for arg in call_ast.get('args'):
            result = self.run_expression(arg)
            output = output + get_printable(result)
        super().output(output)
        return Interpreter.NIL_VALUE

    def assign(self, assign_ast):
        var_name = assign_ast.get('name')
        value_obj = self.run_expression(assign_ast.get('expression'))
        self.env.set(var_name, value_obj.value())
        
    def run_expression(self, expression): 

        if expression.elem_type == InterpreterBase.INT_DEF:
            return Value(Type.INT, expression.get('val'))
        if expression.elem_type == InterpreterBase.STRING_DEF:
            return Value(Type.STRING, expression.get('val'))
        if expression.elem_type == InterpreterBase.BOOL_DEF:
            return Value(Type.BOOL, expression.get('val'))
        if expression.elem_type == InterpreterBase.NIL_DEF:
            return Interpreter.NIL_VALUE
        if expression.elem_type == InterpreterBase.VAR_DEF:
            var_name = expression.get('name')
            try:
                val = self.env.get(var_name)
            except: 
                super().error(ErrorType.NAME_ERROR, f'variable {var_name} not found')
            value_obj = create_value(val)
            return value_obj
        if expression.elem_type == InterpreterBase.FCALL_DEF:
            return self.call_func(expression)
        if expression.elem_type in Interpreter.BIN_OPS:
            return self.eval_op(expression)
        if expression.elem_type == InterpreterBase.NOT_DEF:
            return self.bool_negation(expression)
        if expression.elem_type == InterpreterBase.NEG_DEF:
            return self.num_neg(expression)
        if expression.elem_type in Interpreter.BOOL_OPS:
            return self.eval_bool(expression)
        

    def eval_bool(self, bool_ast):
        left_value_obj = self.run_expression(bool_ast.get('op1'))
        right_value_obj = self.run_expression(bool_ast.get('op2'))
        if(right_value_obj.type() == Type.NIL and left_value_obj.type() == Type.NIL):
            return Value(Type.BOOL, bool_ast.elem_type == '==')

        if left_value_obj.type() != right_value_obj.type():
            if(left_value_obj.type() == Type.NIL or right_value_obj.type() == Type.NIL):
                return Value(Type.BOOL, bool_ast.elem_type != '==')
            if(bool_ast.elem_type in ['==', '!=']):
                return Value(Type.BOOL, bool_ast.elem_type != '==')
            else: 
                super().error(
                    ErrorType.TYPE_ERROR, 
                    f'Incompatible types for {bool_ast.elem_type} operation')

        if bool_ast.elem_type not in self.bool_to_lambda[left_value_obj.type()]:
                super().error(
                    ErrorType.TYPE_ERROR, 
                    f'Incompatible types for {bool_ast.elem_type} operation')
                
        f = self.bool_to_lambda[left_value_obj.type()][bool_ast.elem_type]
        return f(left_value_obj, right_value_obj)

    def setup_bools(self):
        self.bool_to_lambda = {}
        self.bool_to_lambda[Type.INT] = {}
        self.bool_to_lambda[Type.STRING] = {}
        self.bool_to_lambda[Type.BOOL] = {}

        self.bool_to_lambda[Type.INT]['==']= lambda x, y: Value(
            Type.BOOL, x.value() == y.value()
        )
        self.bool_to_lambda[Type.INT]['<']= lambda x, y: Value(
            Type.BOOL, x.value() < y.value()
        )
        self.bool_to_lambda[Type.INT]['<=']= lambda x, y: Value(
            Type.BOOL, x.value() <= y.value()
        )
        self.bool_to_lambda[Type.INT]['>'] = lambda x, y: Value(
            Type.BOOL, x.value() > y.value()
        )
        self.bool_to_lambda[Type.INT]['>='] = lambda x, y: Value(
            Type.BOOL, x.value() >= y.value()
        )
        self.bool_to_lambda[Type.INT]['!='] = lambda x, y: Value(
            Type.BOOL, x.value() != y.value()
        )
        self.bool_to_lambda[Type.STRING]['=='] = lambda x, y: Value(
            Type.BOOL, x.value() == y.value()
        )
        self.bool_to_lambda[Type.STRING]['!='] = lambda x, y: Value(
            Type.BOOL, x.value() != y.value()
        )
        self.bool_to_lambda[Type.BOOL]['=='] = lambda x, y: Value(
            Type.BOOL, x.value() == y.value()
        )
        self.bool_to_lambda[Type.BOOL]['!='] = lambda x, y: Value(
            Type.BOOL, x.value() != y.value()
        )
        self.bool_to_lambda[Type.BOOL]['&&'] = lambda x, y: Value(
            Type.BOOL, x.value() and y.value()
        )
        self.bool_to_lambda[Type.BOOL]['||'] = lambda x, y: Value(
            Type.BOOL, x.value() or y.value()
        )

    def num_neg(self, expression):
        right_hand_side = self.run_expression(expression.get('op1'))

        if(right_hand_side.type() != Type.INT):
            super().error(ErrorType.TYPE_ERROR, f'negation of non numerical')
        return Value(Type.INT, -1 * right_hand_side.value())
    
    def bool_negation(self, expression):
        right_hand_side = self.run_expression(expression.get('op1'))
        if(right_hand_side.type() != Type.BOOL):
            super().error(ErrorType.TYPE_ERROR, 'logical not used with non bool')
        return Value(Type.BOOL, not right_hand_side.value())
        
    def eval_op(self, arith_ast):
        left_value_obj = self.run_expression(arith_ast.get('op1'))
        right_value_obj = self.run_expression(arith_ast.get('op2'))
        if left_value_obj.type() != right_value_obj.type():
            super().error(
                ErrorType.TYPE_ERROR, 
                f'Incompatible types for {arith_ast.elem_type} operation')
        if arith_ast.elem_type not in self.op_to_lambda[left_value_obj.type()]:
            super().error(
                ErrorType.TYPE_ERROR, f'Incompatible operator {arith_ast.get_type} for type {left_value_obj.type()}')
        
        f = self.op_to_lambda[left_value_obj.type()][arith_ast.elem_type]
        return f(left_value_obj, right_value_obj)

    def setup_ops(self):
        self.op_to_lambda = {}
        self.op_to_lambda[Type.INT] = {}
        self.op_to_lambda[Type.STRING] = {}

        self.op_to_lambda[Type.INT]['+']= lambda x, y: Value(
            x.type(), x.value() + y.value()
        )
        self.op_to_lambda[Type.INT]['-']= lambda x, y: Value(
            x.type(), x.value() - y.value()
        )
        self.op_to_lambda[Type.INT]['*']= lambda x, y: Value(
            x.type(), x.value() * y.value()
        )
        self.op_to_lambda[Type.INT]['/'] = lambda x, y: Value(
            x.type(), x.value() // y.value()
        )
        self.op_to_lambda[Type.STRING]['+'] = lambda x, y: Value(
            x.type(), x.value() + y.value()
        )
    

program_source = """

"""
 
# Int_instance = Interpreter() 
# Int_instance.run(program_source)


