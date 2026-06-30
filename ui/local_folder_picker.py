import platform
import string
from pathlib import Path
from nicegui import events, ui


class local_folder_picker(ui.dialog):
    def __init__(self, directory: str, *, upper_limit: str | None = None, show_hidden_files: bool = False) -> None:
        """Local Folder Picker Dialog.

        :param directory: The directory to start in.
        :param upper_limit: The directory to stop at (None: no limit).
        :param show_hidden_files: Whether to show hidden files/folders.
        """
        super().__init__()
        
        # Start directory resolution
        start_path = Path(directory).expanduser().resolve() if directory else Path(".").resolve()
        if not start_path.exists() or not start_path.is_dir():
            start_path = Path(".").resolve()
            
        self.path = start_path
        self.upper_limit = Path(upper_limit).expanduser().resolve() if upper_limit else None
        self.show_hidden_files = show_hidden_files

        with self, ui.card().classes("w-[450px] h-[550px] flex flex-col p-4"):
            ui.label("Select Directory").classes("text-base font-bold text-gray-900 dark:text-white mb-1")
            
            # Show current path path at top
            self.header = ui.label().classes("text-xs text-indigo-600 dark:text-indigo-400 font-mono break-all w-full mb-2 bg-gray-50 dark:bg-gray-950 p-2 rounded border border-gray-200 dark:border-gray-800")
            
            self.add_drives_toggle()
            
            # Search Input to filter folders
            self.search_input = ui.input(
                placeholder="Search folders...",
                on_change=lambda: self.update_grid()
            ).classes("w-full mb-2 text-xs").props("clearable")
            
            # Grid for displaying folders
            self.grid = ui.aggrid({
                "columnDefs": [{"field": "name", "headerName": "Folder", "flex": 1}],
                "rowSelection": "single",
                "domLayout": "normal",
            }).classes("flex-1 w-full border border-gray-200 dark:border-gray-800 rounded").on("cellDoubleClicked", self.handle_double_click)
            
            with ui.row().classes("w-full justify-between items-center mt-3 gap-2"):
                ui.button("Select Folder", on_click=self.handle_ok).classes("bg-indigo-600 text-white text-xs px-4 py-2")
                with ui.row().classes("gap-2"):
                    ui.button("Cancel", on_click=self.close).props("outline").classes("text-xs")
        
        self.update_grid()

    def add_drives_toggle(self) -> None:
        if platform.system() == "Windows":
            drives = []
            try:
                import win32api
                drives = win32api.GetLogicalDriveStrings().split("\000")[:-1]
            except ImportError:
                for letter in string.ascii_uppercase:
                    drive = f"{letter}:\\"
                    if Path(drive).exists():
                        drives.append(drive)
            
            if drives:
                # Find current drive
                current_drive = ""
                for d in drives:
                    if str(self.path).lower().startswith(d.lower()):
                        current_drive = d
                        break
                if not current_drive:
                    current_drive = drives[0]
                
                with ui.row().classes("w-full items-center mb-2 gap-2"):
                    ui.label("Drive:").classes("text-xs text-gray-600 dark:text-gray-400")
                    self.drives_toggle = ui.toggle(
                        drives, 
                        value=current_drive, 
                        on_change=self.update_drive
                    ).classes("text-xs")

    def update_drive(self) -> None:
        self.path = Path(self.drives_toggle.value).expanduser().resolve()
        self.update_grid()

    def update_grid(self) -> None:
        self.header.set_text(str(self.path))
        
        row_data = []
        
        # Add parent directory navigation if not at upper limit/root
        if self.upper_limit is None or self.path != self.upper_limit:
            if self.path.parent != self.path:
                row_data.append({"name": "📁 ..", "path": str(self.path.parent)})
        
        try:
            # Find subdirectories
            paths = [p for p in self.path.iterdir() if p.is_dir()]
            if not self.show_hidden_files:
                paths = [p for p in paths if not p.name.startswith(".")]
            
            # Apply search filter
            if hasattr(self, "search_input") and self.search_input.value:
                query = self.search_input.value.strip().lower()
                if query:
                    paths = [p for p in paths if query in p.name.lower()]

            paths.sort(key=lambda p: p.name.lower())
            
            for p in paths:
                row_data.append({"name": f"📁 {p.name}", "path": str(p)})
        except Exception as e:
            ui.notify(f"Could not list directory: {e}", type="negative")
            
        self.grid.options["rowData"] = row_data
        self.grid.update()

    def handle_double_click(self, e: events.GenericEventArguments) -> None:
        path_str = e.args["data"]["path"]
        self.path = Path(path_str).resolve()
        
        # Clear search input when navigating
        if hasattr(self, "search_input"):
            self.search_input.value = ""
            
        # Update drive toggle selected value if drive changes
        if platform.system() == "Windows" and hasattr(self, "drives_toggle"):
            for d in self.drives_toggle.options:
                if str(self.path).lower().startswith(d.lower()):
                    self.drives_toggle.value = d
                    break
                    
        self.update_grid()

    def handle_ok(self) -> None:
        self.submit(str(self.path))
