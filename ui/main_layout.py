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
        self._expanded_dirs: set[Path] = set()
        self.checked_files: set[Path] = set()
        self.multi_push_mode: bool = False
        self._last_clicked_path: Path | None = None
        self._rendered_paths: list[Path] = []
        self._search_input = None
        self._file_count_label = None

    def build(self):
        drawer = ui.left_drawer(value=True, bordered=True, top_corner=True, bottom_corner=True).classes("p-0 bg-gray-50 dark:bg-gray-900").props("width=550")
        with drawer:
            self._file_list_container = ui.column().classes("w-full gap-0 p-0")
            self._build_file_panel()

        with ui.header().classes("items-center gap-2 px-4 py-2 bg-gray-100 dark:bg-gray-900 text-gray-900 dark:text-white border-b border-gray-200 dark:border-gray-800"):
            ui.button(icon="menu", on_click=drawer.toggle).classes("text-gray-600 dark:text-gray-300").props("flat round dense")
            ui.label("md2confluence").classes("text-indigo-600 dark:text-indigo-400 font-bold text-sm")
            self._dir_input = ui.input(
                placeholder="Select directory…",
                value=self.config.last_directory,
            ).classes("flex-1 max-w-xs text-xs").props("readonly")
            ui.button("Browse", on_click=self._browse).classes("text-xs")
            ui.space()
            ui.button("⬇ Download", on_click=self._open_download_dialog).classes("text-xs").tooltip("Download pages from Confluence")
            ui.button("⚙ Config", on_click=lambda: ui.navigate.to("/config")).classes("text-xs").tooltip("Configure Confluence settings")
            ui.button("📖 Readme", on_click=lambda: ui.navigate.to("/readme")).classes("text-xs").tooltip("View Project Documentation")

        # The main content area handles the details panel
        self._detail_container = ui.column().classes("w-full p-4")
        self._build_detail_panel()

        with ui.footer().classes("px-4 py-1 bg-gray-100 dark:bg-gray-950 text-xs text-gray-600 dark:text-gray-500 border-t border-gray-200 dark:border-gray-800 flex gap-4"):
            self._conn_dot = ui.label("● Connected").classes("text-green-600 dark:text-green-400")
            ui.label(self.config.cloud_domain or self.config.server_url or "")
            ui.space()
            self._status_label = ui.label("No directory loaded")

    # Stubs — filled in Tasks 8, 9, 10
    def _build_file_panel(self):
        with self._file_list_container:
            with ui.row().classes("w-full items-center px-2 py-1 bg-gray-100 dark:bg-gray-900 border-b border-gray-200 dark:border-gray-800 gap-1"):
                ui.label("View:").classes("text-xs text-gray-600 dark:text-gray-400")
                ui.button("≡ Flat", on_click=lambda: self._set_view("flat")).classes("text-xs px-2 py-0.5")
                ui.button("⊞ Tree", on_click=lambda: self._set_view("tree")).classes("text-xs px-2 py-0.5")
                self._divider = ui.element("div").classes("w-px h-4 bg-gray-300 dark:bg-gray-700 mx-1")
                self._multi_push_toggle_btn = ui.button(
                    "☑ Select",
                    on_click=self._toggle_multi_push_mode
                ).classes("text-xs px-2 py-0.5 !bg-slate-100 !text-slate-700 dark:!bg-slate-800 dark:!text-slate-300 font-bold border border-slate-300 dark:border-slate-700 hover:!bg-slate-200")
                self._push_checked_btn = ui.button(
                    "",
                    on_click=lambda: self._prompt_parent_page_id(list(self.checked_files))
                ).classes("text-xs !bg-indigo-600 hover:!bg-indigo-700 !text-white px-2 py-0.5 font-bold").tooltip("Push selected files to Confluence")
                self._cancel_checked_btn = ui.button(
                    "Cancel",
                    on_click=self._cancel_multi_push
                ).classes("text-xs px-2 py-0.5 !bg-gray-200 !text-gray-700 dark:!bg-gray-800 dark:!text-gray-300 hover:!bg-gray-300")
                self._update_push_checked_btn()
                ui.space()
                self._file_count_label = ui.label(f"{len(self.files)} files").classes("text-xs text-gray-600 dark:text-gray-400 mr-2")
                with ui.button(on_click=self._refresh).classes("text-xs items-center px-2 py-0.5").tooltip(
                    "Rescan directory and recompute sync status (no API calls)"
                ) as self._refresh_btn:
                    self._refresh_icon = ui.html("&#x27F3;").classes("inline-block origin-center mr-1.5")
                    self._refresh_text = ui.label("Refresh")

            with ui.row().classes("w-full items-center px-2 py-1 bg-gray-50 dark:bg-gray-950 border-b border-gray-200 dark:border-gray-800 gap-2") as self._tree_controls_row:
                ui.label("Folders:").classes("text-xs text-gray-600 dark:text-gray-400")
                self._expand_all_btn = ui.button("＋ Expand All", on_click=self._expand_all).classes("text-xs px-1.5 py-0.5 !bg-slate-100 !text-slate-700 dark:!bg-slate-800 dark:!text-slate-300 border border-slate-300 dark:border-slate-700 hover:!bg-slate-200")
                self._collapse_all_btn = ui.button("－ Collapse All", on_click=self._collapse_all).classes("text-xs px-1.5 py-0.5 !bg-slate-100 !text-slate-700 dark:!bg-slate-800 dark:!text-slate-300 border border-slate-300 dark:border-slate-700 hover:!bg-slate-200")

            self._search_input = ui.input(
                placeholder="Search files...",
                on_change=self._rebuild_file_list
            ).classes("w-full px-3 py-1.5 text-xs").props("clearable")

            self._list_container = ui.column().classes("w-full gap-0 p-0")
            self._update_tree_buttons_visibility()
            self._rebuild_file_list()

    def _toggle_multi_push_mode(self):
        self.multi_push_mode = True
        self.checked_files.clear()
        self._update_push_checked_btn()
        self._rebuild_file_list()

    def _cancel_multi_push(self):
        self.multi_push_mode = False
        self.checked_files.clear()
        self._update_push_checked_btn()
        self._rebuild_file_list()

    def _update_push_checked_btn(self):
        if not self.multi_push_mode:
            self._multi_push_toggle_btn.set_visibility(True)
            self._push_checked_btn.set_visibility(False)
            self._cancel_checked_btn.set_visibility(False)
        else:
            self._multi_push_toggle_btn.set_visibility(False)
            self._cancel_checked_btn.set_visibility(True)
            count = len(self.checked_files)
            if count > 0:
                self._push_checked_btn.set_text(f"Push ({count})")
                self._push_checked_btn.set_visibility(True)
            else:
                self._push_checked_btn.set_visibility(False)

    def _set_view(self, view: str):
        self._current_view = view
        self._update_tree_buttons_visibility()
        self._rebuild_file_list()

    def _expand_all(self):
        base = Path(self.config.last_directory) if self.config.last_directory else None
        if not base:
            return
        for f in self.files:
            p = f.path.parent
            while p and p != base and p != p.parent:
                self._expanded_dirs.add(p)
                p = p.parent
            if p:
                self._expanded_dirs.add(p)
        self._rebuild_file_list()

    def _collapse_all(self):
        self._expanded_dirs.clear()
        self._rebuild_file_list()

    def _update_tree_buttons_visibility(self):
        is_tree = self._current_view == "tree"
        if hasattr(self, "_tree_controls_row") and self._tree_controls_row:
            self._tree_controls_row.set_visibility(is_tree)

    def _get_filtered_files(self) -> list[FileInfo]:
        if not self._search_input or not self._search_input.value:
            return self.files
        query = self._search_input.value.strip().lower()
        if not query:
            return self.files
        return [info for info in self.files if query in info.path.name.lower()]

    def _render_flat_list(self):
        filtered = self._get_filtered_files()
        self._rendered_paths = [info.path for info in filtered]
        for info in filtered:
            self._file_row(info, indent=0)

    def _render_tree_list(self):
        self._rendered_paths = []
        base = Path(self.config.last_directory) if self.config.last_directory else None

        class TreeNode:
            def __init__(self, name: str, path: Path):
                self.name = name
                self.path = path
                self.children: dict[str, TreeNode] = {}
                self.files: list[FileInfo] = []

        root = TreeNode("", base or Path())

        filtered = self._get_filtered_files()
        for info in filtered:
            current = root
            try:
                rel = info.path.parent.relative_to(base) if base else info.path.parent
                parts = rel.parts
            except ValueError:
                parts = info.path.parent.parts

            curr_path = base or Path()
            for part in parts:
                if not part or part == ".":
                    continue
                curr_path = curr_path / part
                if part not in current.children:
                    current.children[part] = TreeNode(part, curr_path)
                current = current.children[part]
            current.files.append(info)

        def get_all_files(n: TreeNode) -> list[Path]:
            res = [f.path for f in n.files]
            for child in n.children.values():
                res.extend(get_all_files(child))
            return res

        def is_dir_checked(n: TreeNode) -> bool:
            all_files = get_all_files(n)
            if not all_files:
                return False
            return all(p in self.checked_files for p in all_files)

        def toggle_dir_checked(n: TreeNode, checked: bool):
            all_files = get_all_files(n)
            for p in all_files:
                if checked:
                    self.checked_files.add(p)
                else:
                    self.checked_files.discard(p)
            self._update_push_checked_btn()
            self._rebuild_file_list()

        import re
        def natural_sort_key(s: str) -> list:
            return [int(text) if text.isdigit() else text.lower() for text in re.split(r'(\d+)', s)]

        def render_node(node: TreeNode, indent: int = 0):
            if node is root:
                for child_name, child_node in sorted(node.children.items(), key=lambda item: natural_sort_key(item[0])):
                    render_node(child_node, indent)
                for info in sorted(node.files, key=lambda f: natural_sort_key(f.path.name)):
                    self._rendered_paths.append(info.path)
                    self._file_row(info, indent)
            else:
                is_expanded = node.path in self._expanded_dirs
                dir_checked = self.multi_push_mode and is_dir_checked(node)
                row_classes = (
                    "w-full items-center px-2 py-1 gap-1 cursor-pointer "
                    + ("bg-indigo-50 dark:bg-indigo-950" if dir_checked else "hover:bg-gray-100 dark:hover:bg-gray-800")
                )
                with ui.row().classes(row_classes).on(
                    "click", lambda _, p=node.path: self._toggle_dir(p)
                ):
                    ui.label("▾" if is_expanded else "▸").classes("text-gray-600 dark:text-gray-500 text-lg").style(f"margin-left: {indent}px")
                    if self.multi_push_mode:
                        cb = ui.checkbox(value=dir_checked, on_change=lambda e, n=node: toggle_dir_checked(n, e.value)).props("dense").classes("scale-75 origin-left -my-1.5")
                        cb.on("click.stop", lambda: None)
                    ui.label(node.name + "/").classes(
                        "text-xs font-bold text-indigo-900 dark:text-white uppercase" if dir_checked else "text-xs text-gray-600 dark:text-gray-400 uppercase"
                    )
                if is_expanded:
                    for child_name, child_node in sorted(node.children.items(), key=lambda item: natural_sort_key(item[0])):
                        render_node(child_node, indent + 12)
                    for info in sorted(node.files, key=lambda f: natural_sort_key(f.path.name)):
                        self._rendered_paths.append(info.path)
                        self._file_row(info, indent + 12)

        render_node(root)

    def _toggle_dir(self, directory: Path):
        if directory in self._expanded_dirs:
            self._expanded_dirs.remove(directory)
        else:
            self._expanded_dirs.add(directory)
        self._rebuild_file_list()

    def _file_row(self, info: "FileInfo", indent: int = 0):
        dot_color = {
            "synced": "bg-green-500",
            "modified_locally": "bg-orange-400",
            "not_linked": "bg-gray-500",
            "failed": "bg-red-500",
        }.get(info.status.value, "bg-gray-500")

        is_selected = self.selected_file is not None and self.selected_file.path == info.path
        is_checked = self.multi_push_mode and info.path in self.checked_files
        should_highlight = is_selected or is_checked
        row_classes = (
            "w-full flex items-center px-3 py-1.5 cursor-pointer border-b border-gray-200 dark:border-gray-800 "
            + ("bg-indigo-50 dark:bg-indigo-950" if should_highlight else "hover:bg-gray-100 dark:hover:bg-gray-800")
        )

        with ui.element("div").classes(row_classes).style(f"padding-left:{indent + 12}px").on(
            "click", lambda e, i=info: self._on_row_click(i, e)
        ):
            with ui.row().classes("items-center gap-1.5"):
                if self.multi_push_mode:
                    cb = ui.checkbox(value=is_checked, on_change=lambda e, p=info.path: self._toggle_checked(p, e.value)).props("dense").classes("scale-75 origin-left -my-1.5")
                    cb.on("click.stop", lambda: None)
                ui.element("span").classes(f"w-2 h-2 rounded-full flex-shrink-0 {dot_color}")
                ui.label(info.path.name).classes(
                    "text-xs font-bold text-indigo-900 dark:text-white" if should_highlight else "text-xs text-gray-800 dark:text-gray-300"
                )

    def _on_row_click(self, info: "FileInfo", event_args=None):
        ctrl_pressed = False
        shift_pressed = False
        if event_args and isinstance(event_args.args, dict):
            shift_pressed = event_args.args.get("shiftKey", False)
            ctrl_pressed = event_args.args.get("ctrlKey", False) or event_args.args.get("metaKey", False)

        # Auto-activate multi push mode on Shift/Ctrl click
        if (shift_pressed or ctrl_pressed) and not self.multi_push_mode:
            self.multi_push_mode = True
            self.checked_files.clear()
            if self.selected_file:
                self._last_clicked_path = self.selected_file.path
            self._update_push_checked_btn()

        if self.multi_push_mode:
            current_path = info.path
            if shift_pressed and self._last_clicked_path and self._last_clicked_path in self._rendered_paths and current_path in self._rendered_paths:
                idx1 = self._rendered_paths.index(self._last_clicked_path)
                idx2 = self._rendered_paths.index(current_path)
                start_idx, end_idx = min(idx1, idx2), max(idx1, idx2)
                target_state = self._last_clicked_path in self.checked_files if self._last_clicked_path in self.checked_files else True
                for p in self._rendered_paths[start_idx : end_idx + 1]:
                    if target_state:
                        self.checked_files.add(p)
                    else:
                        self.checked_files.discard(p)
                self._update_push_checked_btn()
                self._rebuild_file_list()
            else:
                new_val = current_path not in self.checked_files
                self._toggle_checked(current_path, new_val)
                self._last_clicked_path = current_path
                self._rebuild_file_list()
        else:
            self._select_file(info)

    def _toggle_checked(self, path: Path, value: bool):
        if value:
            self.checked_files.add(path)
        else:
            self.checked_files.discard(path)
        self._update_push_checked_btn()

    def _select_file(self, info: "FileInfo"):
        self.selected_file = info
        base = Path(self.config.last_directory) if self.config.last_directory else None
        p = info.path.parent
        while p and p != base and p != p.parent:
            self._expanded_dirs.add(p)
            p = p.parent
        if p:
            self._expanded_dirs.add(p)
        # Full re-render is acceptable for the expected scale (< ~500 files).
        self._rebuild_file_list()
        self._rebuild_detail()

    def _build_detail_panel(self):
        if not self.selected_file:
            with self._detail_container:
                with ui.column().classes("w-full h-full items-center justify-center"):
                    ui.label("Select a file to view details").classes("text-gray-600 dark:text-gray-500 text-sm")
            return

        info = self.selected_file
        status_colors = {
            "synced": ("text-green-700 dark:text-green-400", "bg-green-50 dark:bg-green-950 border border-green-200 dark:border-green-800"),
            "modified_locally": ("text-orange-700 dark:text-orange-400", "bg-orange-50 dark:bg-orange-950 border border-orange-200 dark:border-orange-800"),
            "not_linked": ("text-gray-700 dark:text-gray-400", "bg-gray-100 dark:bg-gray-800 border border-gray-200 dark:border-gray-700"),
            "failed": ("text-red-700 dark:text-red-400", "bg-red-50 dark:bg-red-950 border border-red-200 dark:border-red-800"),
        }
        txt_color, badge_bg = status_colors.get(info.status.value, ("text-gray-700 dark:text-gray-400", "bg-gray-100 dark:bg-gray-800"))

        with self._detail_container:
            with ui.column().classes("w-full gap-3"):
                # Header: filename + status badge
                with ui.row().classes("w-full items-start justify-between"):
                    with ui.column().classes("gap-0.5"):
                        ui.label(info.path.name).classes("text-gray-900 dark:text-white text-lg font-bold")
                        ui.label(str(info.path)).classes("text-gray-600 dark:text-gray-500 text-xs")
                    ui.label(f"● {info.status.value.replace('_', ' ')}").classes(
                        f"text-xs px-3 py-1 rounded-full {txt_color} {badge_bg} whitespace-nowrap"
                    )

                # Confluence info card
                with ui.card().classes("w-full bg-gray-50 dark:bg-gray-900 border border-gray-100 dark:border-gray-800"):
                    ui.label("Confluence").classes("text-xs text-gray-600 dark:text-gray-400 uppercase mb-2")
                    if info.confluence_id:
                        with ui.grid(columns=2).classes("w-full text-xs gap-y-1.5"):
                            ui.label("Page name").classes("text-gray-600 dark:text-gray-400")
                            ui.label(info.confluence_page_name or "—").classes("text-gray-900 dark:text-white font-bold")
                            ui.label("Page ID").classes("text-gray-600 dark:text-gray-400")
                            ui.label(info.confluence_id).classes("text-indigo-600 dark:text-indigo-400 font-medium")
                            ui.label("Space").classes("text-gray-600 dark:text-gray-400")
                            ui.label(info.confluence_space or "—").classes("text-gray-900 dark:text-gray-300")
                            ui.label("Last sync").classes("text-gray-600 dark:text-gray-400")
                            ui.label(info.confluence_last_sync or "—").classes("text-gray-900 dark:text-gray-300")
                            ui.label("Open").classes("text-gray-600 dark:text-gray-400")
                            if info.confluence_url:
                                ui.link("View in Confluence ↗", target=info.confluence_url, new_tab=True).classes(
                                    "text-indigo-600 dark:text-indigo-400 text-xs"
                                )
                            else:
                                ui.label("—").classes("text-gray-600 dark:text-gray-500")
                    else:
                        ui.label("Not linked to a Confluence page yet.").classes("text-gray-600 dark:text-gray-500 text-xs")

                # Action buttons
                with ui.row().classes("gap-2 flex-wrap"):
                    ui.button(
                        "⬆ Push",
                        on_click=lambda: self._prompt_parent_page_id([info.path]),
                    ).classes("bg-indigo-600 text-white text-xs").tooltip("Push this file to Confluence")
                    ui.button(
                        "⬇ Pull",
                        on_click=lambda: self._do_pull(info),
                    ).props("outline").classes("text-xs").tooltip("Pull page content from Confluence")
                    ui.button(
                        "🔗 Change ID",
                        on_click=lambda: self._change_id_dialog(info),
                    ).props("outline").classes("text-xs").tooltip("Change the linked Confluence Page ID")

                # Operation log
                ui.label("Last Operation Log").classes("text-xs text-gray-600 dark:text-gray-400 uppercase")
                self._log_label = ui.log(max_lines=1000).classes(
                    "w-full h-64 bg-gray-50 dark:bg-gray-950 text-gray-900 dark:text-gray-100 text-xs font-mono rounded border border-gray-200 dark:border-gray-800"
                )

    def _prompt_parent_page_id(self, paths):
        if not paths:
            ui.notify("No files selected", type="warning")
            return

        with ui.dialog() as dlg, ui.card():
            ui.label("Enter Parent Page ID").classes("font-bold")
            parent_id_input = ui.input(
                "Parent Page ID",
                value=self.config.default_parent_page_id or ""
            ).classes("w-full")

            def _confirm():
                parent_id = parent_id_input.value.strip()
                dlg.close()
                self._do_upload(paths, parent_id if parent_id else None)

            with ui.row().classes("gap-2 justify-end w-full mt-2"):
                ui.button("Cancel", on_click=dlg.close).props("flat")
                ui.button("Push", on_click=_confirm).classes("bg-indigo-600 text-white")
        dlg.open()

    def _do_upload(self, paths, parent_page_id=None):
        # Deferred to avoid importing service modules at UI module load time
        from services.upload_service import UploadService
        svc = UploadService(self.config, self.tracker)
        log_widget = self._log_label  # capture now to avoid stale ref if user switches file
        client = ui.context.client
        loop = asyncio.get_running_loop()

        def _cb(file, msg):
            if log_widget:
                loop.call_soon_threadsafe(log_widget.push, msg)

        async def _run():
            try:
                await loop.run_in_executor(None, lambda: svc.upload(paths, parent_page_id=parent_page_id, progress_callback=_cb))
                await self._refresh()
            except Exception as exc:
                with client:
                    ui.notify(f"Upload error: {exc}", type="negative")

        asyncio.create_task(_run())

    def _do_pull(self, info):
        if not info.confluence_url:
            ui.notify("No Confluence URL — use Change ID to set one first", type="warning")
            return
        # Deferred to avoid importing service modules at UI module load time
        from services.download_service import DownloadService, DownloadScope
        svc = DownloadService(self.config, self.tracker)
        client = ui.context.client
        loop = asyncio.get_running_loop()

        def _cb(msg):
            if log_widget := self._log_label:
                loop.call_soon_threadsafe(log_widget.push, msg)

        async def _run():
            try:
                await loop.run_in_executor(
                    None,
                    lambda: svc.download(info.confluence_url, DownloadScope.SINGLE, info.path.parent,
                                          overwrite=True, progress_callback=_cb),
                )
                await self._refresh()
            except Exception as exc:
                with client:
                    ui.notify(f"Download error: {exc}", type="negative")

        asyncio.create_task(_run())

    def _change_id_dialog(self, info):
        client = ui.context.client
        with ui.dialog() as dlg, ui.card().classes("w-96 p-6"):
            ui.label("Set Confluence Page ID").classes("text-lg font-bold text-gray-800 dark:text-gray-200")
            new_id = ui.input(
                "Page ID", 
                value=info.confluence_id or "", 
                placeholder="e.g. 98321"
            ).classes("w-full")

            async def _apply():
                page_id = new_id.value.strip()
                if not page_id:
                    with client:
                        ui.notify("Please enter a Page ID first", type="warning")
                    return
                
                dlg.close()
                
                with client:
                    loading_notification = ui.notify("Updating page ID and resolving space key...", type="info", timeout=0)
                
                try:
                    # Resolve space key via Confluence API
                    space_key = await asyncio.get_running_loop().run_in_executor(
                        None, 
                        self.config.fetch_space_key_for_page, 
                        page_id
                    )
                    
                    self.tracker.write_sync_state(info.path, {
                        "confluence_id": page_id,
                        "confluence_space": space_key,
                    })
                    
                    with client:
                        ui.notify(f"Confluence ID updated. Space resolved to '{space_key}'", type="positive")
                except Exception as exc:
                    # Fallback to default space
                    fallback_space = self.config.default_space
                    self.tracker.write_sync_state(info.path, {
                        "confluence_id": page_id,
                        "confluence_space": fallback_space,
                    })
                    
                    with client:
                        ui.notify(
                            f"Confluence ID updated. Used default space '{fallback_space}' (API lookup failed: {exc})", 
                            type="warning"
                        )
                finally:
                    new_info = self.tracker._inspect(info.path)
                    if self.selected_file and self.selected_file.path == info.path:
                        self.selected_file = new_info
                    
                    with client:
                        self._rebuild_detail()
                        asyncio.create_task(self._refresh())
                        try:
                            loading_notification.dismiss()
                        except Exception:
                            pass

            with ui.row().classes("gap-2 justify-end w-full mt-4"):
                ui.button("Cancel", on_click=dlg.close).props("flat")
                ui.button("Save", on_click=lambda: asyncio.create_task(_apply())).classes("bg-indigo-600 text-white")
        dlg.open()

    def _open_download_dialog(self):
        from ui.download_dialog import open_download_dialog
        open_download_dialog(self.config, self.tracker, default_dir=self.config.last_directory, on_download_complete=self._refresh)

    def _rebuild_file_list(self):
        if self._list_container:
            self._list_container.clear()
            with self._list_container:
                if self._current_view == "flat":
                    self._render_flat_list()
                else:
                    self._render_tree_list()
            if self._file_count_label:
                filtered_count = len(self._get_filtered_files())
                total_count = len(self.files)
                if filtered_count != total_count:
                    self._file_count_label.set_text(f"{filtered_count}/{total_count} files")
                else:
                    self._file_count_label.set_text(f"{total_count} files")

    def _rebuild_detail(self):
        if self._detail_container:
            self._detail_container.clear()
            self._build_detail_panel()

    async def _browse(self):
        from ui.local_folder_picker import local_folder_picker
        picker = local_folder_picker(self.config.last_directory or ".")
        result = await picker
        if result:
            self._dir_input.value = result
            self.config.last_directory = result
            self.config.save()
            await self._refresh()

    async def _refresh(self):
        directory = self._dir_input.value.strip()
        if not directory:
            return
        if self._refresh_icon:
            self._refresh_icon.classes("animate-spin")
        try:
            self.files = await asyncio.get_running_loop().run_in_executor(None, self.tracker.scan, Path(directory))
            counts = {"synced": 0, "modified_locally": 0, "not_linked": 0, "failed": 0}
            for f in self.files:
                counts[f.status.value] += 1
            if self._status_label:
                self._status_label.set_text(
                    f"{counts['synced']} synced · {counts['modified_locally']} modified · "
                    f"{counts['not_linked']} unlinked · {counts['failed']} error"
                )
            self.checked_files.clear()
            self.multi_push_mode = False
            self._update_push_checked_btn()
            self._rebuild_file_list()
        finally:
            if self._refresh_icon:
                self._refresh_icon.classes(remove="animate-spin")
