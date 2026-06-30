import asyncio
from pathlib import Path
from nicegui import ui
from services.confluence_config import ConfluenceConfig
from services.download_service import DownloadService, DownloadScope
from services.file_tracker import FileTracker


def open_download_dialog(config: ConfluenceConfig, tracker: FileTracker, default_dir: str = "", on_download_complete=None):
    with ui.dialog() as dlg, ui.card().classes("w-full max-w-lg"):
        ui.label("⬇ Download from Confluence").classes("font-bold text-base mb-2")

        with ui.column().classes("w-full max-h-[40vh] overflow-y-auto gap-3 pr-2"):
            url_input = ui.input(
                "Confluence Page URL or Page ID",
                placeholder="https://company.atlassian.net/wiki/spaces/TEAM/pages/123",
            ).classes("w-full")
            resolved_label = ui.label("").classes("text-xs mt-0.5 text-gray-600 dark:text-gray-500")

            def _on_url_change():
                v = url_input.value.strip()
                resolved_label.set_text(
                    "Enter a URL — page name will resolve on download" if v else ""
                )

            url_input.on_value_change(lambda _: _on_url_change())

            ui.label("Scope").classes("text-xs text-gray-600 dark:text-gray-400 uppercase mt-3")
            scope_radio = ui.radio(
                {DownloadScope.SINGLE: "Single page", DownloadScope.RECURSIVE: "Page + all children (recursive)"},
                value=DownloadScope.SINGLE,
            ).classes("text-sm")

            async def _browse_dir():
                from ui.local_folder_picker import local_folder_picker
                picker = local_folder_picker(dir_input.value or default_dir or ".")
                result = await picker
                if result:
                    dir_input.value = result

            ui.label("Save to").classes("text-xs text-gray-600 dark:text-gray-400 uppercase mt-3")
            with ui.row().classes("w-full gap-2"):
                dir_input = ui.input(value=default_dir).classes("flex-1")
                ui.button("Browse", on_click=_browse_dir).classes("text-xs")

            ui.label("Options").classes("text-xs text-gray-600 dark:text-gray-400 uppercase mt-3")
            opt_attachments = ui.checkbox("Download attachments and images", value=True)
            opt_frontmatter = ui.checkbox("Write Confluence ID to frontmatter", value=True)
            opt_overwrite = ui.checkbox("Overwrite existing files", value=False).tooltip(
                "When unchecked, files that already exist locally are skipped. "
                "When checked, existing files are replaced with the Confluence version."
            )

        progress_log = ui.log(max_lines=10).classes(
            "w-full h-24 bg-gray-50 dark:bg-gray-950 text-gray-900 dark:text-gray-100 text-xs font-mono rounded border border-gray-200 dark:border-gray-800 mt-3"
        )
        progress_log.set_visibility(False)

        async def _download():
            url = url_input.value.strip()
            target = dir_input.value.strip()
            if not url or not target:
                ui.notify("URL and directory are required", type="warning")
                return

            progress_log.set_visibility(True)
            svc = DownloadService(config, tracker)
            loop = asyncio.get_running_loop()

            def _cb(msg: str) -> None:
                loop.call_soon_threadsafe(progress_log.push, msg)

            try:
                ok, msg = await loop.run_in_executor(
                    None,
                    lambda: svc.download(
                        page_url=url,
                        scope=scope_radio.value,
                        target_dir=Path(target),
                        overwrite=opt_overwrite.value,
                        download_attachments=opt_attachments.value,
                        write_frontmatter=opt_frontmatter.value,
                        progress_callback=_cb,
                    ),
                )
                if ok:
                    ui.notify("Download complete", type="positive")
                    if on_download_complete:
                        if asyncio.iscoroutinefunction(on_download_complete):
                            await on_download_complete()
                        else:
                            on_download_complete()
                else:
                    ui.notify(f"Download failed: {msg}", type="negative")
            except Exception as exc:
                ui.notify(f"Unexpected error: {exc}", type="negative")

        with ui.row().classes("w-full justify-end gap-2 mt-4"):
            ui.button("Cancel", on_click=dlg.close).props("flat")
            ui.button("⬇ Download", on_click=_download).classes("bg-indigo-600 text-white")

    dlg.open()
