#!/usr/bin/env python3
"""
Minimalistic Python File Editor with Virtual Environment Support
Features:
- Complete dark/light mode UI with persistence
- Syntax highlighting for Python code
- Smart indentation (auto-detect tabs vs spaces)
- Line numbers display
- Code execution
- Virtual environment management (create/select/activate)
- Syntax validation
- Ctrl+Click error navigation
- Ctrl+F Find & Replace dialog
- Multi-line Tab indent/unindent
"""

import sys
import re
import ast
import subprocess
import tempfile
import os
import venv
from PySide6.QtWidgets import (QApplication, QMainWindow, QPlainTextEdit, 
                               QFileDialog, QMessageBox, QToolBar, QStatusBar,
                               QTextEdit, QSplitter, QCompleter, QInputDialog, QWidget,
                               QDialog, QVBoxLayout, QHBoxLayout, QLineEdit, QPushButton,
                               QLabel, QCheckBox, QRadioButton, QButtonGroup, QGroupBox)
from PySide6.QtCore import Qt, QRegularExpression, QProcess, QStringListModel, QRect, QTimer
from PySide6.QtGui import (QSyntaxHighlighter, QTextCharFormat, QColor, 
                          QFont, QKeyEvent, QAction, QTextCursor, QPainter, QPalette, QTextDocument)


class VenvDialog(QDialog):
    """Dialog for creating or selecting a virtual environment"""
    
    def __init__(self, current_venv=None, parent=None):
        super().__init__(parent)
        self.selected_venv = current_venv
        self.init_ui()
    
    def init_ui(self):
        """Initialize the UI"""
        self.setWindowTitle("Virtual Environment Manager")
        self.setModal(True)
        layout = QVBoxLayout()
        
        # Current venv display
        current_group = QGroupBox("Current Environment")
        current_layout = QVBoxLayout()
        if self.selected_venv:
            current_layout.addWidget(QLabel(f"Active: {self.selected_venv}"))
        else:
            current_layout.addWidget(QLabel("No virtual environment active"))
        current_group.setLayout(current_layout)
        layout.addWidget(current_group)
        
        # Option selection
        options_group = QGroupBox("Select Action")
        options_layout = QVBoxLayout()
        
        self.button_group = QButtonGroup()
        
        self.create_radio = QRadioButton("Create new virtual environment")
        self.select_radio = QRadioButton("Select existing virtual environment")
        self.deactivate_radio = QRadioButton("Deactivate current environment")
        
        self.button_group.addButton(self.create_radio)
        self.button_group.addButton(self.select_radio)
        self.button_group.addButton(self.deactivate_radio)
        
        options_layout.addWidget(self.create_radio)
        options_layout.addWidget(self.select_radio)
        options_layout.addWidget(self.deactivate_radio)
        
        self.create_radio.setChecked(True)
        
        options_group.setLayout(options_layout)
        layout.addWidget(options_group)
        
        # Create venv section
        create_group = QGroupBox("Create New")
        create_layout = QVBoxLayout()
        
        name_layout = QHBoxLayout()
        name_layout.addWidget(QLabel("Environment name:"))
        self.venv_name_input = QLineEdit()
        self.venv_name_input.setText("venv")
        name_layout.addWidget(self.venv_name_input)
        create_layout.addLayout(name_layout)
        
        location_layout = QHBoxLayout()
        location_layout.addWidget(QLabel("Location:"))
        self.venv_location_input = QLineEdit()
        self.venv_location_input.setText(os.getcwd())
        location_layout.addWidget(self.venv_location_input)
        browse_btn = QPushButton("Browse...")
        browse_btn.clicked.connect(self.browse_location)
        location_layout.addWidget(browse_btn)
        create_layout.addLayout(location_layout)
        
        self.system_packages_check = QCheckBox("Include system site-packages")
        create_layout.addWidget(self.system_packages_check)
        
        create_group.setLayout(create_layout)
        layout.addWidget(create_group)
        
        # Select venv section
        select_group = QGroupBox("Select Existing")
        select_layout = QVBoxLayout()
        
        select_path_layout = QHBoxLayout()
        select_path_layout.addWidget(QLabel("Path:"))
        self.venv_path_input = QLineEdit()
        select_path_layout.addWidget(self.venv_path_input)
        browse_venv_btn = QPushButton("Browse...")
        browse_venv_btn.clicked.connect(self.browse_venv)
        select_path_layout.addWidget(browse_venv_btn)
        select_layout.addLayout(select_path_layout)
        
        select_group.setLayout(select_layout)
        layout.addWidget(select_group)
        
        # Status label
        self.status_label = QLabel("")
        layout.addWidget(self.status_label)
        
        # Buttons
        button_layout = QHBoxLayout()
        
        ok_btn = QPushButton("OK")
        ok_btn.clicked.connect(self.on_ok)
        button_layout.addWidget(ok_btn)
        
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(cancel_btn)
        
        layout.addLayout(button_layout)
        
        self.setLayout(layout)
        self.resize(600, 400)
    
    def browse_location(self):
        """Browse for directory to create venv in"""
        directory = QFileDialog.getExistingDirectory(
            self, "Select Directory", self.venv_location_input.text()
        )
        if directory:
            self.venv_location_input.setText(directory)
    
    def browse_venv(self):
        """Browse for existing venv directory"""
        directory = QFileDialog.getExistingDirectory(
            self, "Select Virtual Environment Directory", os.getcwd()
        )
        if directory:
            self.venv_path_input.setText(directory)
    
    def on_ok(self):
        """Handle OK button"""
        if self.create_radio.isChecked():
            self.create_venv()
        elif self.select_radio.isChecked():
            self.select_venv()
        elif self.deactivate_radio.isChecked():
            self.selected_venv = None
            self.accept()
    
    def create_venv(self):
        """Create a new virtual environment"""
        name = self.venv_name_input.text().strip()
        location = self.venv_location_input.text().strip()
        
        if not name:
            self.status_label.setText("Please enter a name for the environment")
            return
        
        if not location:
            self.status_label.setText("Please select a location")
            return
        
        venv_path = os.path.join(location, name)
        
        if os.path.exists(venv_path):
            reply = QMessageBox.question(
                self,
                "Directory Exists",
                f"Directory {venv_path} already exists.\nOverwrite?",
                QMessageBox.Yes | QMessageBox.No
            )
            if reply == QMessageBox.No:
                return
        
        try:
            self.status_label.setText("Creating virtual environment...")
            QApplication.processEvents()
            
            # Create venv
            builder = venv.EnvBuilder(
                system_site_packages=self.system_packages_check.isChecked(),
                clear=True,
                with_pip=True
            )
            builder.create(venv_path)
            
            self.selected_venv = venv_path
            self.status_label.setText(f"Successfully created: {venv_path}")
            QMessageBox.information(
                self,
                "Success",
                f"Virtual environment created at:\n{venv_path}"
            )
            self.accept()
            
        except Exception as e:
            self.status_label.setText(f"Error: {str(e)}")
            QMessageBox.critical(
                self,
                "Error",
                f"Failed to create virtual environment:\n{str(e)}"
            )
    
    def select_venv(self):
        """Select an existing virtual environment"""
        venv_path = self.venv_path_input.text().strip()
        
        if not venv_path:
            self.status_label.setText("Please select a virtual environment directory")
            return
        
        if not os.path.exists(venv_path):
            self.status_label.setText("Directory does not exist")
            return
        
        # Check if it's a valid venv
        if sys.platform == "win32":
            python_exe = os.path.join(venv_path, "Scripts", "python.exe")
        else:
            python_exe = os.path.join(venv_path, "bin", "python")
        
        if not os.path.exists(python_exe):
            QMessageBox.warning(
                self,
                "Invalid Environment",
                f"This doesn't appear to be a valid virtual environment.\n"
                f"Expected Python executable not found at:\n{python_exe}"
            )
            return
        
        self.selected_venv = venv_path
        self.status_label.setText(f"Selected: {venv_path}")
        self.accept()


class PythonHighlighter(QSyntaxHighlighter):
    """Syntax highlighter for Python code"""
    
    def __init__(self, parent=None, is_dark_mode=True):
        super().__init__(parent)
        self.is_dark_mode = is_dark_mode
        self.setup_formats()
        
    def setup_formats(self):
        """Setup text formats based on theme"""
        # Define formats matching PyCharm theme
        if self.is_dark_mode:
            # Dark theme colors
            keyword_color = "#CC7832"
            string_color = "#6A8759"
            comment_color = "#808080"
            function_color = "#FFC66D"
            class_color = "#A9B7C6"
            number_color = "#6897BB"
            decorator_color = "#BBB529"
            builtin_color = "#8888C6"
            self_color = "#94558D"
            type_color = "#8888C6"
        else:
            # Light theme colors
            keyword_color = "#0000FF"
            string_color = "#008000"
            comment_color = "#808080"
            function_color = "#795E26"
            class_color = "#267F99"
            number_color = "#098658"
            decorator_color = "#AF00DB"
            builtin_color = "#0000FF"
            self_color = "#001080"
            type_color = "#267F99"
        
        self.keyword_format = QTextCharFormat()
        self.keyword_format.setForeground(QColor(keyword_color))
        self.keyword_format.setFontWeight(QFont.Bold)
        
        self.string_format = QTextCharFormat()
        self.string_format.setForeground(QColor(string_color))
        
        self.fstring_brace_format = QTextCharFormat()
        self.fstring_brace_format.setForeground(QColor(keyword_color))
        self.fstring_brace_format.setFontWeight(QFont.Bold)
        
        self.comment_format = QTextCharFormat()
        self.comment_format.setForeground(QColor(comment_color))
        self.comment_format.setFontItalic(True)
        
        self.function_format = QTextCharFormat()
        self.function_format.setForeground(QColor(function_color))
        
        self.class_format = QTextCharFormat()
        self.class_format.setForeground(QColor(class_color))
        self.class_format.setFontWeight(QFont.Bold)
        
        self.number_format = QTextCharFormat()
        self.number_format.setForeground(QColor(number_color))
        
        self.decorator_format = QTextCharFormat()
        self.decorator_format.setForeground(QColor(decorator_color))
        
        self.builtin_format = QTextCharFormat()
        self.builtin_format.setForeground(QColor(builtin_color))
        
        self.self_format = QTextCharFormat()
        self.self_format.setForeground(QColor(self_color))
        self.self_format.setFontItalic(True)
        
        self.type_format = QTextCharFormat()
        self.type_format.setForeground(QColor(type_color))
        
        # Store patterns as instance variables for later use
        self.highlighting_rules = []
        self.comment_pattern = QRegularExpression(r'#[^\n]*')
        
        # Keywords (highest priority)
        keywords = [
            'and', 'as', 'assert', 'break', 'class', 'continue', 'def',
            'del', 'elif', 'else', 'except', 'False', 'finally', 'for',
            'from', 'global', 'if', 'import', 'in', 'is', 'lambda', 'None',
            'nonlocal', 'not', 'or', 'pass', 'raise', 'return', 'True',
            'try', 'while', 'with', 'yield', 'async', 'await'
        ]
        
        keyword_pattern = r'\b(' + '|'.join(keywords) + r')\b'
        self.highlighting_rules.append((QRegularExpression(keyword_pattern), self.keyword_format))
        
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
        self.highlighting_rules.append((QRegularExpression(builtin_pattern), self.builtin_format))
        
        # Type annotations
        type_hints = [
            'List', 'Dict', 'Set', 'Tuple', 'Optional', 'Union', 'Any', 'Callable',
            'Iterable', 'Iterator', 'Sequence', 'Mapping', 'Type', 'TypeVar',
            'Generic', 'Protocol', 'Literal', 'Final', 'ClassVar'
        ]
        type_pattern = r'\b(' + '|'.join(type_hints) + r')\b'
        self.highlighting_rules.append((QRegularExpression(type_pattern), self.type_format))
        
        # self keyword
        self.highlighting_rules.append((QRegularExpression(r'\bself\b'), self.self_format))
        
        # Numbers
        self.highlighting_rules.append((QRegularExpression(r'\b[+-]?[0-9]+\.?[0-9]*([eE][+-]?[0-9]+)?\b'), self.number_format))
        
        # Decorators
        self.highlighting_rules.append((QRegularExpression(r'@\w+'), self.decorator_format))
        
        # Function definitions
        self.highlighting_rules.append((QRegularExpression(r'\bdef\s+(\w+)'), self.function_format))
        
        # Function calls
        self.highlighting_rules.append((QRegularExpression(r'\b(\w+)(?=\s*\()'), self.function_format))
        
        # Class definitions
        self.highlighting_rules.append((QRegularExpression(r'\bclass\s+(\w+)'), self.class_format))
        
        self.tri_single_format = self.string_format
        self.tri_double_format = self.string_format
        
    def highlightBlock(self, text):
        """Apply syntax highlighting to a block of text"""
        
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
                current_format = self.format(start)
                if (current_format.foreground().color() != self.string_format.foreground().color() or 
                    format_style == self.comment_format):
                    self.setFormat(start, length, format_style)
        
        # Apply comments last to override everything
        comment_iterator = self.comment_pattern.globalMatch(text)
        while comment_iterator.hasNext():
            match = comment_iterator.next()
            start = match.capturedStart()
            length = match.capturedLength()
            self.setFormat(start, length, self.comment_format)
    
    def highlight_strings(self, text):
        """Highlight string literals including f-strings"""
        i = 0
        while i < len(text):
            # Check for f-string
            if i < len(text) - 1 and text[i] in 'fFrRbBuU':
                prefix = text[i]
                quote_char = text[i + 1] if i + 1 < len(text) else None
                
                if quote_char in ['"', "'"]:
                    start = i
                    i += 2
                    is_fstring = prefix in 'fF'
                    
                    while i < len(text):
                        if text[i] == '\\' and i + 1 < len(text):
                            i += 2
                            continue
                        elif text[i] == quote_char:
                            self.setFormat(start, i - start + 1, self.string_format)
                            
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
                brace_start = i
                depth = 1
                i += 1
                
                while i < end and depth > 0:
                    if text[i] == '{':
                        depth += 1
                    elif text[i] == '}':
                        depth -= 1
                        if depth == 0:
                            self.setFormat(brace_start, 1, self.fstring_brace_format)
                            self.setFormat(i, 1, self.fstring_brace_format)
                    i += 1
                continue
            elif text[i] == '}' and (i + 1 >= end or text[i + 1] != '}'):
                self.setFormat(i, 1, self.fstring_brace_format)
            
            i += 1


class LineNumberArea(QWidget):
    """Widget for displaying line numbers"""
    
    def __init__(self, editor):
        super().__init__(editor)
        self.editor = editor

    def paintEvent(self, event):
        self.editor.lineNumberAreaPaintEvent(event)


class CodeEditor(QPlainTextEdit):
    """Custom text editor with smart indentation and line numbers"""
    
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
        
        # Theme settings
        self.is_dark_mode = True
        self.load_theme_preference()
        
        # Initialize highlighter
        self.highlighter = PythonHighlighter(self.document(), self.is_dark_mode)
        
        # Setup line number area
        self.line_number_area = LineNumberArea(self)
        
        # Connect signals for line numbers
        self.blockCountChanged.connect(self.updateLineNumberAreaWidth)
        self.updateRequest.connect(self.updateLineNumberAreaHelper)
        self.cursorPositionChanged.connect(lambda: self.line_number_area.update())
        
        # Set initial viewport margins
        self.updateLineNumberAreaWidth(0)
        
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
        
        # Track cursor position for status updates
        self.cursorPositionChanged.connect(self.on_cursor_position_changed)
        
        # Track Ctrl key for jump to definition
        self.ctrl_pressed = False
        self.setMouseTracking(True)
    
    def load_theme_preference(self):
        """Load theme preference from file"""
        try:
            with open('.microid_theme', 'r') as f:
                theme = f.read().strip()
                self.is_dark_mode = (theme == 'dark')
                self.apply_theme()
        except:
            self.is_dark_mode = True
            self.apply_theme()
    
    def save_theme_preference(self):
        """Save theme preference to file"""
        try:
            with open('.microid_theme', 'w') as f:
                f.write('dark' if self.is_dark_mode else 'light')
        except:
            pass
    
    def apply_theme(self):
        """Apply current theme"""
        if self.is_dark_mode:
            self.setStyleSheet("background-color: #1E1E1E; color: #D4D4D4;")
        else:
            self.setStyleSheet("background-color: #FFFFFF; color: #000000;")
        
        # Reinitialize highlighter with current theme
        self.highlighter = PythonHighlighter(self.document(), self.is_dark_mode)
        self.highlighter.rehighlight()
    
    def toggle_theme(self):
        """Toggle between light and dark mode"""
        self.is_dark_mode = not self.is_dark_mode
        self.save_theme_preference()
        self.apply_theme()
    
    def lineNumberAreaWidth(self):
        """Calculate width needed for line numbers"""
        digits = 1
        max_num = max(1, self.blockCount())
        while max_num >= 10:
            max_num //= 10
            digits += 1
        
        font_metrics = self.fontMetrics()
        space = 3 + font_metrics.horizontalAdvance('9') * digits
        return space
    
    def updateLineNumberAreaWidth(self, _):
        """Update viewport margins when line count changes"""
        self.setViewportMargins(self.lineNumberAreaWidth(), 0, 0, 0)
    
    def updateLineNumberAreaHelper(self, rect, dy):
        """Helper to connect updateRequest signal properly"""
        self.updateLineNumberArea(rect, dy)
    
    def updateLineNumberArea(self, rect, dy):
        """Update line number area when editor scrolls"""
        if dy:
            self.line_number_area.scroll(0, dy)
        else:
            self.line_number_area.update(0, rect.y(), 
                                   self.lineNumberAreaWidth(), rect.height())
    
        if rect.contains(self.viewport().rect()):
            self.updateLineNumberAreaWidth(0)

    
    def resizeEvent(self, event):
        """Handle resize events"""
        super().resizeEvent(event)
        cr = self.contentsRect()
        self.line_number_area.setGeometry(
            QRect(cr.left(), cr.top(), 
                  self.lineNumberAreaWidth(), cr.height())
        )
    
    def lineNumberAreaPaintEvent(self, event):
        """Paint line numbers"""
        painter = QPainter(self.line_number_area)
        if self.is_dark_mode:
            painter.fillRect(event.rect(), QColor("#2B2B2B"))
        else:
            painter.fillRect(event.rect(), QColor("#F0F0F0"))
        
        block = self.firstVisibleBlock()
        block_number = block.blockNumber()
        top = self.blockBoundingGeometry(block).translated(self.contentOffset()).top()
        bottom = top + self.blockBoundingRect(block).height()
        
        font_metrics = self.fontMetrics()
        current_block_number = self.textCursor().blockNumber()
        
        while block.isValid() and top <= event.rect().bottom():
            if block.isVisible() and bottom >= event.rect().top():
                number = str(block_number + 1)
                
                # Highlight current line number
                if block_number == current_block_number:
                    if self.is_dark_mode:
                        painter.fillRect(0, int(top), self.lineNumberAreaWidth(), 
                                       font_metrics.height(), 
                                       QColor("#3A3A3A"))
                        painter.setPen(QColor("#D4D4D4"))
                    else:
                        painter.fillRect(0, int(top), self.lineNumberAreaWidth(), 
                                       font_metrics.height(), 
                                       QColor("#E0E0E0"))
                        painter.setPen(QColor("#000000"))
                else:
                    if self.is_dark_mode:
                        painter.setPen(QColor("#606366"))
                    else:
                        painter.setPen(QColor("#999999"))
                
                painter.drawText(0, int(top), self.lineNumberAreaWidth(), 
                               font_metrics.height(),
                               Qt.AlignRight, number)
            
            block = block.next()
            top = bottom
            bottom = top + self.blockBoundingRect(block).height()
            block_number += 1
    
    def on_cursor_position_changed(self):
        """Emit signal when cursor position changes"""
        pass
    
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
            
            leading_spaces = len(line) - len(line.lstrip(' '))
            leading_tabs = len(line) - len(line.lstrip('\t'))
            
            if leading_tabs > 0:
                tabs_count += 1
            elif leading_spaces > 0:
                spaces_count += 1
                if leading_spaces % 2 == 0:
                    indent_sizes.append(leading_spaces)
        
        if tabs_count > spaces_count:
            self.indent_type = "tabs"
            self.indent_size = 1
        else:
            self.indent_type = "spaces"
            if indent_sizes:
                from collections import Counter
                size_diffs = []
                sorted_sizes = sorted(set(indent_sizes))
                for i in range(1, len(sorted_sizes)):
                    size_diffs.append(sorted_sizes[i] - sorted_sizes[i-1])
                
                if size_diffs:
                    common_diff = Counter(size_diffs).most_common(1)[0][0]
                    self.indent_size = common_diff
                else:
                    self.indent_size = 4
            else:
                self.indent_size = 4
    
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
        for match in re.finditer(r'\bdef\s+(\w+)', code):
            identifiers.add(match.group(1))
        
        for match in re.finditer(r'\bclass\s+(\w+)', code):
            identifiers.add(match.group(1))
        
        for match in re.finditer(r'\b([a-zA-Z_]\w*)\s*=', code):
            identifiers.add(match.group(1))
        
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
        
        type_hints = [
            'List', 'Dict', 'Set', 'Tuple', 'Optional', 'Union', 'Any', 'Callable',
            'Iterable', 'Iterator', 'Sequence', 'Mapping', 'Type', 'TypeVar',
            'Generic', 'Protocol', 'Literal', 'Final', 'ClassVar', 'cast',
            'list', 'dict', 'set', 'tuple',
        ]
        
        return_patterns = [
            '-> None:', '-> str:', '-> int:', '-> float:', '-> bool:',
            '-> list:', '-> dict:', '-> tuple:', '-> List[str]:', '-> List[int]:',
            '-> Dict[str, Any]:', '-> Optional[str]:', '-> Optional[int]:',
        ]
        
        identifiers.update(keywords)
        identifiers.update(builtins)
        identifiers.update(type_hints)
        identifiers.update(return_patterns)
        
        self.completion_model.setStringList(sorted(identifiers))
    
    def insert_completion(self, completion):
        """Insert the selected completion"""
        cursor = self.textCursor()
        
        prefix = self.completer.completionPrefix()
        
        for _ in range(len(prefix)):
            cursor.deletePreviousChar()
        
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
        
        if event.key() == Qt.Key_Control:
            self.ctrl_pressed = True
            self.viewport().setCursor(Qt.IBeamCursor)
        
        if self.completer.popup().isVisible():
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
        
        if self.auto_detect_indent and self.toPlainText():
            self.detect_indentation()
            self.auto_detect_indent = False
        
        cursor = self.textCursor()
        
        if event.key() in (Qt.Key_Return, Qt.Key_Enter):
            cursor = self.textCursor()
            cursor.select(QTextCursor.LineUnderCursor)
            current_line = cursor.selectedText()
            
            indent_level = self.get_line_indentation(current_line)
            stripped_line = current_line.rstrip()
            if stripped_line.endswith(':'):
                indent_level += 1
            
            cursor = self.textCursor()
            super().keyPressEvent(event)
            
            indent_str = self.create_indent_string(indent_level)
            self.insertPlainText(indent_str)
            
            return
        
        elif event.key() == Qt.Key_Tab:
            cursor = self.textCursor()
            if cursor.hasSelection():
                # Indent selected lines
                self.indent_selected_lines()
            else:
                # Insert tab/spaces at cursor
                if self.indent_type == "tabs":
                    self.insertPlainText('\t')
                else:
                    self.insertPlainText(' ' * self.indent_size)
            return
        
        elif event.key() == Qt.Key_Backtab:
            cursor = self.textCursor()
            if cursor.hasSelection():
                # Unindent selected lines
                self.unindent_selected_lines()
            else:
                # Unindent current line
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
        
        elif event.key() == Qt.Key_Backspace:
            cursor = self.textCursor()
            cursor.select(QTextCursor.LineUnderCursor)
            line = cursor.selectedText()
            
            pos = self.textCursor().positionInBlock()
            
            if pos > 0 and line[:pos].strip() == '':
                if self.indent_type == "spaces" and pos >= self.indent_size:
                    if pos % self.indent_size == 0:
                        cursor = self.textCursor()
                        for _ in range(self.indent_size):
                            cursor.deletePreviousChar()
                        return
        
        super().keyPressEvent(event)
        
        if event.text() == ':' or event.text() == ')':
            self.check_type_hint_insertion()
        
        cursor = self.textCursor()
        cursor.movePosition(QTextCursor.Right, QTextCursor.KeepAnchor)
        if cursor.selectedText().strip():
            self.completer.popup().hide()
            return
        
        completion_prefix = self.text_under_cursor()
        if len(completion_prefix) >= 2:
            if completion_prefix != self.completer.completionPrefix():
                self.completer.setCompletionPrefix(completion_prefix)
                popup = self.completer.popup()
                popup.setCurrentIndex(self.completer.completionModel().index(0, 0))
            
            cursor_rect = self.cursorRect()
            cursor_rect.setWidth(self.completer.popup().sizeHintForColumn(0)
                               + self.completer.popup().verticalScrollBar().sizeHint().width())
            self.completer.complete(cursor_rect)
        else:
            self.completer.popup().hide()
    
    def indent_selected_lines(self):
        """Indent all selected lines"""
        cursor = self.textCursor()
        start = cursor.selectionStart()
        end = cursor.selectionEnd()
        
        # Move to start of selection
        cursor.setPosition(start)
        cursor.movePosition(QTextCursor.StartOfLine)
        start_block = cursor.blockNumber()
        
        # Move to end of selection
        cursor.setPosition(end)
        end_block = cursor.blockNumber()
        
        # Indent each line
        cursor.beginEditBlock()
        for block_num in range(start_block, end_block + 1):
            cursor.setPosition(self.document().findBlockByNumber(block_num).position())
            if self.indent_type == "tabs":
                cursor.insertText('\t')
            else:
                cursor.insertText(' ' * self.indent_size)
        cursor.endEditBlock()
    
    def unindent_selected_lines(self):
        """Unindent all selected lines"""
        cursor = self.textCursor()
        start = cursor.selectionStart()
        end = cursor.selectionEnd()
        
        # Move to start of selection
        cursor.setPosition(start)
        cursor.movePosition(QTextCursor.StartOfLine)
        start_block = cursor.blockNumber()
        
        # Move to end of selection
        cursor.setPosition(end)
        end_block = cursor.blockNumber()
        
        # Unindent each line
        cursor.beginEditBlock()
        for block_num in range(start_block, end_block + 1):
            block = self.document().findBlockByNumber(block_num)
            cursor.setPosition(block.position())
            line_text = block.text()
            
            if self.indent_type == "tabs" and line_text.startswith('\t'):
                cursor.deleteChar()
            elif self.indent_type == "spaces":
                spaces_to_remove = min(self.indent_size, len(line_text) - len(line_text.lstrip(' ')))
                for _ in range(spaces_to_remove):
                    if cursor.position() < block.position() + block.length() - 1:
                        char = self.document().characterAt(cursor.position())
                        if char == ' ':
                            cursor.deleteChar()
                        else:
                            break
        cursor.endEditBlock()
    
    def check_type_hint_insertion(self):
        """Check if we should insert type hint template"""
        cursor = self.textCursor()
        cursor.select(QTextCursor.LineUnderCursor)
        line = cursor.selectedText()
        
        if re.match(r'^\s*def\s+\w+\([^)]*\)\s*:\s*$', line):
            if '->' not in line:
                cursor = self.textCursor()
                block_text = cursor.block().text()
                colon_pos = block_text.rfind(':')
                if colon_pos != -1:
                    cursor.movePosition(QTextCursor.StartOfLine)
                    cursor.movePosition(QTextCursor.Right, QTextCursor.MoveAnchor, colon_pos)
                    cursor.insertText(' -> None')
                    cursor.movePosition(QTextCursor.Right)
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
        
        patterns = [
            rf'^\s*def\s+{re.escape(identifier)}\s*\(',
            rf'^\s*class\s+{re.escape(identifier)}\s*[\(:]',
            rf'^\s*{re.escape(identifier)}\s*=',
        ]
        
        for line_num, line in enumerate(lines):
            for pattern in patterns:
                if re.search(pattern, line):
                    cursor = QTextCursor(self.document().findBlockByLineNumber(line_num))
                    self.setTextCursor(cursor)
                    self.centerCursor()
                    self.highlight_line(line_num)
                    return
    
    def jump_to_line(self, line_num):
        """Jump to a specific line number (0-based)"""
        if line_num < 0:
            return
        
        cursor = QTextCursor(self.document().findBlockByLineNumber(line_num))
        self.setTextCursor(cursor)
        self.centerCursor()
        self.highlight_line(line_num)
    
    def highlight_line(self, line_num):
        """Briefly highlight a line"""
        cursor = QTextCursor(self.document().findBlockByLineNumber(line_num))
        cursor.select(QTextCursor.LineUnderCursor)
        
        selection = QTextEdit.ExtraSelection()
        if self.is_dark_mode:
            selection.format.setBackground(QColor("#3A3A3A"))
        else:
            selection.format.setBackground(QColor("#FFFF00"))
        selection.cursor = cursor
        
        self.setExtraSelections([selection])
        
        QTimer.singleShot(1000, lambda: self.setExtraSelections([]))


class OutputConsole(QTextEdit):
    """Custom output console with Ctrl+Click error navigation"""
    
    def __init__(self, editor, parent=None):
        super().__init__(parent)
        self.editor = editor
        self.ctrl_pressed = False
        self.setMouseTracking(True)
        self.setReadOnly(True)
        self.is_dark_mode = True
        
        # Set dark theme
        font = QFont("Consolas", 9)
        if not font.exactMatch():
            font = QFont("Courier New", 9)
        self.setFont(font)
        self.apply_theme()
    
    def apply_theme(self):
        """Apply current theme"""
        if self.is_dark_mode:
            self.setStyleSheet("background-color: #1E1E1E; color: #D4D4D4;")
        else:
            self.setStyleSheet("background-color: #FFFFFF; color: #000000;")
    
    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Control:
            self.ctrl_pressed = True
            self.viewport().setCursor(Qt.PointingHandCursor)
        super().keyPressEvent(event)
    
    def keyReleaseEvent(self, event):
        if event.key() == Qt.Key_Control:
            self.ctrl_pressed = False
            self.viewport().setCursor(Qt.IBeamCursor)
        super().keyReleaseEvent(event)
    
    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton and self.ctrl_pressed:
            # Get the text cursor at click position
            cursor = self.cursorForPosition(event.pos())
            cursor.select(QTextCursor.LineUnderCursor)
            line_text = cursor.selectedText()
            
            # Parse line number from error message
            # Look for patterns like "line 123," or "line 123,"
            match = re.search(r'line\s+(\d+)', line_text)
            if match:
                line_num = int(match.group(1))
                # Jump to that line in the editor (convert to 0-based)
                self.editor.jump_to_line(line_num - 1)
                # Bring focus back to editor
                self.editor.setFocus()
                return
        
        super().mousePressEvent(event)
    
    def mouseMoveEvent(self, event):
        if self.ctrl_pressed:
            cursor = self.cursorForPosition(event.pos())
            cursor.select(QTextCursor.LineUnderCursor)
            line_text = cursor.selectedText()
            
            # Check if this line contains a line number reference
            if re.search(r'line\s+\d+', line_text):
                self.viewport().setCursor(Qt.PointingHandCursor)
            else:
                self.viewport().setCursor(Qt.IBeamCursor)
        else:
            self.viewport().setCursor(Qt.IBeamCursor)
        
        super().mouseMoveEvent(event)


class FindDialog(QDialog):
    """Find and Replace dialog"""
    
    def __init__(self, editor, parent=None):
        super().__init__(parent)
        self.editor = editor
        self.last_match_pos = -1
        self.init_ui()
    
    def init_ui(self):
        """Initialize the UI"""
        self.setWindowTitle("Find")
        self.setModal(False)
        layout = QVBoxLayout()
        
        # Find section
        find_layout = QHBoxLayout()
        find_layout.addWidget(QLabel("Find:"))
        self.find_input = QLineEdit()
        self.find_input.returnPressed.connect(self.find_next)
        find_layout.addWidget(self.find_input)
        layout.addLayout(find_layout)
        
        # Replace section
        replace_layout = QHBoxLayout()
        replace_layout.addWidget(QLabel("Replace:"))
        self.replace_input = QLineEdit()
        replace_layout.addWidget(self.replace_input)
        layout.addLayout(replace_layout)
        
        # Options
        options_layout = QHBoxLayout()
        self.case_sensitive = QCheckBox("Case sensitive")
        self.whole_word = QCheckBox("Whole words")
        self.use_regex = QCheckBox("Regex")
        options_layout.addWidget(self.case_sensitive)
        options_layout.addWidget(self.whole_word)
        options_layout.addWidget(self.use_regex)
        layout.addLayout(options_layout)
        
        # Buttons
        button_layout = QHBoxLayout()
        
        find_next_btn = QPushButton("Find Next")
        find_next_btn.clicked.connect(self.find_next)
        button_layout.addWidget(find_next_btn)
        
        find_prev_btn = QPushButton("Find Previous")
        find_prev_btn.clicked.connect(self.find_previous)
        button_layout.addWidget(find_prev_btn)
        
        replace_btn = QPushButton("Replace")
        replace_btn.clicked.connect(self.replace_current)
        button_layout.addWidget(replace_btn)
        
        replace_all_btn = QPushButton("Replace All")
        replace_all_btn.clicked.connect(self.replace_all)
        button_layout.addWidget(replace_all_btn)
        
        layout.addLayout(button_layout)
        
        # Status label
        self.status_label = QLabel("")
        layout.addWidget(self.status_label)
        
        self.setLayout(layout)
        self.resize(500, 180)
    
    def get_search_flags(self):
        """Get QTextDocument search flags"""
        flags = QTextDocument.FindFlags()
        if self.case_sensitive.isChecked():
            flags |= QTextDocument.FindCaseSensitively
        if self.whole_word.isChecked():
            flags |= QTextDocument.FindWholeWords
        return flags
    
    def find_next(self):
        """Find next occurrence"""
        search_text = self.find_input.text()
        if not search_text:
            self.status_label.setText("Enter search text")
            return
        
        cursor = self.editor.textCursor()
        
        if self.use_regex.isChecked():
            regex = QRegularExpression(search_text)
            if not self.case_sensitive.isChecked():
                regex.setPatternOptions(QRegularExpression.CaseInsensitiveOption)
            found_cursor = self.editor.document().find(regex, cursor, self.get_search_flags())
        else:
            found_cursor = self.editor.document().find(search_text, cursor, self.get_search_flags())
        
        if found_cursor.isNull():
            # Wrap around to beginning
            cursor.movePosition(QTextCursor.Start)
            if self.use_regex.isChecked():
                regex = QRegularExpression(search_text)
                if not self.case_sensitive.isChecked():
                    regex.setPatternOptions(QRegularExpression.CaseInsensitiveOption)
                found_cursor = self.editor.document().find(regex, cursor, self.get_search_flags())
            else:
                found_cursor = self.editor.document().find(search_text, cursor, self.get_search_flags())
            
            if found_cursor.isNull():
                self.status_label.setText("Not found")
                return
            else:
                self.status_label.setText("Wrapped to beginning")
        else:
            self.status_label.setText("")
        
        self.editor.setTextCursor(found_cursor)
        self.editor.centerCursor()
    
    def find_previous(self):
        """Find previous occurrence"""
        search_text = self.find_input.text()
        if not search_text:
            self.status_label.setText("Enter search text")
            return
        
        cursor = self.editor.textCursor()
        cursor.movePosition(QTextCursor.Start, QTextCursor.MoveAnchor)
        cursor.movePosition(QTextCursor.End, QTextCursor.KeepAnchor)
        current_pos = self.editor.textCursor().selectionStart()
        
        flags = self.get_search_flags()
        flags |= QTextDocument.FindBackward
        
        cursor = self.editor.textCursor()
        
        if self.use_regex.isChecked():
            regex = QRegularExpression(search_text)
            if not self.case_sensitive.isChecked():
                regex.setPatternOptions(QRegularExpression.CaseInsensitiveOption)
            found_cursor = self.editor.document().find(regex, cursor, flags)
        else:
            found_cursor = self.editor.document().find(search_text, cursor, flags)
        
        if found_cursor.isNull():
            # Wrap around to end
            cursor.movePosition(QTextCursor.End)
            if self.use_regex.isChecked():
                regex = QRegularExpression(search_text)
                if not self.case_sensitive.isChecked():
                    regex.setPatternOptions(QRegularExpression.CaseInsensitiveOption)
                found_cursor = self.editor.document().find(regex, cursor, flags)
            else:
                found_cursor = self.editor.document().find(search_text, cursor, flags)
            
            if found_cursor.isNull():
                self.status_label.setText("Not found")
                return
            else:
                self.status_label.setText("Wrapped to end")
        else:
            self.status_label.setText("")
        
        self.editor.setTextCursor(found_cursor)
        self.editor.centerCursor()
    
    def replace_current(self):
        """Replace current selection"""
        cursor = self.editor.textCursor()
        if cursor.hasSelection():
            replace_text = self.replace_input.text()
            cursor.insertText(replace_text)
            self.status_label.setText("Replaced")
            self.find_next()
    
    def replace_all(self):
        """Replace all occurrences"""
        search_text = self.find_input.text()
        replace_text = self.replace_input.text()
        
        if not search_text:
            self.status_label.setText("Enter search text")
            return
        
        cursor = self.editor.textCursor()
        cursor.beginEditBlock()
        
        cursor.movePosition(QTextCursor.Start)
        self.editor.setTextCursor(cursor)
        
        count = 0
        flags = self.get_search_flags()
        
        while True:
            if self.use_regex.isChecked():
                regex = QRegularExpression(search_text)
                if not self.case_sensitive.isChecked():
                    regex.setPatternOptions(QRegularExpression.CaseInsensitiveOption)
                found_cursor = self.editor.document().find(regex, cursor, flags)
            else:
                found_cursor = self.editor.document().find(search_text, cursor, flags)
            
            if found_cursor.isNull():
                break
            
            found_cursor.insertText(replace_text)
            cursor = found_cursor
            count += 1
        
        cursor.endEditBlock()
        self.status_label.setText(f"Replaced {count} occurrence(s)")
    
    def showEvent(self, event):
        """When dialog is shown, select text in find input and focus it"""
        super().showEvent(event)
        self.find_input.setFocus()
        self.find_input.selectAll()


class PythonEditor(QMainWindow):
    """Main editor window"""
    
    def __init__(self):
        super().__init__()
        
        self.current_file = None
        self.process = None
        self.find_dialog = None
        self.active_venv = None
        self.load_venv_preference()
        self.init_ui()
    
    def load_venv_preference(self):
        """Load venv preference from file"""
        try:
            with open('.microid_venv', 'r') as f:
                venv_path = f.read().strip()
                if venv_path and os.path.exists(venv_path):
                    self.active_venv = venv_path
        except:
            pass
    
    def save_venv_preference(self):
        """Save venv preference to file"""
        try:
            with open('.microid_venv', 'w') as f:
                f.write(self.active_venv if self.active_venv else '')
        except:
            pass
    
    def get_python_executable(self):
        """Get the Python executable to use (venv or system)"""
        if self.active_venv:
            if sys.platform == "win32":
                python_exe = os.path.join(self.active_venv, "Scripts", "python.exe")
            else:
                python_exe = os.path.join(self.active_venv, "bin", "python")
            
            if os.path.exists(python_exe):
                return python_exe
        
        return sys.executable
    
    def init_ui(self):
        """Initialize the user interface"""
        self.setWindowTitle("Microid")
        self.setGeometry(100, 100, 900, 700)
        
        # Create splitter for editor and output
        splitter = QSplitter(Qt.Vertical)
        
        # Create editor
        self.editor = CodeEditor()
        splitter.addWidget(self.editor)
        
        # Create output console with error navigation
        self.output = OutputConsole(self.editor)
        splitter.addWidget(self.output)
        
        # Set splitter sizes
        splitter.setSizes([500, 200])
        
        self.setCentralWidget(splitter)
        
        # Track modifications
        self.editor.document().modificationChanged.connect(self.on_modification_changed)
        
        # Track cursor position and text changes for statistics
        self.editor.cursorPositionChanged.connect(self.update_status_bar)
        self.editor.textChanged.connect(self.update_status_bar)
        
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
        
        # Virtual Environment action
        self.venv_action = QAction("🐍 Venv: None", self)
        self.venv_action.triggered.connect(self.manage_venv)
        toolbar.addAction(self.venv_action)
        self.update_venv_button()
        
        toolbar.addSeparator()
        
        # Find action
        find_action = QAction("Find", self)
        find_action.setShortcut("Ctrl+F")
        find_action.triggered.connect(self.show_find_dialog)
        toolbar.addAction(find_action)
        
        # Go to line action
        goto_action = QAction("Go to Line", self)
        goto_action.setShortcut("Ctrl+G")
        goto_action.triggered.connect(self.go_to_line)
        toolbar.addAction(goto_action)
        
        toolbar.addSeparator()
        
        # Theme toggle action
        self.theme_action = QAction("🌙 Dark Mode", self)
        self.theme_action.triggered.connect(self.toggle_theme)
        toolbar.addAction(self.theme_action)
        self.update_theme_button()
        
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
    
    def manage_venv(self):
        """Open virtual environment manager dialog"""
        dialog = VenvDialog(self.active_venv, self)
        if dialog.exec():
            self.active_venv = dialog.selected_venv
            self.save_venv_preference()
            self.update_venv_button()
            
            if self.active_venv:
                self.append_output(f"Activated virtual environment: {self.active_venv}", "#6A8759")
            else:
                self.append_output("Deactivated virtual environment", "#FFC66D")
    
    def update_venv_button(self):
        """Update venv button text"""
        if self.active_venv:
            venv_name = os.path.basename(self.active_venv)
            self.venv_action.setText(f"🐍 Venv: {venv_name}")
            self.venv_action.setToolTip(self.active_venv)
        else:
            self.venv_action.setText("🐍 Venv: None")
            self.venv_action.setToolTip("No virtual environment active")
    
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
        cursor = self.editor.textCursor()
        line = cursor.blockNumber() + 1
        col = cursor.columnNumber() + 1
        
        total_lines = self.editor.document().blockCount()
        total_chars = len(self.editor.toPlainText())
        
        indent_info = f"{self.editor.indent_type.capitalize()} ({self.editor.indent_size})"
        
        venv_info = ""
        if self.active_venv:
            venv_name = os.path.basename(self.active_venv)
            venv_info = f" | Venv: {venv_name}"
        
        status = f"Line {line}/{total_lines} | Col {col} | {total_chars} chars | Indent: {indent_info}{venv_info}"
        self.statusBar.showMessage(status)
        
        if self.editor.indent_type == "spaces":
            self.indent_action.setText(f"Indent: Spaces ({self.editor.indent_size})")
        else:
            self.indent_action.setText("Indent: Tabs")
    
    def show_find_dialog(self):
        """Show the find/replace dialog"""
        if self.find_dialog is None:
            self.find_dialog = FindDialog(self.editor, self)
        
        # Get selected text if any
        cursor = self.editor.textCursor()
        if cursor.hasSelection():
            self.find_dialog.find_input.setText(cursor.selectedText())
        
        self.find_dialog.show()
        self.find_dialog.raise_()
        self.find_dialog.activateWindow()
    
    def toggle_theme(self):
        """Toggle between light and dark theme"""
        self.editor.toggle_theme()
        self.output.is_dark_mode = self.editor.is_dark_mode
        self.output.apply_theme()
        
        # Update main window palette
        if self.editor.is_dark_mode:
            set_dark_palette(QApplication.instance())
        else:
            set_light_palette(QApplication.instance())
        
        self.update_theme_button()
    
    def update_theme_button(self):
        """Update theme button text"""
        if self.editor.is_dark_mode:
            self.theme_action.setText("☀️ Light Mode")
        else:
            self.theme_action.setText("🌙 Dark Mode")
    
    def clear_output(self):
        """Clear the output console"""
        self.output.clear()
    
    def add_typing_import(self):
        """Add 'from typing import' statement at top of file"""
        code = self.editor.toPlainText()
        
        if re.search(r'from\s+typing\s+import', code):
            self.append_output("Typing import already exists", "#FFC66D")
            return
        
        typing_imports = "from typing import List, Dict, Optional, Union, Any, Tuple, Set, Callable"
        
        lines = code.split('\n')
        insert_line = 0
        
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
            
            if line.strip().startswith('import ') or line.strip().startswith('from '):
                insert_line = i + 1
            elif line.strip() and not line.strip().startswith('#'):
                break
        
        lines.insert(insert_line, typing_imports)
        self.editor.setPlainText('\n'.join(lines))
        self.append_output("Added typing imports", "#6A8759")
    
    def go_to_line(self):
        """Open dialog to go to a specific line"""
        total_lines = self.editor.document().blockCount()
        current_line = self.editor.textCursor().blockNumber() + 1
        
        line_num, ok = QInputDialog.getInt(
            self,
            "Go to Line",
            f"Line number (1-{total_lines}):",
            current_line,
            1,
            total_lines,
            1
        )
        
        if ok:
            cursor = QTextCursor(self.editor.document().findBlockByLineNumber(line_num - 1))
            self.editor.setTextCursor(cursor)
            self.editor.centerCursor()
            self.editor.highlight_line(line_num - 1)
    
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
        
        try:
            ast.parse(code)
        except SyntaxError as e:
            self.append_output("=" * 50, "#808080")
            self.append_output("Cannot run - Syntax Error:", "#FF6B6B")
            self.append_output(f"  Line {e.lineno}: {e.msg}", "#FF6B6B")
            self.append_output("=" * 50, "#808080")
            return
        
        python_exe = self.get_python_executable()
        
        self.append_output("=" * 50, "#808080")
        if self.active_venv:
            venv_name = os.path.basename(self.active_venv)
            self.append_output(f"Running code with venv: {venv_name}...", "#6897BB")
        else:
            self.append_output("Running code...", "#6897BB")
        self.append_output(f"Python: {python_exe}", "#808080")
        self.append_output("", "#D4D4D4")
        
        try:
            with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False, encoding='utf-8') as f:
                f.write(code)
                temp_file = f.name
            
            self.process = QProcess(self)
            self.process.readyReadStandardOutput.connect(self.handle_stdout)
            self.process.readyReadStandardError.connect(self.handle_stderr)
            self.process.finished.connect(lambda: self.handle_finished(temp_file))
            
            self.process.start(python_exe, [temp_file])
            
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
            
            try:
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


def set_light_palette(app):
    """Set light theme palette for the entire application"""
    palette = QPalette()
    
    # Base colors
    palette.setColor(QPalette.Window, QColor("#F0F0F0"))
    palette.setColor(QPalette.WindowText, QColor("#000000"))
    palette.setColor(QPalette.Base, QColor("#FFFFFF"))
    palette.setColor(QPalette.AlternateBase, QColor("#F5F5F5"))
    palette.setColor(QPalette.ToolTipBase, QColor("#FFFFCC"))
    palette.setColor(QPalette.ToolTipText, QColor("#000000"))
    palette.setColor(QPalette.Text, QColor("#000000"))
    palette.setColor(QPalette.Button, QColor("#E1E1E1"))
    palette.setColor(QPalette.ButtonText, QColor("#000000"))
    palette.setColor(QPalette.BrightText, Qt.red)
    palette.setColor(QPalette.Link, QColor("#0000FF"))
    palette.setColor(QPalette.Highlight, QColor("#308CC6"))
    palette.setColor(QPalette.HighlightedText, QColor("#FFFFFF"))
    
    # Disabled colors
    palette.setColor(QPalette.Disabled, QPalette.WindowText, QColor("#808080"))
    palette.setColor(QPalette.Disabled, QPalette.Text, QColor("#808080"))
    palette.setColor(QPalette.Disabled, QPalette.ButtonText, QColor("#808080"))
    palette.setColor(QPalette.Disabled, QPalette.HighlightedText, QColor("#808080"))
    
    app.setPalette(palette)


def set_dark_palette(app):
    """Set dark theme palette for the entire application"""
    palette = QPalette()
    
    # Base colors
    palette.setColor(QPalette.Window, QColor("#1E1E1E"))
    palette.setColor(QPalette.WindowText, QColor("#D4D4D4"))
    palette.setColor(QPalette.Base, QColor("#1E1E1E"))
    palette.setColor(QPalette.AlternateBase, QColor("#2B2B2B"))
    palette.setColor(QPalette.ToolTipBase, QColor("#1E1E1E"))
    palette.setColor(QPalette.ToolTipText, QColor("#D4D4D4"))
    palette.setColor(QPalette.Text, QColor("#D4D4D4"))
    palette.setColor(QPalette.Button, QColor("#2B2B2B"))
    palette.setColor(QPalette.ButtonText, QColor("#D4D4D4"))
    palette.setColor(QPalette.BrightText, Qt.red)
    palette.setColor(QPalette.Link, QColor("#6897BB"))
    palette.setColor(QPalette.Highlight, QColor("#214283"))
    palette.setColor(QPalette.HighlightedText, QColor("#FFFFFF"))
    
    # Disabled colors
    palette.setColor(QPalette.Disabled, QPalette.WindowText, QColor("#808080"))
    palette.setColor(QPalette.Disabled, QPalette.Text, QColor("#808080"))
    palette.setColor(QPalette.Disabled, QPalette.ButtonText, QColor("#808080"))
    palette.setColor(QPalette.Disabled, QPalette.HighlightedText, QColor("#808080"))
    
    app.setPalette(palette)


def main():
    app = QApplication(sys.argv)
    
    # Set Fusion style
    app.setStyle("Fusion")
    
    # Create editor first to check theme preference
    editor = PythonEditor()
    
    # Set theme based on editor preference
    if editor.editor.is_dark_mode:
        set_dark_palette(app)
    else:
        set_light_palette(app)
    
    editor.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()