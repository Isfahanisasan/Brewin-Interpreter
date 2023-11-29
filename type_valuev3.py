import copy

from enum import Enum
from intbase import InterpreterBase


# Enumerated type for our different language data types
class Type(Enum):
    INT = 1
    BOOL = 2
    STRING = 3
    CLOSURE = 4
    NIL = 5
    OBJECT = 6


class Closure:
    def __init__(self, func_ast, env):
        self.captured_env = copy.deepcopy(env)
        self.func_ast = func_ast
        self.type = Type.CLOSURE

        # Replace objects in the captured environment with references to the original objects
        for layer_index, layer in enumerate(env.environment):
            # Iterate over each item in the layer
            for key, value in layer.items():
                # Replace ObjectInstance in the copied layer with a reference to the original object
                if value.type() == Type.OBJECT or value.type() == Type.CLOSURE:
                    self.captured_env.environment[layer_index][key] = value

class ObjectInstance:
    def __init__(self, prototype=None):
        self.fields = {}
        self.methods = {}
        self.type = Type.OBJECT
        self.prototype = prototype
    
    def set_field(self, name, value): 
        self.fields[name] = value
    
    def add_method(self, func_name, func_closure): 
        self.methods[func_name] = func_closure
        # print(self.methods['f'].type())

    def get_field(self, field_name):
        #if not found returns none 
        # return self.fields.get(field_name, None)
        value = self.fields.get(field_name, None)
        
        if value is None and self.prototype:
            return self.prototype.get_field(field_name)
        return value
    
    def get_method(self, method_name):
        # try:
        #     return self.methods[method_name]
        # except:
        #     raise KeyError
        # return self.methods.get(method_name, None)
            
        method = self.methods.get(method_name, None)
        if method is not None:
            return method
        
        if method_name in self.fields: 
            return None
        # print(self.prototype)
        if method is None and self.prototype:
            return self.prototype.get_method(method_name)
        return method

# Represents a value, which has a type and its value
class Value:
    def __init__(self, t, v=None):
        self.t = t
        self.v = v

    def value(self):
        return self.v

    def type(self):
        return self.t

    def set(self, other):
        self.t = other.t
        self.v = other.v


def create_value(val):
    if val == InterpreterBase.TRUE_DEF:
        return Value(Type.BOOL, True)
    elif val == InterpreterBase.FALSE_DEF:
        return Value(Type.BOOL, False)
    elif val == InterpreterBase.NIL_DEF:
        return Value(Type.NIL, None)
    elif isinstance(val, str):
        return Value(Type.STRING, val)
    elif isinstance(val, int):
        return Value(Type.INT, val)

    else:
        raise ValueError("Unknown value type")


def get_printable(val):
    if val.type() == Type.INT:
        return str(val.value())
    if val.type() == Type.STRING:
        return val.value()
    if val.type() == Type.BOOL:
        if val.value() is True:
            return "true"
        return "false"
    return None