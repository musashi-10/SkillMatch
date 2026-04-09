with open('app.py', 'r', encoding='utf-8') as f:
    text = f.read()

import ast

try:
    ast.parse(text)
    print("AST Parse Successful!")
except SyntaxError as e:
    print(f"AST Parse Failed: {e.msg} at line {e.lineno}")

quotes = text.split('\"\"\"')
print(f"Triple quotes: {len(quotes) - 1}")
if (len(quotes)-1) % 2 != 0:
    print("UNBALANCED TRIPLE QUOTES!")
