"""This module builds Abstract Syntax Trees for Quake QC source files.

Example:
    with open('myprog.qc') as source_file:
        ast = qc.parse(source_file)

References:
    Quake Documentation Version 3.4
    - Olivier Montanuy, et al.
    - http://www.gamers.org/dEngine/quake/spec/quake-spec34/qc-menu.htm
"""

import re

class ParseError(Exception):
    def __init__(self, message, location):
        super().__init__(message + ' line {0}, column {1}'.format(location[0], location[1]))
        self.location = location

def parse(program):
    token = None

    def expression(rbp=0):
        """Constructs an expression

        Args:
            rpb: The right binding power

        Returns:
            An AST representing the expression
        """

        nonlocal token
        t = token
        advance()
        left = t.nud()

        while rbp < token.lbp:
            t = token
            advance()
            left = t.led(left)

        return left

    def tokenize(program):
        """Transforms the program into a sequence of Symbols.

        Args:
            program: The program to be tokenized as a string.

        Yields:
            A Symbol
        """
        token_pattern = re.compile('\s*(?:(float|void|vector|entity|string)|([a-zA-Z_][a-zA-Z0-9_]{0,31})|(\d+)|(.))')

        for type, name, number, operator in token_pattern.findall(program):
            if type:
                symbol = symbol_table['(type)']
                s = symbol()
                s.value = type
                s.type = 'type'

            elif name:
                symbol = symbol_table['(literal)']
                s = symbol()
                s.value = name
                s.type = 'name'

                yield s

            elif number:
                symbol = symbol_table['(literal)']
                s = symbol()
                s.value = number
                s.type = 'number'

                yield s

            else:
                symbol = symbol_table.get(operator)
                s = symbol()
                s.type = 'operator'

                if not symbol_table:
                    raise

                yield s

        yield symbol_table['(end)']

    class Symbol(object):
        """Base class used to construct all symbols.

        Attributes:
            id:

            value:

            first:

            second:

            third:
        """

        id = None
        value = None
        first = second = third = None

        def nud(self):
            """Null denotation. Does not care about tokens to the left.
            Typically used by values and prefix operators.
            """

            raise NotImplementedError

        def led(self, left):
            """Left denotation. Does care about tokens to the left. Typically
            used by infix and suffix operators.

            Args:
                left: The left operand.
            """

            raise NotImplementedError

        def __repr__(self):
            if self.id == "(name)" or self.id == "(literal)":
                return "(%s %s)" % (self.id[1:-1], self.value)

            out = [self.id, self.first, self.second, self.third]
            out = map(str, filter(None, out))
            return "(" + " ".join(out) + ")"

    # A table for holding all of the defined symbols.
    symbol_table = {}

    def symbol(id, bp=0):
        """Creates and returns a subclass of Symbol

        Will define a class deriving from Symbol based off of the given
        identifier and binding power. If the derived class already exists in
        the symbol table, it will simply be returned.

        Args:
            id: The symbol's identifier

            bp: The symbol's left binding power

        Returns:
            The subclass created
        """

        try:
            s = symbol_table[id]

        except KeyError:
            class s(Symbol):
                pass

            s.__name__ = 'symbol-{0}'.format(id)
            s.id = id
            s.lbp = bp
            symbol_table[id] = s

        else:
            s.lbp = max(bp, s.lbp)

        return s

    def advance(id=None):
        """Verifies the current token(if id_or_class is given) and proceeds
        to the next token.

        Args:
            id: Optional. A string to compare the current against.

        Returns:
            The previous token

        Raises:
            ParseError: If expected symbol is not found.
        """

        nonlocal token
        token = next()

        if id:
            expect(id)

        if token == symbol_table['(end)']:
            return

        if token.type == 'number':
            token.arity = 'literal'

        else:
            token.arity = token.type

        #previous = token

        return token

    def expect(id):
        """Verifies current token, raises if not equal to the given id_or_class

        Args:
            id: The string id to compare against

        Raises:
            ParseError: If expected symbol is not found
        """

        nonlocal token
        error_message = 'Expected "{0}" got "{1}"'

        if id and id != token.id:
            error(error_message.format(id, token.id))

    def error(message):
        """Raises an exception with the given message. Also provides the
        row and column information as to where the error occurred.

        Attributes:
            message: The exception message

        Raises:
            ParseError
        """

        #nonlocal line, column
        #location = ' line {0}, column {1}'.format(line, column)
        location = 0, 0 #line, column

        raise ParseError(message, location)


    def infix(id, bp):
        """Helper function for defining infix operators

        Args:
            id: The symbol identifier

            bp: The right binding power
        """
        def led(self, left):
            self.first = left
            self.second = expression(bp)

            return self

        symbol(id, bp).led = led

    def infix_r(id, bp):
        """Helper function for defining right associative infix operators

        Args:
            id: The symbol identifier

            bp: The right binding power
        """
        def led(self, left):
            self.first = left
            self.second = expression(bp - 1)

            return self

        symbol(id, bp).led = led

    def prefix(id, bp):
        """Helper function for defining prefix operators

        Args:
            id: The symbol identifier

            bp: The right binding power"""
        def nud(self):
            self.first = expression(bp)
            self.second = None

            return self

        symbol(id).nud = nud

    def assignment(id, bp):
        def led(self, left):
            if left.id != '.' and left.arity != 'name':
                left.error = 'Bad lvalue'

            self.first = left
            self.second = expression(bp - 1)
            self.assignment = True
            self.arity = 'binary'

            return self

        symbol(id, bp).led = led

    def dot_operator():
        def led(self, left):
            self.first = left

            if token.arity != 'name':
                token.error = 'Expected a property name'

            token.arity = 'literal'
            self.second = token
            self.arity = 'binary'
            advance()

            return self

        symbol('.', 80).led = led

    def statement():
        n = token
        if hasattr(n, 'std'):
            advance()
            return n.std()

        v = expression(0)
        if not hasattr(v, 'assignment') and not v.id == '(':
            v.error = 'Bad expression statement'

        advance(';')
        return v

    def statements():
        a = []
        while True:
            if token.id == '}' or token.id == '(end)':
                break

            s = statement()

            if s:
                a.append(s)

        return a

    def stmt(s, f):
        x = symbol(s)
        x.std = f

        return x

    def block_statement():
        a = statements()
        advance('}')

        return a

    def block():
        t = token
        advance('{')

        return t.std()

    def initialization():


    # Populate symbol table
    infix('+', 50)
    infix('-', 50)
    infix('*', 60)
    infix('/', 60)

    infix('==', 40)
    infix('!=', 40)
    infix('<', 40)
    infix('<=', 40)
    infix('>', 40)
    infix('>=', 40)

    prefix('+', 100)
    prefix('-', 100)

    dot_operator()

    symbol('(literal)').nud = lambda self: self
    symbol('(end)')

    assignment('=', 10)
    assignment('+=', 10)
    assignment('-=', 10)

    stmt('{', block_statement)

    next = tokenize(program).__next__
    token = advance()

    s = statements()
    advance('(end)')

    return s
