from nicegui import ui

def main():
    ui.label("md2confluence — starting up")
    ui.run(title="md2confluence", port=0, reload=False)

if __name__ == "__main__":
    main()
