#!/usr/bin/env python3
"""
Minimalistic Python File Editor
Features:
- Syntax highlighting for Python code
- Smart indentation (auto-detect tabs vs spaces)
- Maintains indent type consistency
- Code execution
- Syntax validation
"""

import sys
import re
import ast
import subprocess
import tempfile
from PySide6.QtWidgets import (QApplication, QMainWindow, QPlainTextEdit, 
                               QFileDialog, QMessageBox, QToolBar, QStatusBar,
                               QTextEdit, QSplitter, QCompleter)
from PySide6.QtCore import Qt, QRegularExpression, QProcess, QStringListModel
from PySide6.QtGui import (QSyntaxHighlighter, QTextCharFormat, QColor, 
                          QFont, QKeyEvent, QAction, QTextCursor)


class PythonHighlighter(QSyntaxHighlighter):
    """Syntax highlighter for Python code"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        # Define formats matching PyCharm Darcula theme
        keyword_format = QTextCharFormat()
        keyword_format.setForeground(QColor("#CC7832"))
        keyword_format.setFontWeight(QFont.Bold)
        
        string_format = QTextCharFormat()
        string_format.setForeground(QColor("#6A8759"))
        
        fstring_brace_format = QTextCharFormat()
        fstring_brace_format.setForeground(QColor("#CC7832"))
        fstring_brace_format.setFontWeight(QFont.Bold)
        
        comment_format = QTextCharFormat()
        comment_format.setForeground(QColor("#808080"))
        comment_format.setFontItalic(True)
        
        function_format = QTextCharFormat()
        function_format.setForeground(QColor("#FFC66D"))
        
        class_format = QTextCharFormat()
        class_format.setForeground(QColor("#A9B7C6"))
        class_format.setFontWeight(QFont.Bold)
        
        number_format = QTextCharFormat()
        number_format.setForeground(QColor("#6897BB"))
        
        decorator_format = QTextCharFormat()
        decorator_format.setForeground(QColor("#BBB529"))
        
        builtin_format = QTextCharFormat()
        builtin_format.setForeground(QColor("#8888C6"))
        
        self_format = QTextCharFormat()
        self_format.setForeground(QColor("#94558D"))
        self_format.setFontItalic(True)
        
        type_format = QTextCharFormat()
        type_format.setForeground(QColor("#8888C6"))
        
        # Define highlighting rules as (pattern, format)
        self.highlighting_rules = []
        
        # Keywords (highest priority)
        keywords = [
            'and', 'as', 'assert', 'break', 'class', 'continue', 'def',
            'del', 'elif', 'else', 'except', 'False', 'finally', 'for',
            'from', 'global', 'if', 'import', 'in', 'is', 'lambda', 'None',
            'nonlocal', 'not', 'or', 'pass', 'raise', 'return', 'True',
            'try', 'while', 'with', 'yield', 'async', 'await'
        ]
        
        keyword_pattern = r'\b(' + '|'.join(keywords) + r')\b'
        self.highlighting_rules.append((QRegularExpression(keyword_pattern), keyword_format))
        
        # Built-in functions and exceptions
        builtins = [
            'abs', 'all', 'any', 'bin', 'bool', 'bytes', 'chr', 'dict',
            'dir', 'enumerate', 'filter', 'float', 'int', 'len', 'list',
            'map', 'max', 'min', 'open', 'print', 'range', 'set', 'str',
            'sum', 'tuple', 'type', 'zip', 'Exception', 'ValueError',
            'TypeError', 'KeyError', 'IndexError', 'AttributeError',
            'RuntimeError', 'StopIteration', 'NotImplementedError'
        ]
        
        builtin_pattern = r'\b(' + '|'.join(builtins) + r')\b'
        self.highlighting_rules.append((QRegularExpression(builtin_pattern), builtin_format))
        
        # Type annotations (typing module and built-in generics)
        type_hints = [
            'List', 'Dict', 'Set', 'Tuple', 'Optional', 'Union', 'Any', 'Callable',
            'Iterable', 'Iterator', 'Sequence', 'Mapping', 'Type', 'TypeVar',
            'Generic', 'Protocol', 'Literal', 'Final', 'ClassVar'
        ]
        type_pattern = r'\b(' + '|'.join(type_hints) + r')\b'
        self.highlighting_rules.append((QRegularExpression(type_pattern), type_format))
        
        # self keyword
        self.highlighting_rules.append((
            QRegularExpression(r'\bself\b'),
            self_format
        ))
        
        # Numbers
        self.highlighting_rules.append((
            QRegularExpression(r'\b[+-]?[0-9]+\.?[0-9]*([eE][+-]?[0-9]+)?\b'),
            number_format
        ))
        
        # Decorators
        self.highlighting_rules.append((
            QRegularExpression(r'@\w+'),
            decorator_format
        ))
        
        # Function definitions
        self.highlighting_rules.append((
            QRegularExpression(r'\bdef\s+(\w+)'),
            function_format
        ))
        
        # Function calls
        self.highlighting_rules.append((
            QRegularExpression(r'\b(\w+)(?=\s*\()'),
            function_format
        ))
        
        # Class definitions
        self.highlighting_rules.append((
            QRegularExpression(r'\bclass\s+(\w+)'),
            class_format
        ))
        
        # Comments (must come last in rules)
        self.highlighting_rules.append((
            QRegularExpression(r'#[^\n]*'),
            comment_format
        ))
        
        # Store formats for strings
        self.string_format = string_format
        self.fstring_brace_format = fstring_brace_format
        self.tri_single_format = string_format
        self.tri_double_format = string_format
        
    def highlightBlock(self, text):
        """Apply syntax highlighting to a block of text"""
        
        # First handle multi-line strings
        self.setCurrentBlockState(0)
        
        # Check for continuation of triple-quoted strings
        in_multiline = self.previousBlockState() == 1
        
        if in_multiline:
            end_index = text.find('"""')
            if end_index == -1:
                end_index = text.find("'''")
            
            if end_index >= 0:
                length = end_index + 3
                self.setFormat(0, length, self.tri_double_format)
                self.setCurrentBlockState(0)
            else:
                self.setFormat(0, len(text), self.tri_double_format)
                self.setCurrentBlockState(1)
                return
        
        # Look for start of triple-quoted strings
        for delimiter in ['"""', "'''"]:
            start_index = text.find(delimiter)
            if start_index >= 0:
                end_index = text.find(delimiter, start_index + 3)
                if end_index >= 0:
                    length = end_index - start_index + 3
                    self.setFormat(start_index, length, self.tri_double_format)
                else:
                    self.setFormat(start_index, len(text) - start_index, self.tri_double_format)
                    self.setCurrentBlockState(1)
                    return
        
        # Handle single-line strings (including f-strings)
        self.highlight_strings(text)
        
        # Apply regular highlighting rules (after strings so keywords in strings aren't highlighted)
        for pattern, format_style in self.highlighting_rules:
            match_iterator = pattern.globalMatch(text)
            while match_iterator.hasNext():
                match = match_iterator.next()
                start = match.capturedStart()
                length = match.capturedLength()
                
                # Don't override string formatting
                if self.format(start).foreground().color() != self.string_format.foreground().color():
                    self.setFormat(start, length, format_style)
    
    def highlight_strings(self, text):
        """Highlight string literals including f-strings"""
        i = 0
        while i < len(text):
            # Check for f-string
            if i < len(text) - 1 and text[i] in 'fFrRbBuU':
                prefix = text[i]
                quote_char = text[i + 1] if i + 1 < len(text) else None
                
                if quote_char in ['"', "'"]:
                    # Find string end
                    start = i
                    i += 2
                    is_fstring = prefix in 'fF'
                    
                    while i < len(text):
                        if text[i] == '\\' and i + 1 < len(text):
                            i += 2
                            continue
                        elif text[i] == quote_char:
                            # Found end of string
                            self.setFormat(start, i - start + 1, self.string_format)
                            
                            # If f-string, highlight braces
                            if is_fstring:
                                self.highlight_fstring_braces(text, start, i + 1)
                            
                            i += 1
                            break
                        i += 1
                    continue
            
            # Regular strings
            elif text[i] in ['"', "'"]:
                quote_char = text[i]
                start = i
                i += 1
                
                while i < len(text):
                    if text[i] == '\\' and i + 1 < len(text):
                        i += 2
                        continue
                    elif text[i] == quote_char:
                        self.setFormat(start, i - start + 1, self.string_format)
                        i += 1
                        break
                    i += 1
                continue
            
            i += 1
    
    def highlight_fstring_braces(self, text, start, end):
        """Highlight braces in f-strings"""
        i = start
        while i < end:
            if text[i] == '{' and (i + 1 >= end or text[i + 1] != '{'):
                # Find matching closing brace
                brace_start = i
                depth = 1
                i += 1
                
                while i < end and depth > 0:
                    if text[i] == '{':
                        depth += 1
                    elif text[i] == '}':
                        depth -= 1
                        if depth == 0:
                            # Highlight the braces
                            self.setFormat(brace_start, 1, self.fstring_brace_format)
                            self.setFormat(i, 1, self.fstring_brace_format)
                    i += 1
                continue
            elif text[i] == '}' and (i + 1 >= end or text[i + 1] != '}'):
                # Closing brace
                self.setFormat(i, 1, self.fstring_brace_format)
            
            i += 1


class CodeEditor(QPlainTextEdit):
    """Custom text editor with smart indentation"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        # Set font
        font = QFont("Consolas", 10)
        if not font.exactMatch():
            font = QFont("Courier New", 10)
        self.setFont(font)
        
        # Set tab behavior
        self.setTabStopDistance(40)  # 4 spaces equivalent
        
        # Indentation settings
        self.indent_type = "spaces"  # "spaces" or "tabs"
        self.indent_size = 4
        self.auto_detect_indent = True
        
        # Initialize highlighter
        self.highlighter = PythonHighlighter(self.document())
        
        # Setup autocomplete
        self.completer = QCompleter(self)
        self.completer.setWidget(self)
        self.completer.setCompletionMode(QCompleter.PopupCompletion)
        self.completer.setCaseSensitivity(Qt.CaseInsensitive)
        self.completer.activated.connect(self.insert_completion)
        
        self.completion_model = QStringListModel()
        self.completer.setModel(self.completion_model)
        
        # Update completions on text change
        self.textChanged.connect(self.update_completions)
        
        # Track Ctrl key for jump to definition
        self.ctrl_pressed = False
        self.setMouseTracking(True)
    
    def detect_indentation(self):
        """Auto-detect indentation type from existing content"""
        text = self.toPlainText()
        lines = text.split('\n')
        
        spaces_count = 0
        tabs_count = 0
        indent_sizes = []
        
        for line in lines:
            if not line.strip():
                continue
            
            # Count leading spaces/tabs
            leading_spaces = len(line) - len(line.lstrip(' '))
            leading_tabs = len(line) - len(line.lstrip('\t'))
            
            if leading_tabs > 0:
                tabs_count += 1
            elif leading_spaces > 0:
                spaces_count += 1
                # Track indent sizes
                if leading_spaces % 2 == 0:  # Valid indent
                    indent_sizes.append(leading_spaces)
        
        # Determine indent type
        if tabs_count > spaces_count:
            self.indent_type = "tabs"
            self.indent_size = 1
        else:
            self.indent_type = "spaces"
            # Determine most common indent size
            if indent_sizes:
                # Find GCD-like pattern
                from collections import Counter
                size_diffs = []
                sorted_sizes = sorted(set(indent_sizes))
                for i in range(1, len(sorted_sizes)):
                    size_diffs.append(sorted_sizes[i] - sorted_sizes[i-1])
                
                if size_diffs:
                    common_diff = Counter(size_diffs).most_common(1)[0][0]
                    self.indent_size = common_diff
                else:
                    self.indent_size = 4  # Default
    
    def get_line_indentation(self, line_text):
        """Get indentation level of a line"""
        if self.indent_type == "tabs":
            return len(line_text) - len(line_text.lstrip('\t'))
        else:
            leading_spaces = len(line_text) - len(line_text.lstrip(' '))
            return leading_spaces // self.indent_size
    
    def update_completions(self):
        """Extract identifiers from code for autocomplete"""
        code = self.toPlainText()
        identifiers = set()
        
        # Extract using regex for quick parsing
        # Function definitions
        for match in re.finditer(r'\bdef\s+(\w+)', code):
            identifiers.add(match.group(1))
        
        # Class definitions
        for match in re.finditer(r'\bclass\s+(\w+)', code):
            identifiers.add(match.group(1))
        
        # Variable assignments (simple cases)
        for match in re.finditer(r'\b([a-zA-Z_]\w*)\s*=', code):
            identifiers.add(match.group(1))
        
        # Import statements
        for match in re.finditer(r'\bimport\s+(\w+)', code):
            identifiers.add(match.group(1))
        for match in re.finditer(r'\bfrom\s+\w+\s+import\s+(\w+)', code):
            identifiers.add(match.group(1))
        
        # Add Python keywords and builtins
        keywords = ['def', 'class', 'if', 'elif', 'else', 'for', 'while', 'try', 
                   'except', 'finally', 'with', 'return', 'yield', 'import', 'from',
                   'as', 'pass', 'break', 'continue', 'lambda', 'True', 'False', 
                   'None', 'and', 'or', 'not', 'in', 'is', 'async', 'await']
        
        builtins = ['print', 'len', 'range', 'str', 'int', 'float', 'list', 'dict',
                   'set', 'tuple', 'open', 'enumerate', 'zip', 'map', 'filter',
                   'sum', 'min', 'max', 'abs', 'all', 'any', 'sorted', 'reversed',
                   'isinstance', 'issubclass', 'hasattr', 'getattr', 'setattr']
        
        # Type hints and typing module
        type_hints = [
            'List', 'Dict', 'Set', 'Tuple', 'Optional', 'Union', 'Any', 'Callable',
            'Iterable', 'Iterator', 'Sequence', 'Mapping', 'Type', 'TypeVar',
            'Generic', 'Protocol', 'Literal', 'Final', 'ClassVar', 'cast',
            'list', 'dict', 'set', 'tuple',  # lowercase for Python 3.9+
        ]
        
        # Common return type patterns
        return_patterns = [
            '-> None:',
            '-> str:',
            '-> int:',
            '-> float:',
            '-> bool:',
            '-> list:',
            '-> dict:',
            '-> tuple:',
            '-> List[str]:',
            '-> List[int]:',
            '-> Dict[str, Any]:',
            '-> Optional[str]:',
            '-> Optional[int]:',
        ]
        
        identifiers.update(keywords)
        identifiers.update(builtins)
        identifiers.update(type_hints)
        identifiers.update(return_patterns)
        
        # Update model
        self.completion_model.setStringList(sorted(identifiers))
    
    def insert_completion(self, completion):
        """Insert the selected completion"""
        cursor = self.textCursor()
        
        # Get the prefix that was typed
        prefix = self.completer.completionPrefix()
        
        # Delete the prefix
        for _ in range(len(prefix)):
            cursor.deletePreviousChar()
        
        # Insert the full completion
        cursor.insertText(completion)
        self.setTextCursor(cursor)
    
    def text_under_cursor(self):
        """Get the word under cursor for completion"""
        cursor = self.textCursor()
        cursor.select(QTextCursor.WordUnderCursor)
        return cursor.selectedText()
    
    def create_indent_string(self, level):
        """Create indent string based on current settings"""
        if self.indent_type == "tabs":
            return '\t' * level
        else:
            return ' ' * (self.indent_size * level)
    
    def keyPressEvent(self, event: QKeyEvent):
        """Handle key press events for smart indentation and autocomplete"""
        
        # Track Ctrl key
        if event.key() == Qt.Key_Control:
            self.ctrl_pressed = True
            self.viewport().setCursor(Qt.IBeamCursor)
        
        # Handle completer popup
        if self.completer.popup().isVisible():
            # Keys that should be handled by completer
            if event.key() in (Qt.Key_Enter, Qt.Key_Return):
                event.ignore()
                return
            elif event.key() == Qt.Key_Escape:
                self.completer.popup().hide()
                event.accept()
                return
            elif event.key() in (Qt.Key_Tab, Qt.Key_Backtab):
                event.ignore()
                return
        
        # Auto-detect indentation on first edit
        if self.auto_detect_indent and self.toPlainText():
            self.detect_indentation()
            self.auto_detect_indent = False
        
        cursor = self.textCursor()
        
        # Handle Return/Enter key
        if event.key() in (Qt.Key_Return, Qt.Key_Enter):
            cursor = self.textCursor()
            
            # Get current line for indent calculation
            cursor.select(QTextCursor.LineUnderCursor)
            current_line = cursor.selectedText()
            
            # Calculate base indentation from current line
            indent_level = self.get_line_indentation(current_line)
            
            # Check if line ends with colon (increase indent)
            stripped_line = current_line.rstrip()
            if stripped_line.endswith(':'):
                indent_level += 1
            
            # Reset cursor and insert newline
            cursor = self.textCursor()
            super().keyPressEvent(event)
            
            # Add indentation to new line
            indent_str = self.create_indent_string(indent_level)
            self.insertPlainText(indent_str)
            
            return
        
        # Handle Tab key
        elif event.key() == Qt.Key_Tab:
            if self.indent_type == "tabs":
                self.insertPlainText('\t')
            else:
                self.insertPlainText(' ' * self.indent_size)
            return
        
        # Handle Shift+Tab (dedent)
        elif event.key() == Qt.Key_Backtab:
            cursor = self.textCursor()
            cursor.select(QTextCursor.LineUnderCursor)
            line = cursor.selectedText()
            
            if self.indent_type == "tabs":
                if line.startswith('\t'):
                    cursor.movePosition(QTextCursor.StartOfLine)
                    cursor.deleteChar()
            else:
                leading_spaces = len(line) - len(line.lstrip(' '))
                if leading_spaces >= self.indent_size:
                    cursor.movePosition(QTextCursor.StartOfLine)
                    for _ in range(self.indent_size):
                        cursor.deleteChar()
            
            return
        
        # Handle Backspace at start of line (smart dedent)
        elif event.key() == Qt.Key_Backspace:
            cursor = self.textCursor()
            cursor.select(QTextCursor.LineUnderCursor)
            line = cursor.selectedText()
            
            pos = self.textCursor().positionInBlock()
            
            # If we're in the indentation area
            if pos > 0 and line[:pos].strip() == '':
                if self.indent_type == "spaces" and pos >= self.indent_size:
                    # Check if we can delete a full indent
                    if pos % self.indent_size == 0:
                        cursor = self.textCursor()
                        for _ in range(self.indent_size):
                            cursor.deletePreviousChar()
                        return
        
        # Default behavior
        super().keyPressEvent(event)
        
        # Check for type hint template insertion
        if event.text() == ':' or event.text() == ')':
            self.check_type_hint_insertion()
        
        # Trigger autocomplete only when typing new text
        cursor = self.textCursor()
        
        # Don't trigger if there's text immediately after cursor (in middle of word)
        cursor.movePosition(QTextCursor.Right, QTextCursor.KeepAnchor)
        if cursor.selectedText().strip():
            self.completer.popup().hide()
            return
        
        completion_prefix = self.text_under_cursor()
        if len(completion_prefix) >= 2:  # Start autocomplete after 2 characters
            if completion_prefix != self.completer.completionPrefix():
                self.completer.setCompletionPrefix(completion_prefix)
                popup = self.completer.popup()
                popup.setCurrentIndex(self.completer.completionModel().index(0, 0))
            
            # Position and show popup
            cursor_rect = self.cursorRect()
            cursor_rect.setWidth(self.completer.popup().sizeHintForColumn(0)
                               + self.completer.popup().verticalScrollBar().sizeHint().width())
            self.completer.complete(cursor_rect)
        else:
            self.completer.popup().hide()
    
    def check_type_hint_insertion(self):
        """Check if we should insert type hint template"""
        cursor = self.textCursor()
        cursor.select(QTextCursor.LineUnderCursor)
        line = cursor.selectedText()
        
        # Check if this is a function definition without return type
        if re.match(r'^\s*def\s+\w+\([^)]*\)\s*:\s*$', line):
            # Check if there's already a return type annotation
            if '->' not in line:
                # Move cursor before the colon
                cursor = self.textCursor()
                block_text = cursor.block().text()
                colon_pos = block_text.rfind(':')
                if colon_pos != -1:
                    cursor.movePosition(QTextCursor.StartOfLine)
                    cursor.movePosition(QTextCursor.Right, QTextCursor.MoveAnchor, colon_pos)
                    cursor.insertText(' -> None')
                    cursor.movePosition(QTextCursor.Right)  # Move past the colon
                    self.setTextCursor(cursor)
    
    def mousePressEvent(self, event):
        """Handle mouse press for Ctrl+Click navigation"""
        if event.button() == Qt.LeftButton and self.ctrl_pressed:
            cursor = self.cursorForPosition(event.pos())
            cursor.select(QTextCursor.WordUnderCursor)
            word = cursor.selectedText()
            
            if word:
                self.jump_to_definition(word)
                return
        
        super().mousePressEvent(event)
    
    def mouseMoveEvent(self, event):
        """Change cursor when hovering over identifiers with Ctrl held"""
        if self.ctrl_pressed:
            cursor = self.cursorForPosition(event.pos())
            cursor.select(QTextCursor.WordUnderCursor)
            word = cursor.selectedText()
            
            # Check if word is an identifier
            if word and re.match(r'^[a-zA-Z_]\w*$', word):
                self.viewport().setCursor(Qt.PointingHandCursor)
            else:
                self.viewport().setCursor(Qt.IBeamCursor)
        else:
            self.viewport().setCursor(Qt.IBeamCursor)
        
        super().mouseMoveEvent(event)
    
    def keyReleaseEvent(self, event):
        """Handle key release to track Ctrl"""
        if event.key() == Qt.Key_Control:
            self.ctrl_pressed = False
            self.viewport().setCursor(Qt.IBeamCursor)
        super().keyReleaseEvent(event)
    
    def jump_to_definition(self, identifier):
        """Jump to the definition of a function or class"""
        code = self.toPlainText()
        lines = code.split('\n')
        
        # Search for function or class definition
        patterns = [
            rf'^\s*def\s+{re.escape(identifier)}\s*\(',
            rf'^\s*class\s+{re.escape(identifier)}\s*[\(:]',
            rf'^\s*{re.escape(identifier)}\s*=',  # Variable assignment
        ]
        
        for line_num, line in enumerate(lines):
            for pattern in patterns:
                if re.search(pattern, line):
                    # Found definition, jump to it
                    cursor = QTextCursor(self.document().findBlockByLineNumber(line_num))
                    self.setTextCursor(cursor)
                    self.centerCursor()
                    
                    # Briefly highlight the line
                    self.highlight_line(line_num)
                    return
    
    def highlight_line(self, line_num):
        """Briefly highlight a line"""
        # Select the line
        cursor = QTextCursor(self.document().findBlockByLineNumber(line_num))
        cursor.select(QTextCursor.LineUnderCursor)
        
        # Create selection with highlight
        selection = QTextEdit.ExtraSelection()
        selection.format.setBackground(QColor("#3A3A3A"))
        selection.cursor = cursor
        
        self.setExtraSelections([selection])
        
        # Clear highlight after 1 second
        from PySide6.QtCore import QTimer
        QTimer.singleShot(1000, lambda: self.setExtraSelections([]))


class PythonEditor(QMainWindow):
    """Main editor window"""
    
    def __init__(self):
        super().__init__()
        
        self.current_file = None
        self.process = None
        self.init_ui()
    
    def init_ui(self):
        """Initialize the user interface"""
        self.setWindowTitle("Microid")
        self.setGeometry(100, 100, 900, 700)
        
        # Create splitter for editor and output
        splitter = QSplitter(Qt.Vertical)
        
        # Create editor
        self.editor = CodeEditor()
        splitter.addWidget(self.editor)
        
        # Create output console
        self.output = QTextEdit()
        self.output.setReadOnly(True)
        self.output.setMaximumHeight(200)
        font = QFont("Consolas", 9)
        if not font.exactMatch():
            font = QFont("Courier New", 9)
        self.output.setFont(font)
        self.output.setStyleSheet("background-color: #1E1E1E; color: #D4D4D4;")
        splitter.addWidget(self.output)
        
        # Set splitter sizes
        splitter.setSizes([500, 200])
        
        self.setCentralWidget(splitter)
        
        # Track modifications
        self.editor.document().modificationChanged.connect(self.on_modification_changed)
        
        # Create toolbar
        toolbar = QToolBar()
        self.addToolBar(toolbar)
        
        # New file action
        new_action = QAction("New", self)
        new_action.setShortcut("Ctrl+N")
        new_action.triggered.connect(self.new_file)
        toolbar.addAction(new_action)
        
        # Open file action
        open_action = QAction("Open", self)
        open_action.setShortcut("Ctrl+O")
        open_action.triggered.connect(self.open_file)
        toolbar.addAction(open_action)
        
        # Save file action
        save_action = QAction("Save", self)
        save_action.setShortcut("Ctrl+S")
        save_action.triggered.connect(self.save_file)
        toolbar.addAction(save_action)
        
        # Save As action
        save_as_action = QAction("Save As", self)
        save_as_action.setShortcut("Ctrl+Shift+S")
        save_as_action.triggered.connect(self.save_file_as)
        toolbar.addAction(save_as_action)
        
        toolbar.addSeparator()
        
        # Run code action
        run_action = QAction("▶ Run", self)
        run_action.setShortcut("F5")
        run_action.triggered.connect(self.run_code)
        toolbar.addAction(run_action)
        
        # Validate syntax action
        validate_action = QAction("✓ Validate", self)
        validate_action.setShortcut("F6")
        validate_action.triggered.connect(self.validate_syntax)
        toolbar.addAction(validate_action)
        
        toolbar.addSeparator()
        
        # Indent type toggle with state display
        self.indent_action = QAction("Indent: Spaces (4)", self)
        self.indent_action.triggered.connect(self.toggle_indent_type)
        toolbar.addAction(self.indent_action)
        
        # Clear output action
        clear_action = QAction("Clear Output", self)
        clear_action.triggered.connect(self.clear_output)
        toolbar.addAction(clear_action)
        
        toolbar.addSeparator()
        
        # Add typing import action
        typing_action = QAction("Add typing import", self)
        typing_action.triggered.connect(self.add_typing_import)
        toolbar.addAction(typing_action)
        
        # Status bar
        self.statusBar = QStatusBar()
        self.setStatusBar(self.statusBar)
        self.update_status_bar()
    
    def on_modification_changed(self, changed):
        """Update window title when document is modified"""
        title = "Microid"
        if self.current_file:
            title += f" - {self.current_file}"
        if changed:
            title += " *"
        self.setWindowTitle(title)
    
    def update_status_bar(self):
        """Update status bar and indent button with current settings"""
        indent_info = f"Indent: {self.editor.indent_type} ({self.editor.indent_size})"
        self.statusBar.showMessage(indent_info)
        
        # Update button text
        if self.editor.indent_type == "spaces":
            self.indent_action.setText(f"Indent: Spaces ({self.editor.indent_size})")
        else:
            self.indent_action.setText("Indent: Tabs")
    
    def clear_output(self):
        """Clear the output console"""
        self.output.clear()
    
    def add_typing_import(self):
        """Add 'from typing import' statement at top of file"""
        code = self.editor.toPlainText()
        
        # Check if typing import already exists
        if re.search(r'from\s+typing\s+import', code):
            self.append_output("Typing import already exists", "#FFC66D")
            return
        
        # Common typing imports
        typing_imports = "from typing import List, Dict, Optional, Union, Any, Tuple, Set, Callable"
        
        # Find where to insert (after any existing imports or at top)
        lines = code.split('\n')
        insert_line = 0
        
        # Skip shebang and docstrings
        in_docstring = False
        for i, line in enumerate(lines):
            if i == 0 and line.startswith('#!'):
                insert_line = i + 1
                continue
            
            if '"""' in line or "'''" in line:
                in_docstring = not in_docstring
                if not in_docstring:
                    insert_line = i + 1
                continue
            
            if in_docstring:
                continue
            
            # Find last import
            if line.strip().startswith('import ') or line.strip().startswith('from '):
                insert_line = i + 1
            elif line.strip() and not line.strip().startswith('#'):
                # First non-import, non-comment line
                break
        
        # Insert the import
        lines.insert(insert_line, typing_imports)
        self.editor.setPlainText('\n'.join(lines))
        self.append_output("Added typing imports", "#6A8759")
    
    def append_output(self, text, color="#D4D4D4"):
        """Append text to output console with optional color"""
        self.output.setTextColor(QColor(color))
        self.output.append(text)
        self.output.setTextColor(QColor("#D4D4D4"))
    
    def validate_syntax(self):
        """Validate Python syntax without running"""
        code = self.editor.toPlainText()
        
        if not code.strip():
            self.append_output("No code to validate.", "#FFC66D")
            return
        
        self.append_output("=" * 50, "#808080")
        self.append_output("Validating syntax...", "#6897BB")
        
        try:
            ast.parse(code)
            self.append_output("✓ Syntax is valid!", "#6A8759")
        except SyntaxError as e:
            self.append_output(f"✗ Syntax Error:", "#FF6B6B")
            self.append_output(f"  Line {e.lineno}: {e.msg}", "#FF6B6B")
            if e.text:
                self.append_output(f"  {e.text.rstrip()}", "#FFC66D")
                if e.offset:
                    self.append_output(f"  {' ' * (e.offset - 1)}^", "#FF6B6B")
        except Exception as e:
            self.append_output(f"✗ Error: {str(e)}", "#FF6B6B")
        
        self.append_output("=" * 50, "#808080")
    
    def run_code(self):
        """Execute the Python code"""
        code = self.editor.toPlainText()
        
        if not code.strip():
            self.append_output("No code to run.", "#FFC66D")
            return
        
        # First validate syntax
        try:
            ast.parse(code)
        except SyntaxError as e:
            self.append_output("=" * 50, "#808080")
            self.append_output("Cannot run - Syntax Error:", "#FF6B6B")
            self.append_output(f"  Line {e.lineno}: {e.msg}", "#FF6B6B")
            self.append_output("=" * 50, "#808080")
            return
        
        self.append_output("=" * 50, "#808080")
        self.append_output("Running code...", "#6897BB")
        self.append_output("", "#D4D4D4")
        
        # Save code to temporary file
        try:
            with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False, encoding='utf-8') as f:
                f.write(code)
                temp_file = f.name
            
            # Create process
            self.process = QProcess(self)
            self.process.readyReadStandardOutput.connect(self.handle_stdout)
            self.process.readyReadStandardError.connect(self.handle_stderr)
            self.process.finished.connect(lambda: self.handle_finished(temp_file))
            
            # Start process
            self.process.start(sys.executable, [temp_file])
            
        except Exception as e:
            self.append_output(f"Error running code: {str(e)}", "#FF6B6B")
            self.append_output("=" * 50, "#808080")
    
    def handle_stdout(self):
        """Handle standard output from process"""
        if self.process:
            data = self.process.readAllStandardOutput()
            text = bytes(data).decode('utf-8', errors='replace')
            self.append_output(text.rstrip(), "#D4D4D4")
    
    def handle_stderr(self):
        """Handle standard error from process"""
        if self.process:
            data = self.process.readAllStandardError()
            text = bytes(data).decode('utf-8', errors='replace')
            self.append_output(text.rstrip(), "#FF6B6B")
    
    def handle_finished(self, temp_file):
        """Handle process completion"""
        if self.process:
            exit_code = self.process.exitCode()
            self.append_output("", "#D4D4D4")
            if exit_code == 0:
                self.append_output(f"Process finished with exit code {exit_code}", "#6A8759")
            else:
                self.append_output(f"Process finished with exit code {exit_code}", "#FF6B6B")
            self.append_output("=" * 50, "#808080")
            
            # Clean up temp file
            try:
                import os
                os.unlink(temp_file)
            except:
                pass
    
    def new_file(self):
        """Create a new file"""
        if self.maybe_save():
            self.editor.clear()
            self.current_file = None
            self.editor.auto_detect_indent = True
            self.setWindowTitle("Microid")
    
    def open_file(self):
        """Open an existing file"""
        if self.maybe_save():
            file_name, _ = QFileDialog.getOpenFileName(
                self, "Open File", "", "Python Files (*.py);;All Files (*)"
            )
            
            if file_name:
                try:
                    with open(file_name, 'r', encoding='utf-8') as f:
                        content = f.read()
                    
                    self.editor.setPlainText(content)
                    self.current_file = file_name
                    self.editor.auto_detect_indent = True
                    self.editor.detect_indentation()
                    self.editor.document().setModified(False)
                    self.update_status_bar()
                    self.setWindowTitle(f"Microid - {file_name}")
                except Exception as e:
                    QMessageBox.critical(self, "Error", f"Could not open file:\n{e}")
    
    def save_file(self):
        """Save the current file"""
        if self.current_file:
            return self.save_to_file(self.current_file)
        else:
            return self.save_file_as()
    
    def save_file_as(self):
        """Save the file with a new name"""
        file_name, _ = QFileDialog.getSaveFileName(
            self, "Save File", "", "Python Files (*.py);;All Files (*)"
        )
        
        if file_name:
            if self.save_to_file(file_name):
                self.current_file = file_name
                self.setWindowTitle(f"Microid - {file_name}")
                return True
        return False
    
    def save_to_file(self, file_name):
        """Save content to a file"""
        try:
            with open(file_name, 'w', encoding='utf-8') as f:
                f.write(self.editor.toPlainText())
            
            self.editor.document().setModified(False)
            return True
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Could not save file:\n{e}")
            return False
    
    def maybe_save(self):
        """Prompt to save if document is modified"""
        if self.editor.document().isModified():
            ret = QMessageBox.question(
                self,
                "Save Changes?",
                "The document has been modified.\nDo you want to save your changes?",
                QMessageBox.Save | QMessageBox.Discard | QMessageBox.Cancel
            )
            
            if ret == QMessageBox.Save:
                return self.save_file()
            elif ret == QMessageBox.Cancel:
                return False
        
        return True
    
    def toggle_indent_type(self):
        """Toggle between spaces and tabs"""
        if self.editor.indent_type == "spaces":
            self.editor.indent_type = "tabs"
            self.editor.indent_size = 1
        else:
            self.editor.indent_type = "spaces"
            self.editor.indent_size = 4
        
        self.update_status_bar()
    
    def closeEvent(self, event):
        """Handle window close event"""
        if self.maybe_save():
            event.accept()
        else:
            event.reject()


def main():
    app = QApplication(sys.argv)
    editor = PythonEditor()
    editor.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
