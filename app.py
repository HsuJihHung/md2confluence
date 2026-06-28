from nicegui import ui

def main():
    ui.label("md2confluence — starting up")
    # port=0 lets the OS assign a free port, avoiding conflicts with other local services
    ui.run(title="md2confluence", port=0, reload=False)

if __name__ == "__main__":
    main()
