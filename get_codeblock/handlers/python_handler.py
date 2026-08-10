"""Python language handler for get_codeblock."""


class PythonHandler:
    """Handles Python code block detection using indentation and keywords."""

    BLOCK_KEYWORDS = ("def ", "class ", "if ", "elif ", "else:", "for ", "while ", 
                      "try:", "except", "finally:", "with ")

    def get_blocks(self, file_path, line_num):
        """Get all code blocks containing the specified line.

        Returns list of blocks sorted by level (0=outermost).
        """
        with open(file_path, "r", encoding="utf-8") as f:
            lines = f.readlines()

        if line_num < 1 or line_num > len(lines):
            return []

        # Build block structure using indentation and keywords
        block_starts = self._find_block_starts(lines)

        # Find which blocks contain line_num
        result = [b for b in block_starts if b["start"] <= line_num <= b["end"]]

        return result

    def _find_block_starts(self, lines):
        """Find all block starts and their ranges based on indentation."""
        blocks = []
        
        # Track open paren/bracket levels for multi-line constructs
        paren_depth = 0
        
        for i in range(len(lines)):
            line = lines[i]
            stripped = line.rstrip("\n\r")
            
            # Calculate current indent (spaces only)
            indent = len(line) - len(line.lstrip(" "))
            
            # Track parentheses/brackets depth
            paren_depth += stripped.count("(") + stripped.count("[")
            paren_depth -= stripped.count(")") + stripped.count("]")
            
            # Check if this is a block start keyword
            for kw in self.BLOCK_KEYWORDS:
                if stripped.lstrip().startswith(kw):
                    start_line = i + 1  # 1-indexed
                    
                    # Find end of this block by tracking indent
                    end_line = self._find_block_end(lines, i, indent)
                    
                    level = len([b for b in blocks if b["start"] <= i and b["end"] >= i])
                    
                    blocks.append({
                        "type": kw.strip().rstrip(":"),
                        "level": level + 1,
                        "start": start_line,
                        "end": end_line + 1  # inclusive
                    })
                    break
            
            # Handle multi-line imports with parentheses
            if paren_depth > 0 and stripped.lstrip().startswith(("from ", "import ")) \
               and "(" in stripped:
                start_line = i + 1
                
                # Find where this import ends (when we're back at same level or lower)
                end_line = self._find_multi_line_end(lines, i, indent)
                
                blocks.append({
                    "type": "import",
                    "level": 1,
                    "start": start_line,
                    "end": end_line + 1
                })

        return sorted(blocks, key=lambda b: (b["level"], b["start"]))

    def _find_block_end(self, lines, start_idx, base_indent):
        """Find where a block ends by tracking indentation and parentheses."""
        i = start_idx
        paren_depth = 0
        
        while i + 1 < len(lines):
            next_line = lines[i + 1]
            stripped = next_line.rstrip("\n\r")
            
            # Skip empty lines and comments
            if not stripped.strip() or stripped.lstrip().startswith("#"):
                paren_depth += stripped.count("(") - stripped.count(")")
                i += 1
                continue
            
            # Track parentheses first (before checking indent)
            paren_depth += stripped.count("(") - stripped.count(")")
            
            next_indent = len(next_line) - len(next_line.lstrip(" "))
            
            # Block ends when: at base indent or less AND no unclosed parens
            # BUT we must include the line that closes any open parens
            if next_indent <= base_indent and paren_depth == 0:
                break
            
            i += 1
        
        return i

    def _find_multi_line_end(self, lines, start_idx, base_indent):
        """Find where a multi-line import/construct ends."""
        i = start_idx
        paren_depth = 0
        
        # Count initial parentheses on first line
        first_stripped = lines[start_idx].rstrip("\n\r")
        paren_depth += first_stripped.count("(") - first_stripped.count(")")
        
        while i + 1 < len(lines):
            next_line = lines[i + 1]
            stripped = next_line.rstrip("\n\r")
            
            # Skip empty lines and comments
            if not stripped.strip() or stripped.lstrip().startswith("#"):
                i += 1
                continue
            
            next_indent = len(next_line) - len(next_line.lstrip(" "))
            
            # Count parentheses
            paren_depth += stripped.count("(") - stripped.count(")")
            
            # If parentheses closed or we're back at base indent, done
            if paren_depth <= 0 or (next_indent <= base_indent and "(" not in stripped):
                break
            
            i += 1
        
        return i
