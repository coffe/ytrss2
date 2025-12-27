import sys
import os
import asyncio
import random
from src.utils import clipboard_copy

try:
    from rich.panel import Panel
    from rich.style import Style
    from rich.console import Console, Group
    from rich.align import Align
    from InquirerPy import inquirer
    from InquirerPy.base.control import Choice
    from InquirerPy.separator import Separator
    from rich.columns import Columns
    from rich.text import Text
    from rich.table import Table
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

async def show_fireworks(console):
    from rich.align import Align
    from rich.text import Text
    width = console.size.width
    height = console.size.height
    
    # Simple flashing animation
    colors = ["red", "yellow", "green", "blue", "magenta", "cyan", "white"]
    for _ in range(6):
        console.clear()
        c1 = random.choice(colors)
        c2 = random.choice(colors)
        text = Text("✨  HAPPY NEW YEAR!  ✨", style=f"bold {c1}")
        console.print(Align.center(text, vertical="middle"), height=height)
        await asyncio.sleep(0.2)
    console.clear()

async def show_stats_ui(stats, duration_to_secs_func, secs_to_readable_func, year=None):
    """Renders the statistics dashboard. If year is provided, shows Year in Review."""
    console = Console()
    
    title_text = f"YTRSS INSIGHTS {year}" if year else "YTRSS INSIGHTS"
    
    # Calculate times
    total_seconds = sum(duration_to_secs_func(d) for d in stats['seen_durations'])
    if 'backlog_durations' in stats:
        backlog_seconds = sum(duration_to_secs_func(d) for d in stats['backlog_durations'])
        backlog_time_str = secs_to_readable_func(backlog_seconds)
    else:
        backlog_time_str = "N/A" # No backlog in Year review
    
    total_time_str = secs_to_readable_func(total_seconds)
    
    # Create Panels
    time_panel = Panel(
        Text.assemble(("Total Watch Time\n", "bold cyan"), (f"🕐 {total_time_str}", "white")),
        title="[Time]", border_style="blue"
    )
    
    if year:
         right_panel = Panel(
            Text.assemble(("Year\n", "bold yellow"), (f"📅 {year}", "white")),
            title="[Year]", border_style="yellow"
        )
    else:
        right_panel = Panel(
            Text.assemble(("Backlog Duration\n", "bold yellow"), (f"🎒 {backlog_time_str}", "white")),
            title="[Watch Later]", border_style="yellow"
        )
    
    # Top Channels Table
    table = Table(title=f"🏆 Top Channels {year if year else '(All Time)'}", box=None, header_style="bold magenta")
    table.add_column("Channel", style="white")
    table.add_column("Videos", justify="right", style="green")
    
    for item in stats['top_channels']:
        table.add_row(item['channel'], str(item['count']))
    
    # Layout
    from rich.layout import Layout
    layout = Layout()
    layout.split_column(
        Layout(Columns([time_panel, right_panel]), size=5),
        Layout(Panel(table, border_style="magenta"))
    )
    
    from src.utils import clear_screen
    
    while True:
        clear_screen()
        console.print(Panel(layout, title=f"[bold white]{title_text}[/bold white]", subtitle="Select an action", height=20))
        
        choices = [
            Choice("copy", "   📋  Copy Stats to Clipboard (Social Media)"),
            Choice("back", "   🔙  Back to Main Menu")
        ]
        
        # Only show Year Review option if we are in normal mode
        if not year:
             choices.insert(1, Choice("year_review", "   📅  Year in Review (2025)"))

        selection = await ui_select(message="Options:", choices=choices)
        
        if selection == "back" or selection is None:
            return "back"
        elif selection == "year_review":
            return "year_2025" # Signal caller to switch mode
        elif selection == "copy":
            if year:
                 # Fireworks!
                await show_fireworks(console)
                clear_screen()
                # Redraw panel quickly
                console.print(Panel(layout, title=f"[bold white]{title_text}[/bold white]", subtitle="Stats Copied!", height=20))
            
            # Generate Social Text
            header = f"📺 My YTRSS {year} Year in Review 🎆" if year else "📺 My YTRSS Insights 📊"
            social_text = (
                f"{header}\n\n"
                f"🕐 Total Watch Time: {total_time_str}\n"
            )
            if not year:
                 social_text += f"🎒 Backlog Size:     {backlog_time_str}\n"
            
            social_text += f"\n🏆 Top Channels:\n"
            for i, item in enumerate(stats['top_channels'][:3], 1):
                social_text += f"{i}. {item['channel']} ({item['count']})\n"
            
            social_text += "\n#YTRSS #OpenSource"
            
            clipboard_copy(social_text)
            console.print("Stats copied!", style="bold green")
            await asyncio.sleep(1.2)