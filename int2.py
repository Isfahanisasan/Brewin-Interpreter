from intbase import * 
from brewparse import *
from type_valuev1 import *
from env_v1 import *

class Interpreter(InterpreterBase) :

    NIL_VALUE = create_value(InterpreterBase.NIL_DEF)
    BIN_OPS = {"+", "-"}


    def __init__(self, console_output=True, inp=None, trace_output=False):
        super().__init__(console_output, inp)
        self.trace_output = trace_output
        self.setup_ops() 
        # self.variable_name_to_value = {}
    
    def run(self, program):
        #This returns an element.Elemenet instance of the main() functio node
        ast = parse_program(program)  #returns the program node 
        self.set_up_function_table(ast)
        try:
            main_function_ast = self.get_func_by_name('main')
        except NameError: 
            super().error(ErrorType.NAME_ERROR, "No main() function was found")
        self.variable_name_to_value ={}
        self.env = EnvironmentManager()
        self.run_statements(main_function_ast.get('statements'))

    def set_up_function_table(self, ast):
        self.func_name_to_ast = {}
        for func_def in ast.get('functions'):
            self.func_name_to_ast[func_def.get('name')] = func_def

    def get_func_by_name(self, func_name):
        if func_name not in self.func_name_to_ast:
            super.error(ErrorType.NAME_ERROR, f'Function {func_name} not found')
        return self.func_name_to_ast[func_name] #returns func ast


    def run_statements(self, statements): 
        for statement in statements: 
            if self.trace_output:
                print(statement)
            if statement.elem_type == InterpreterBase.FCALL_DEF:
                self.call_func(statement)
            elif statement.elem_type == '=':
                self.assign(statement)
        return Interpreter.NIL_VALUE


    def call_func(self, call_node): 
        func_name = call_node.get('name')
        # args = func_call.get('args') will need later
        if func_name == 'print': 
            return self.call_print(call_node)
        elif func_name == 'inputi':
            return self.call_inputi(call_node)  
        else: 
            # add support for other functions
            super().error(ErrorType.NAME_ERROR)

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
        #support other input types here


    def call_print(self, call_ast):
        output = ""
        for arg in call_ast.get('args'):
            result = self.run_expression(arg)
            output += get_printable(result)
        super().output(output)
        return Interpreter.NIL_VALUE

    def assign(self, assign_ast):
        var_name = assign_ast.get('name')
        value_obj = self.run_expression(assign_ast.get('expression'))
        self.env.set(var_name, value_obj)
        

    def run_expression(self, expression): 
        #recursively calculate the expressions: int-string-fcall-another expression
        #base is int or string
        if expression.elem_type == InterpreterBase.INT_DEF:
            return Value(Type.INT, expression.get('val'))
        if expression.elem_type == InterpreterBase.STRING_DEF:
            return Value(Type.STRING, expression.get('val'))
        if expression.elem_type == InterpreterBase.VAR_DEF:
            var_name = expression.get('name')
            val = self.env.get(var_name)
            if val is None: 
                super().error(ErrorType.NAME_ERROR, f'Variable {var_name} not found')
            return val 
        if expression.elem_type == InterpreterBase.FCALL_DEF:
            return self.call_func(expression)
        if expression.elem_type == Interpreter.BIN_OPS:
            return self.eval_op(expression)
        
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
        #constructing a value with type of left handside 
        self.op_to_lambda[Type.INT]['+']= lambda x, y: Value(
            x.type(), x.value() + y.value()
        )
        self.op_to_lambda[Type.INT]['-']= lambda x, y: Value(
            x.type(), x.value() - y.value()
        )



    # def run_main_node(self, func_node): 
    #     func_statements = func_node.get('statements')
    #     for statement_node in func_statements:
    #         # print(statement_node)
    #         self.run_statement(statement_node)
    # output = ''

    # # func_name = func_call.get('name')
    # args = call_to_print.get('args')
    # for arg in args: 
    #     # print(arg)
    #     if arg.elem_type == 'string':
    #         output += arg.get('val')
    #     elif arg.elem_type == 'int':
    #         output += str(arg.get('val'))
    #     elif arg.elem_type == 'bool':
    #         if arg.get('val'):
    #             output += 'true'
    #         else: 
    #             output += 'false'
    #     elif arg.elem_type == '!':
    #         negated_value = self.run_expression(arg)
    #         if negated_value:
    #             output += 'true'
    #         else: 
    #             output += 'false'
    #     # elif arg.elem_type == 'nil': if you wanna add a case for nil
    #     elif arg.elem_type == 'var':
    #         variable_name = arg.get('name')
    #         if variable_name in self.variable_name_to_value:
    #             output += str(self.variable_name_to_value[variable_name])   
    #         else: 
    #             #variable to print is not defined 
    #             super().error(ErrorType.NAME_ERROR, f"Unknown variable {variable_name}")
    #     elif arg.elem_type in ('+', '-', 'neg'):
    #         output += str(self.run_expression(arg))
    # super().output(output)

            
    #old run_expression
    # if expression.elem_type in ('int', 'string', 'bool'):
    #     return expression.get('val')
    # elif expression.elem_type == 'var':
    #     var_name = expression.get('name')
    #     if var_name in self.variable_name_to_value:
    #         return self.variable_name_to_value[var_name]
    #     else:
    #         #the variable is not defined
    #         super().error(ErrorType.NAME_ERROR, f"Unknown variable {var_name}")
    # elif expression.elem_type == '+':
    #     operator1 = expression.get('op1')
    #     operator2 = expression.get('op2')
    #     op1_value = self.run_expression(operator1)
    #     op2_value = self.run_expression(operator2)
    #     if isinstance(op1_value, str) or isinstance(op2_value, str):
    #         super().error(ErrorType.TYPE_ERROR, "Incompatible types for arithmetic operation")
    #     return op1_value + op2_value
    # elif expression.elem_type == '-':
    #     operator1 = expression.get('op1')
    #     operator2 = expression.get('op2')
    #     op1_value = self.run_expression(operator1)
    #     op2_value = self.run_expression(operator2)
    #     if isinstance(op1_value, str) or isinstance(op2_value, str):
    #         super().error(ErrorType.TYPE_ERROR, "Incompatible types for arithmetic operation")
    #     return op1_value - op2_value
    # elif expression.elem_type == 'neg':
    #     return (-1) * self.run_expression(expression.get('op1'))
    # elif expression.elem_type == '!':
    #     return not self.run_expression(expression.get('op1'))   
    # elif expression.elem_type == 'fcall':
    #     return self.call_func(expression)
    # else:
    #     super().error(ErrorType.NAME_ERROR, "Invalid expression")

    #old run statement 
    # if statement_node.elem_type == 'fcall':
    #     #do the function call 
    #     self.call_func(statement_node)
    # elif statement_node.elem_type == '=':
    #     right_hand_side = statement_node.get('expression')
    #     left_hand_side_name = statement_node.get('name')
    #     self.variable_name_to_value[left_hand_side_name] = self.run_expression(right_hand_side)
                 
    

# program_source = """
# func main(){
#     print("hi");

# }
# """

# Int_instance = Interpreter() 
# Int_instance.run(program_source)


# ast = parse_program(program_source)
# print(ast)

