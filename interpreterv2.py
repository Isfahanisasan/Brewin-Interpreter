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

        self.env = EnvironmentManager()
        self.env.open_scope #opening a global scope
        self.set_up_function_table(ast)


        try:
            main_function_ast = self.get_func_by_name('main', 0)
        except NameError: 
            super().error(ErrorType.NAME_ERROR, "No main() function was found")

        self.env.open_scope #open the scope for main 
        self.run_statements(main_function_ast.get('statements'))
        self.env.close_scope() #closing scope of main 

        self.env.close_scope()# closing the global scope

    def set_up_function_table(self, ast):
        self.func_name_to_ast = {}
        for func_def in ast.get('functions'):
            func_name = func_def.get('name')
            num_args = len(func_def.get('args'))
            #while setting up the function table, also store the functions as variables in global scope
            self.func_name_to_ast[(func_name, num_args)] = func_def
            self.env.set(func_name, (num_args, func_def))

    def get_func_by_name(self, func_name, num_args):
        #first check if the fucntion exists as an object in scope
        if ((func_name, num_args) not in self.func_name_to_ast): #function call is not found in function table
            try:  #trying lambda or an obj that has func value
                func_or_lambda_obj = self.env.get(func_name) 
                if type(func_or_lambda_obj) is dict: #this is when a lambda is being executed
                    lambda_dict = func_or_lambda_obj
                    lambda_node = lambda_dict['lambda_expression']
                    num_of_lambda_args = len(lambda_node.get('args'))
                    if num_of_lambda_args != num_args:
                        super().error(ErrorType.TYPE_ERROR, f'Lambda {func_name} called with wrong number of parameters')
                    return func_or_lambda_obj
                else: 
                    func_tuple = func_or_lambda_obj
                # func_tuple = func_or_lambda_obj
                if func_tuple[0] != num_args: #now check if function is in scope as an object
                    super().error(ErrorType.TYPE_ERROR, f'Function {func_name} called with wrong number of parameters')
                else: 
                    return func_tuple[1]    
            except NameError: 
                super().error(ErrorType.NAME_ERROR, f'Function {func_name} not found or wrong number of parameters')
            except TypeError:
                super().error(ErrorType.TYPE_ERROR, f'Function {func_name} not a function')


        return self.func_name_to_ast[(func_name, num_args)] #returns func ast

    def execute_lambda(self, lambda_dict, call_node):
        self.env.replace_with_captured(lambda_dict['captured_scope'])
        self.env.open_scope()
        call_node_args = call_node.get('args') 
        lambda_node = lambda_dict['lambda_expression']
        lambda_args = lambda_node.get('args')
        ref_dict = {}
        arg_dict = {lambda_args[i].get('name') : deepcopy(self.run_expression(call_node_args[i])) for i in range(len(lambda_args))}
        #check if param passed to lambda is not an overloaded func 
        for value in arg_dict.values(): 
            if value.type() == Type.Func:
                func_name = value.value()[1].get('name')
                if self.is_overloaded(func_name): 
                    super().error(ErrorType.NAME_ERROR, f'Function {func_name} is overloaded and cannot be passed as a param to a lambda')
        self.env.set_func_args_refs(arg_dict, ref_dict)
        statements = lambda_node.get('statements')
        return_value = self.run_statements(statements)
        # breakpoint()
        self.env.close_scope()
        self.env.replace_with_original()
        return return_value
        

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
        if type(func_ast) is dict: #if a lambda is being executed
            return self.execute_lambda(func_ast, call_node)
        arg_dict = {}
        ref_dict = {}
        func_ast_args = func_ast.get('args')
        
        for i,func_arg in enumerate(func_ast_args):
            #when a literal is passed to an argref it's as if it was a 
            if func_arg.elem_type == InterpreterBase.ARG_DEF or call_node_args[i].elem_type != InterpreterBase.VAR_DEF:
                arg_dict[func_arg.get('name')] = deepcopy(self.run_expression(call_node_args[i]))
            elif func_arg.elem_type == InterpreterBase.REFARG_DEF: 
                ref_dict[func_arg.get('name')] = call_node_args[i]

        # arg_dict = {func_ast_args[i].get('name') : deepcopy(self.run_expression(call_node_args[i])) for i in range(len(func_ast_args))}
        # print(arg_dict['x'].value())
        #check if the passed param is not an overloaded funciton 
        for value in arg_dict.values(): 
            if value.type() == Type.Func:
                func_name = value.value()[1].get('name')
                if self.is_overloaded(func_name): 
                    super().error(ErrorType.NAME_ERROR, f'Function {func_name} is overloaded and cannot be passed as a param to a function')

        self.env.set_func_args_refs(arg_dict, ref_dict)
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
        # print(assign_ast)
        value_obj = self.run_expression(assign_ast.get('expression'))
        if value_obj.type() == Type.Func: #checking if overloaded cannot be assigned
            if self.is_overloaded(value_obj.value()[1].get('name')): 
                super().error(ErrorType.NAME_ERROR, f'Function {value_obj.value()[1].get("name")} is overloaded and cannot be assigned')
        self.env.set(var_name, value_obj.value())

    def is_overloaded(self, func_name):
        # first_elements = [key[0] for key in my_dict.keys()
        # func_name = func_node.value()[1].get('name')
        function_names = [key[0] for key in self.func_name_to_ast.keys()]
        return function_names.count(func_name) > 1

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
        if expression.elem_type == Interpreter.LAMBDA_DEF:
            lambda_obj = self.create_lambda(expression)
            return lambda_obj

    def create_lambda(self, lambda_node):
        captured_scope = deepcopy(self.env.environment_stack)
        lambda_obj = {'lambda_expression': lambda_node ,'captured_scope': captured_scope}
        return Value(Type.Lambda, lambda_obj)

    def eval_bool(self, bool_ast):
        left_value_obj = self.run_expression(bool_ast.get('op1'))
        right_value_obj = self.run_expression(bool_ast.get('op2'))
        #nil == nil
        if(right_value_obj.type() == Type.NIL and left_value_obj.type() == Type.NIL):
            return Value(Type.BOOL, bool_ast.elem_type == '==')
        #Comparing different types and incompatible types
        if left_value_obj.type() != right_value_obj.type():
            if(left_value_obj.type() == Type.NIL or right_value_obj.type() == Type.NIL):
                return Value(Type.BOOL, bool_ast.elem_type != '==')
            if(bool_ast.elem_type in ['==', '!=']):
                return Value(Type.BOOL, bool_ast.elem_type != '==')
            else: 
                super().error(
                    ErrorType.TYPE_ERROR, 
                    f'Incompatible types for {bool_ast.elem_type} operation')
        #using types with incompatible operations 
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
        self.bool_to_lambda[Type.Func] = {}
        self.bool_to_lambda[Type.Lambda] = {}


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
        self.bool_to_lambda[Type.Func]['=='] = lambda x, y: Value(
            Type.BOOL, x.value() == y.value()
        )
        self.bool_to_lambda[Type.Func]['!='] = lambda x, y: Value(
            Type.BOOL, x.value() != y.value()
        )
        self.bool_to_lambda[Type.Lambda]['=='] = lambda x, y: Value(
            Type.BOOL, x.value() == y.value()
        )
        self.bool_to_lambda[Type.Lambda]['!='] = lambda x, y: Value(
            Type.BOOL, x.value() != y.value()
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
        print(right_value_obj.type())
        print(left_value_obj.type())
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
func foo(ref x, delta) { /* x passed by reference, delta passed by value */
x = x + delta;
delta = 0;
}
func main() {
a = 10;
delta = 1;
foo(a, delta);
print(a); /* prints 11 */
print(delta); /* prints 1 */
}

"""
 
# Int_instance = Interpreter() 
# Int_instance.run(program_source)
# print(parse_program(program_source))


