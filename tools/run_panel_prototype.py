"""Run the panel prototype (looks and behaviour only, no AI).

    python -m tools.run_panel_prototype              run it (right-click the thin line to quit)
    python -m tools.run_panel_prototype --picture X  save a picture of the open panel to X and exit
"""

import argparse
import sys

from trado.ui import panel


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--picture", metavar="FILE", help="save a picture of the open panel and exit")
    args = parser.parse_args()
    if args.picture:
        from PySide6.QtWidgets import QApplication

        app = QApplication.instance() or QApplication(sys.argv)  # noqa: F841
        p = panel.Panel(on_settings=lambda: None)
        p.grab().save(args.picture)
        print("saved", args.picture)
        return 0
    return panel.run()


if __name__ == "__main__":
    sys.exit(main())
