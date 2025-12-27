import sys
import os

try:
    from InquirerPy import inquirer
    from InquirerPy.base.control import Choice
    from InquirerPy.separator import Separator
    from rich.console import Console
    from rich.style import Style
    from rich.panel import Panel
except ImportError:
    print("Error: Missing dependencies.")
    print("Please install requirements: pip install -r requirements.txt")
    sys.exit(1)

# Keybindings mapping 'escape' to 'interrupt'
# 'q' is removed to allow searching for words with 'q'
kb_select = {
    "interrupt": [{"key": "escape"}]
}

kb_input_esc = {
    "interrupt": [{"key": "escape"}]
}

async def ui_select(message, choices, **kwargs):
    kwargs.setdefault("instruction", "[Esc] Back")
    try:
        # Use select for cursor memory and Separator support
        return await inquirer.select(
            message=message, 
            choices=choices, 
            keybindings=kb_select,
            qmark="",
            amark="",
            **kwargs
        ).execute_async()
    except KeyboardInterrupt:
        return None

async def ui_filter(message, choices, **kwargs):
    """Fuzzy search select for filtering lists."""
    kwargs.setdefault("instruction", "[Type to Search] [Esc] Back")
    
    # inquirer.fuzzy does not support Separator, so we must filter them out
    clean_choices = [c for c in choices if not isinstance(c, Separator)]
    
    try:
        return await inquirer.fuzzy(
            message=message,
            choices=clean_choices,
            keybindings=kb_select,
            qmark="",
            amark="",
            **kwargs
        ).execute_async()
    except KeyboardInterrupt:
        return None

async def ui_text(message, **kwargs):
    try:
        return await inquirer.text(message=message, keybindings=kb_input_esc, **kwargs).execute_async()
    except KeyboardInterrupt:
        return None
