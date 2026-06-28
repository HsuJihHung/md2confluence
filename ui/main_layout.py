# ui/main_layout.py
import asyncio
from pathlib import Path
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
        self._dir_input = None
        self._current_view: str = getattr(config, "default_view", "flat")

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
    def _build_file_panel(self):
        with self._file_list_container:
            with ui.row().classes("w-full items-center px-2 py-1 bg-gray-900 border-b border-gray-800 gap-1"):
                ui.label("View:").classes("text-xs text-gray-500")
                ui.button("≡ Flat", on_click=lambda: self._set_view("flat")).classes("text-xs px-2 py-0.5")
                ui.button("⊞ Tree", on_click=lambda: self._set_view("tree")).classes("text-xs px-2 py-0.5")
                ui.space()
                ui.label(f"{len(self.files)} files").classes("text-xs text-gray-500")

            self._flat_container = ui.column().classes("w-full overflow-y-auto")
            self._tree_container = ui.column().classes("w-full overflow-y-auto")

            self._render_flat_list()
            self._render_tree_list()
            self._set_view(self._current_view)

    def _set_view(self, view: str):
        self._current_view = view
        self._flat_container.set_visibility(view == "flat")
        self._tree_container.set_visibility(view == "tree")

    def _render_flat_list(self):
        self._flat_container.clear()
        with self._flat_container:
            for info in self.files:
                self._file_row(info, indent=0)

    def _render_tree_list(self):
        self._tree_container.clear()
        base = Path(self.config.last_directory) if self.config.last_directory else None
        dirs: dict[Path, list] = {}
        for info in self.files:
            dirs.setdefault(info.path.parent, []).append(info)

        with self._tree_container:
            for parent, infos in sorted(dirs.items()):
                try:
                    rel = parent.relative_to(base) if base else parent
                except ValueError:
                    rel = parent
                with ui.row().classes("items-center px-2 py-1 gap-1"):
                    ui.label("▾").classes("text-gray-500 text-xs")
                    ui.label(str(rel) + "/").classes("text-xs text-gray-400 uppercase")
                for info in infos:
                    self._file_row(info, indent=16)

    def _file_row(self, info: "FileInfo", indent: int = 0):
        dot_color = {
            "synced": "bg-green-500",
            "modified_locally": "bg-orange-400",
            "not_linked": "bg-gray-500",
            "failed": "bg-red-500",
        }.get(info.status.value, "bg-gray-500")

        is_selected = self.selected_file is not None and self.selected_file.path == info.path
        row_classes = (
            "w-full flex flex-col px-3 py-2 cursor-pointer border-b border-gray-800 "
            + ("bg-indigo-950" if is_selected else "hover:bg-gray-800")
        )

        with ui.element("div").classes(row_classes).style(f"padding-left:{indent + 12}px").on(
            "click", lambda _, i=info: self._select_file(i)
        ):
            with ui.row().classes("items-center gap-1.5"):
                ui.element("span").classes(f"w-2 h-2 rounded-full flex-shrink-0 {dot_color}")
                ui.label(info.path.name).classes(
                    "text-xs font-bold text-white" if is_selected else "text-xs text-gray-300"
                )
            if info.confluence_id:
                sub = f"ID: {info.confluence_id} · {info.confluence_last_sync[:10] if info.confluence_last_sync else ''}"
            elif info.status.value == "failed":
                sub = "last operation failed"
            else:
                sub = "not linked"
            ui.label(sub).classes("text-xs text-gray-600 ml-3.5")

    def _select_file(self, info: "FileInfo"):
        self.selected_file = info
        # Full re-render is acceptable for the expected scale (< ~500 files).
        self._rebuild_file_list()
        self._rebuild_detail()

    def _build_detail_panel(self):
        if not self.selected_file:
            with self._detail_container:
                with ui.column().classes("w-full h-full items-center justify-center"):
                    ui.label("Select a file to view details").classes("text-gray-500 text-sm")
            return

        info = self.selected_file
        status_colors = {
            "synced": ("text-green-400", "bg-green-950"),
            "modified_locally": ("text-orange-400", "bg-orange-950"),
            "not_linked": ("text-gray-400", "bg-gray-800"),
            "failed": ("text-red-400", "bg-red-950"),
        }
        txt_color, badge_bg = status_colors.get(info.status.value, ("text-gray-400", "bg-gray-800"))

        with self._detail_container:
            with ui.column().classes("w-full gap-3"):
                # Header: filename + status badge
                with ui.row().classes("w-full items-start justify-between"):
                    with ui.column().classes("gap-0.5"):
                        ui.label(info.path.name).classes("text-white text-lg font-bold")
                        ui.label(str(info.path)).classes("text-gray-500 text-xs")
                    ui.label(f"● {info.status.value.replace('_', ' ')}").classes(
                        f"text-xs px-3 py-1 rounded-full {txt_color} {badge_bg} whitespace-nowrap"
                    )

                # Confluence info card
                with ui.card().classes("w-full bg-gray-900"):
                    ui.label("Confluence").classes("text-xs text-gray-500 uppercase mb-2")
                    if info.confluence_id:
                        with ui.grid(columns=2).classes("w-full text-xs gap-y-1.5"):
                            ui.label("Page name").classes("text-gray-500")
                            ui.label(info.confluence_page_name or "—").classes("text-white font-bold")
                            ui.label("Page ID").classes("text-gray-500")
                            ui.label(info.confluence_id).classes("text-indigo-400")
                            ui.label("Space").classes("text-gray-500")
                            ui.label(info.confluence_space or "—").classes("text-gray-300")
                            ui.label("Last sync").classes("text-gray-500")
                            ui.label(info.confluence_last_sync or "—").classes("text-gray-300")
                            ui.label("Open").classes("text-gray-500")
                            if info.confluence_url:
                                ui.link("View in Confluence ↗", target=info.confluence_url, new_tab=True).classes(
                                    "text-indigo-400 text-xs"
                                )
                            else:
                                ui.label("—").classes("text-gray-500")
                    else:
                        ui.label("Not linked to a Confluence page yet.").classes("text-gray-500 text-xs")

                # Action buttons
                with ui.row().classes("gap-2 flex-wrap"):
                    ui.button(
                        "⬆ Upload to Confluence",
                        on_click=lambda: self._do_upload([info.path]),
                    ).classes("bg-indigo-600 text-white text-xs")
                    ui.button(
                        "⬇ Pull from Confluence",
                        on_click=lambda: self._do_pull(info),
                    ).props("outline").classes("text-xs")
                    ui.button(
                        "🔗 Change ID…",
                        on_click=lambda: self._change_id_dialog(info),
                    ).props("outline").classes("text-xs")

                # Operation log
                ui.label("Last Operation Log").classes("text-xs text-gray-500 uppercase")
                self._log_label = ui.log(max_lines=20).classes(
                    "w-full h-32 bg-gray-950 text-xs font-mono rounded border border-gray-800"
                )

    def _do_upload(self, paths):
        # Deferred to avoid importing service modules at UI module load time
        from services.upload_service import UploadService
        svc = UploadService(self.config, self.tracker)
        log_widget = self._log_label  # capture now to avoid stale ref if user switches file

        def _cb(file, msg):
            if log_widget:
                log_widget.push(msg)

        async def _run():
            await asyncio.get_running_loop().run_in_executor(None, lambda: svc.upload(paths, progress_callback=_cb))
            await self._refresh()

        asyncio.create_task(_run())

    def _do_pull(self, info):
        if not info.confluence_url:
            ui.notify("No Confluence URL — use Change ID to set one first", type="warning")
            return
        # Deferred to avoid importing service modules at UI module load time
        from services.download_service import DownloadService, DownloadScope
        svc = DownloadService(self.config, self.tracker)

        def _cb(msg):
            if log_widget := self._log_label:
                log_widget.push(msg)

        async def _run():
            await asyncio.get_running_loop().run_in_executor(
                None,
                lambda: svc.download(info.confluence_url, DownloadScope.SINGLE, info.path.parent,
                                      overwrite=True, progress_callback=_cb),
            )
            await self._refresh()

        asyncio.create_task(_run())

    def _change_id_dialog(self, info):
        with ui.dialog() as dlg, ui.card():
            ui.label("Set Confluence Page ID").classes("font-bold")
            new_id = ui.input("Page ID", placeholder="e.g. 98321").classes("w-full")

            def _apply():
                if new_id.value.strip():
                    self.tracker.write_sync_state(info.path, {
                        "confluence_id": new_id.value.strip(),
                        "confluence_space": self.config.default_space,
                    })
                    dlg.close()
                    asyncio.create_task(self._refresh())
                    ui.notify("Confluence ID updated", type="positive")

            with ui.row().classes("gap-2 justify-end w-full mt-2"):
                ui.button("Cancel", on_click=dlg.close).props("flat")
                ui.button("Save", on_click=_apply).classes("bg-indigo-600 text-white")
        dlg.open()

    def _open_download_dialog(self):
        from ui.download_dialog import open_download_dialog
        open_download_dialog(self.config, self.tracker, default_dir=self.config.last_directory)

    def _rebuild_file_list(self):
        if self._file_list_container:
            self._file_list_container.clear()
            self._build_file_panel()

    def _rebuild_detail(self):
        if self._detail_container:
            self._detail_container.clear()
            self._build_detail_panel()

    async def _browse(self):
        result = await ui.run_javascript(
            'window.__dir = prompt("Enter directory path:"); window.__dir;'
        )
        if result:
            self._dir_input.value = result
            self.config.last_directory = result
            self.config.save()
            await self._refresh()

    async def _refresh(self):
        directory = self._dir_input.value.strip()
        if not directory:
            return
        self.files = await asyncio.get_running_loop().run_in_executor(None, self.tracker.scan, Path(directory))
        counts = {"synced": 0, "modified_locally": 0, "not_linked": 0, "failed": 0}
        for f in self.files:
            counts[f.status.value] += 1
        if self._status_label:
            self._status_label.set_text(
                f"{counts['synced']} synced · {counts['modified_locally']} modified · "
                f"{counts['not_linked']} unlinked · {counts['failed']} error"
            )
        self._rebuild_file_list()
