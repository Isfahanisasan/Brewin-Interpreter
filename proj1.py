from intbase import * 
from brewparse import *

class Interpreter(InterpreterBase) :
    def __init__(self, console_output=True, inp=None, trace_output=False):
        super().__init__(console_output, inp)
        self.trace_output = trace_output
        self.variable_name_to_value = {}
    
    def run(self, program):
        #This returns an element.Elemenet instance of the main() functio node
        ast = parse_program(program)  #returns the program node 
        list_of_program_functions = ast.get('functions')
        main_function = list_of_program_functions[0]
        if main_function.get('name') != 'main':
            super().error(ErrorType.NAME_ERROR, "No main() function was found")
        self.variable_name_to_value ={}
        self.run_main_node(main_function)

    def run_main_node(self, func_node): 
        func_statements = func_node.get('statements')
        for statement_node in func_statements:
            # print(statement_node)
            self.run_statement(statement_node)

    def run_func_call(self, func_call): 
        #consider having separate print and inputi functions in the class
        func_name = func_call.get('name')
        args = func_call.get('args')
        # print(func_call)
        if func_name == 'print': 
            output = ''
            for arg in args: 
                if arg.elem_type == 'string':
                    output += arg.get('val')
                elif arg.elem_type == 'int':
                    output += str(arg.get('val'))
                elif arg.elem_type == 'var':
                    variable_name = arg.get('name')
                    if variable_name in self.variable_name_to_value:
                        output += str(self.variable_name_to_value[variable_name])   
                    else: 
                        #variable to print is not defined 
                        super().error(ErrorType.NAME_ERROR, f"Unknown variable {variable_name}")
                elif arg.elem_type == '+' or arg.elem_type == '-':
                    output += str(self.run_expression(arg))
            super().output(output)
        elif func_name == 'inputi':
            if len(func_call.get('args')) > 1:
                super().error(ErrorType.NAME_ERROR)
            if len(func_call.get('args')) == 1:
                super().output(func_call.get('args')[0].get('val'))
            user_input = super().get_input()
            try:
                return int(user_input)
            except ValueError:
                return user_input
            
        else: 
            super().error(ErrorType.NAME_ERROR)

    def run_expression(self, expression): 
        #recursively calculate the expressions: int-string-fcall-another expression
        #base is int or string
        if expression.elem_type == 'int' or expression.elem_type == 'string':
            return expression.get('val')
        elif expression.elem_type == 'var':
            var_name = expression.get('name')
            if var_name in self.variable_name_to_value:
                return self.variable_name_to_value[var_name]
            else:
                #the variable is not defined
                super().error(ErrorType.NAME_ERROR, f"Unknown variable {var_name}")
        elif expression.elem_type == '+':
            operator1 = expression.get('op1')
            operator2 = expression.get('op2')
            op1_value = self.run_expression(operator1)
            op2_value = self.run_expression(operator2)
            if isinstance(op1_value, str) or isinstance(op2_value, str):
                super().error(ErrorType.TYPE_ERROR, "Incompatible types for arithmetic operation")
            return op1_value + op2_value
        elif expression.elem_type == '-':
            operator1 = expression.get('op1')
            operator2 = expression.get('op2')
            op1_value = self.run_expression(operator1)
            op2_value = self.run_expression(operator2)
            if isinstance(op1_value, str) or isinstance(op2_value, str):
                super().error(ErrorType.TYPE_ERROR, "Incompatible types for arithmetic operation")
            return op1_value - op2_value
        elif expression.elem_type == 'fcall':
            return self.run_func_call(expression)
        else:
            super().error(ErrorType.NAME_ERROR, "Invalid expression")

    def run_statement(self, statement_node): 
        if statement_node.elem_type == 'fcall':
            #do the function call 
            self.run_func_call(statement_node)
        elif statement_node.elem_type == '=':
            right_hand_side = statement_node.get('expression')
            left_hand_side_name = statement_node.get('name')
            self.variable_name_to_value[left_hand_side_name] = self.run_expression(right_hand_side)

                 
    

program_source = """func main(){
    x = 4 + inputi("enter a num");
    print(x); 
}
"""

# Int_instance = Interpreter() 
# Int_instance.run(program_source)


