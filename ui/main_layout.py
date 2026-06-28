# ui/main_layout.py
from nicegui import ui
from services.confluence_config import ConfluenceConfig
from services.file_tracker import FileTracker, FileInfo


class MainLayout:
    def __init__(self, config: ConfluenceConfig, tracker: FileTracker):
        self.config = config
        self.tracker = tracker
        self.selected_file: FileInfo | None = None
        self.files: list[FileInfo] = []
        self._log_label = None
        self._detail_container = None
        self._file_list_container = None
        self._status_label = None

    def build(self):
        with ui.header().classes("items-center gap-2 px-4 py-2 bg-gray-900"):
            ui.label("md2confluence").classes("text-indigo-400 font-bold text-sm")
            self._dir_input = ui.input(
                placeholder="Select directory…",
                value=self.config.last_directory,
            ).classes("flex-1 max-w-xs text-xs")
            ui.button("Browse…", on_click=self._browse).classes("text-xs")
            ui.button("⟳ Refresh", on_click=self._refresh).classes("text-xs").tooltip(
                "Rescan directory and recompute sync status (no API calls)"
            )
            ui.space()
            ui.button("⬇ Download Page…", on_click=self._open_download_dialog).classes("text-xs")
            ui.button("⚙ Config", on_click=lambda: ui.navigate.to("/config")).classes("text-xs")

        with ui.splitter(value=28).classes("w-full flex-1") as splitter:
            with splitter.before:
                self._file_list_container = ui.column().classes("w-full h-full")
                self._build_file_panel()
            with splitter.after:
                self._detail_container = ui.column().classes("w-full h-full p-4")
                self._build_detail_panel()

        with ui.footer().classes("px-4 py-1 bg-gray-950 text-xs text-gray-500 flex gap-4"):
            self._conn_dot = ui.label("● Connected").classes("text-green-400")
            ui.label(self.config.cloud_domain or self.config.server_url or "")
            ui.space()
            self._status_label = ui.label("No directory loaded")

    # Stubs — filled in Tasks 8, 9, 10
    def _build_file_panel(self): pass
    def _build_detail_panel(self): pass
    def _open_download_dialog(self): pass

    def _rebuild_file_list(self):
        if self._file_list_container:
            self._file_list_container.clear()
            with self._file_list_container:
                self._build_file_panel()

    def _rebuild_detail(self):
        if self._detail_container:
            self._detail_container.clear()
            with self._detail_container:
                self._build_detail_panel()

    def _browse(self):
        async def _pick():
            result = await ui.run_javascript(
                'window.__dir = prompt("Enter directory path:"); window.__dir;'
            )
            if result:
                self._dir_input.value = result
                self.config.last_directory = result
                self.config.save()
                self._refresh()
        import asyncio
        asyncio.ensure_future(_pick())

    def _refresh(self):
        directory = self._dir_input.value.strip()
        if not directory:
            return
        from pathlib import Path
        self.files = self.tracker.scan(Path(directory))
        counts = {s: 0 for s in ["synced", "modified_locally", "not_linked", "failed"]}
        for f in self.files:
            counts[f.status.value] = counts.get(f.status.value, 0) + 1
        if self._status_label:
            self._status_label.set_text(
                f"{counts['synced']} synced · {counts['modified_locally']} modified · "
                f"{counts['not_linked']} unlinked · {counts['failed']} error"
            )
        self._rebuild_file_list()
