#!/usr/bin/env python3
"""
pico_modifier_gui.py

Place this file in your scripts folder and run it from the project root:

    python scripts/pico_modifier_gui.py

Expected project layout from the folder where you run it:

    sd/data/<device>/
    sd/gfx/digimon/<device>/
    sd/gfx/cutin/<device>/
    sd/profile/
    scripts/export_data_to_csv.py
    scripts/import_data_from_csv.py
    scripts/export_sprites.py
    scripts/import_sprites.py
    scripts/export_cutins.py
    scripts/import_cutins.py
    scripts/profile_page_tool.py
    scripts/make_digimon_analyzer_images.py
    scripts/make_and_import_all_analyzer_cutins.py

Root output/edit folders:
    data/
    sprites/
    cutins/
    profile_images/
    generated_images/
"""

from __future__ import annotations
import sys
from pathlib import Path
from typing import List, Optional
from PyQt5 import QtCore, QtGui, QtWidgets
import runpy
import argparse
import io
import re
import sys
from pathlib import Path
from typing import Dict, List, Tuple, Optional
from urllib.parse import quote, unquote, urljoin
import requests
from bs4 import BeautifulSoup, Tag
from PIL import Image, ImageDraw, ImageFont
import traceback
import contextlib
import shutil

import pytesseract

if getattr(sys, "frozen", False):
    tesseract_path = Path(sys._MEIPASS) / "tesseract"
else:
    tesseract_path = Path("third_party/tesseract")

pytesseract.pytesseract.tesseract_cmd = str(tesseract_path)

if getattr(sys, "frozen", False):
    BASE_DIR = Path(sys._MEIPASS)
    SCRIPT_DIR = BASE_DIR / "scripts"

    exe_path = Path(sys.executable).resolve()

    # macOS .app bundle
    if sys.platform == "darwin" and ".app" in str(exe_path):
        APP_ROOT = exe_path.parents[3]

    # Windows/Linux standalone executable
    else:
        APP_ROOT = exe_path.parent

    # Use embedded executable
    PYTHON_EXE = str(exe_path)

else:
    SCRIPT_DIR = Path(__file__).resolve().parent
    APP_ROOT = Path.cwd().resolve()

    PYTHON_EXE = sys.executable

ALL_DEVICES = [
    ("dvc", "Digivice Color"),
    ("d3c", "D-3 Color"),
    ("vb", "Vital Bracelet"),
    ("dmc", "Digital Monster Color"),
    ("penc", "Pendulum Color"),
    ("dm20", "Digital Monster 20th"),
    ("dmx", "Digital Monster X"),
    ("pen20", "Pendulum 20th"),
    ("penz", "Pendulum Z"),
]

SPRITE_DEVICES = [
    ("dvc", "Digivice Color"),
    ("d3c", "D-3 Color"),
    ("vb", "Vital Bracelet"),
    ("dmc", "Digital Monster Color"),
    ("penc", "Pendulum Color"),
]

EXPORT_BTN_STYLE = """
QPushButton { background-color: #1565c0; color: white; font-weight: 700; font-size: 13pt;
              padding: 8px 12px; border-radius: 6px; }
QPushButton:hover { background-color: #1976d2; }
QPushButton:pressed { background-color: #0d47a1; }
QPushButton:disabled { background-color: #555555; color: #999999; }
"""

IMPORT_BTN_STYLE = """
QPushButton { background-color: #2e7d32; color: white; font-weight: 700; font-size: 13pt;
              padding: 8px 12px; border-radius: 6px; }
QPushButton:hover { background-color: #388e3c; }
QPushButton:pressed { background-color: #1b5e20; }
QPushButton:disabled { background-color: #555555; color: #999999; }
"""

SECONDARY_BTN_STYLE = """
QPushButton { background-color: #424242; color: #eeeeee; font-weight: 600;
              padding: 6px 10px; border-radius: 5px; }
QPushButton:hover { background-color: #555555; }
QPushButton:pressed { background-color: #303030; }
"""

DANGER_BTN_STYLE = """
QPushButton { background-color: #8e0000; color: white; font-weight: 700; font-size: 12pt;
              padding: 7px 12px; border-radius: 6px; }
QPushButton:hover { background-color: #b00020; }
QPushButton:pressed { background-color: #5f0000; }
"""

def script_path(name: str) -> Path:
    path = SCRIPT_DIR / name

    print(f"[DEBUG] script_path={path}")

    return path

def relpath(path: Path) -> str:
    try:
        return str(path.relative_to(APP_ROOT))
    except ValueError:
        return str(path)


def ensure_root_dirs() -> None:
    for name in [
        "data",
        "sprites",
        "cutins",
        "profile_images",
        "generated_images",
    ]:
        (APP_ROOT / name).mkdir(parents=True, exist_ok=True)


class NoWheelComboBox(QtWidgets.QComboBox):
    def wheelEvent(self, event):
        if self.view().isVisible():
            super().wheelEvent(event)
        else:
            event.ignore()


class ProcessDialog(QtWidgets.QDialog):
    def __init__(self, title: str, command_preview: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setModal(True)
        self.setMinimumSize(780, 480)
        self.ok = False
        self.process: Optional[QtCore.QProcess] = None

        layout = QtWidgets.QVBoxLayout(self)
        self.header = QtWidgets.QLabel(command_preview)
        self.header.setWordWrap(True)
        self.header.setTextInteractionFlags(QtCore.Qt.TextSelectableByMouse)
        layout.addWidget(self.header)

        self.bar = QtWidgets.QProgressBar()
        self.bar.setRange(0, 0)
        layout.addWidget(self.bar)

        self.output = QtWidgets.QPlainTextEdit()
        self.output.setReadOnly(True)
        self.output.setLineWrapMode(QtWidgets.QPlainTextEdit.NoWrap)
        self.output.setFont(QtGui.QFontDatabase.systemFont(QtGui.QFontDatabase.FixedFont))
        layout.addWidget(self.output, 1)

        row = QtWidgets.QHBoxLayout()
        self.kill_btn = QtWidgets.QPushButton("Stop")
        self.kill_btn.setStyleSheet(DANGER_BTN_STYLE)
        self.close_btn = QtWidgets.QPushButton("Close")
        self.close_btn.setStyleSheet(SECONDARY_BTN_STYLE)
        self.close_btn.setEnabled(False)
        row.addStretch(1)
        row.addWidget(self.kill_btn)
        row.addWidget(self.close_btn)
        layout.addLayout(row)

        self.kill_btn.clicked.connect(self._kill)
        self.close_btn.clicked.connect(self.accept)

    def start(self, program: str, args: List[str], cwd: Path):
        self.process = QtCore.QProcess(self)
        self.process.setProgram(program)
        self.process.setArguments(args)
        self.process.setWorkingDirectory(str(cwd))
        self.process.setProcessChannelMode(QtCore.QProcess.MergedChannels)
        env = QtCore.QProcessEnvironment.systemEnvironment()
        env.insert("PYTHONUNBUFFERED", "1")
        env.insert("PYTHONUTF8", "1")
        env.insert("PYTHONIOENCODING", "utf-8")
        self.process.setProcessEnvironment(env)
        self.process.readyReadStandardOutput.connect(self._read_output)
        self.process.errorOccurred.connect(self._error)
        self.process.finished.connect(self._finished)
        self.process.start()

    def _read_output(self):
        if not self.process:
            return
        data = bytes(self.process.readAllStandardOutput()).decode("utf-8", errors="replace")
        if data:
            self.output.moveCursor(QtGui.QTextCursor.End)
            self.output.insertPlainText(data)
            self.output.moveCursor(QtGui.QTextCursor.End)

    def _error(self, err):
        self.output.appendPlainText(f"\n[QProcess error: {err}]\n")

    def _finished(self, exit_code, exit_status):
        self.ok = (exit_code == 0 and exit_status == QtCore.QProcess.NormalExit)
        self.bar.setRange(0, 100)
        self.bar.setValue(100)
        self.kill_btn.setEnabled(False)
        self.close_btn.setEnabled(True)
        if self.ok:
            self.output.appendPlainText("\n[DONE]\n")
        else:
            self.output.appendPlainText(f"\n[FAILED] exit_code={exit_code}, exit_status={exit_status}\n")

    def _kill(self):
        if self.process and self.process.state() != QtCore.QProcess.NotRunning:
            self.process.kill()
            self.output.appendPlainText("\n[Stopped by user]\n")


class CommandTab(QtWidgets.QWidget):
    def __init__(self, devices=ALL_DEVICES, parent=None):
        super().__init__(parent)
        self.devices = devices
        self._build_ui()

    def _build_ui(self):
        self.main_layout = QtWidgets.QVBoxLayout(self)
        top = QtWidgets.QGroupBox("Device")
        top_layout = QtWidgets.QGridLayout(top)
        self.type_combo = NoWheelComboBox()
        for key, label in self.devices:
            self.type_combo.addItem(label, key)
        top_layout.addWidget(QtWidgets.QLabel("Type:"), 0, 0)
        top_layout.addWidget(self.type_combo, 0, 1)
        top_layout.setColumnStretch(1, 1)
        self.main_layout.addWidget(top)
        self.body = QtWidgets.QVBoxLayout()
        self.main_layout.addLayout(self.body, 1)
        self.status = QtWidgets.QLabel("Ready.")
        self.status.setWordWrap(True)
        self.main_layout.addWidget(self.status)

    def device(self) -> str:
        return self.type_combo.currentData()

    def device_label(self) -> str:
        return self.type_combo.currentText()

    def run_script(self, script_name: str, args: List[str], title: str):
        path = script_path(script_name)
        if not path.exists():
            QtWidgets.QMessageBox.critical(self, "Missing script", f"Could not find:\n{path}")
            return
        cmd_preview = " ".join([PYTHON_EXE, relpath(path)] + args)

        dlg = ProcessDialog(title, cmd_preview, self)

        dlg.start(
            PYTHON_EXE,
            [str(path)] + args,
            APP_ROOT,
        )
        dlg.exec_()
        if dlg.ok:
            self.status.setText(f"{title} completed.")
            QtWidgets.QMessageBox.information(self, "Done", f"{title} completed.")
        else:
            self.status.setText(f"{title} failed.")
            QtWidgets.QMessageBox.critical(self, "Error", f"{title} failed. Check the output window.")


class DataTab(CommandTab):
    def __init__(self, parent=None):
        super().__init__(ALL_DEVICES, parent)

    def _build_ui(self):
        super()._build_ui()
        group = QtWidgets.QGroupBox("Data CSV Import / Export")
        g = QtWidgets.QGridLayout(group)
        self.input_folder = QtWidgets.QLineEdit()
        self.csv_path = QtWidgets.QLineEdit()
        self.output_folder = QtWidgets.QLineEdit()
        self.pick_input_btn = QtWidgets.QPushButton("Pick Data Folder")
        self.pick_csv_btn = QtWidgets.QPushButton("Pick CSV")
        self.pick_output_btn = QtWidgets.QPushButton("Pick Output Folder")
        for b in [self.pick_input_btn, self.pick_csv_btn, self.pick_output_btn]:
            b.setStyleSheet(SECONDARY_BTN_STYLE)
        self.export_btn = QtWidgets.QPushButton("Export Data CSV")
        self.import_btn = QtWidgets.QPushButton("Import Data CSV")
        self.export_btn.setStyleSheet(EXPORT_BTN_STYLE)
        self.import_btn.setStyleSheet(IMPORT_BTN_STYLE)
        g.addWidget(QtWidgets.QLabel("Input data folder:"), 0, 0)
        g.addWidget(self.input_folder, 0, 1)
        g.addWidget(self.pick_input_btn, 0, 2)
        g.addWidget(QtWidgets.QLabel("CSV file:"), 1, 0)
        g.addWidget(self.csv_path, 1, 1)
        g.addWidget(self.pick_csv_btn, 1, 2)
        g.addWidget(QtWidgets.QLabel("Import output folder:"), 2, 0)
        g.addWidget(self.output_folder, 2, 1)
        g.addWidget(self.pick_output_btn, 2, 2)
        g.addWidget(self.export_btn, 3, 1)
        g.addWidget(self.import_btn, 3, 2)
        g.setColumnStretch(1, 1)
        self.body.addWidget(group)
        self.body.addStretch(1)
        self.type_combo.currentIndexChanged.connect(self.update_defaults)
        self.pick_input_btn.clicked.connect(lambda: self.pick_dir(self.input_folder, "Select sd/data/<device> folder"))
        self.pick_csv_btn.clicked.connect(self.pick_csv)
        self.pick_output_btn.clicked.connect(lambda: self.pick_dir(self.output_folder, "Select output sd/data/<device> folder"))
        self.export_btn.clicked.connect(self.export_data)
        self.import_btn.clicked.connect(self.import_data)
        self.update_defaults()

    def update_defaults(self):
        dev = self.device()
        self.input_folder.setText(str(APP_ROOT / "sd" / "data" / dev))
        self.csv_path.setText(str(APP_ROOT / "data" / f"{dev}_data.csv"))
        self.output_folder.setText(str(APP_ROOT / "sd" / "data" / dev))

    def pick_dir(self, edit, title):
        path = QtWidgets.QFileDialog.getExistingDirectory(self, title, edit.text() or str(APP_ROOT))
        if path:
            edit.setText(path)

    def pick_csv(self):
        path, _ = QtWidgets.QFileDialog.getSaveFileName(self, "Select CSV", self.csv_path.text(), "CSV files (*.csv);;All files (*)")
        if path:
            self.csv_path.setText(path)

    def export_data(self):
        self.run_script("export_data_to_csv.py", [self.input_folder.text().strip(), self.csv_path.text().strip()], f"Export Data CSV ({self.device_label()})")

    def import_data(self):
        self.run_script("import_data_from_csv.py", [self.csv_path.text().strip(), self.output_folder.text().strip()], f"Import Data CSV ({self.device_label()})")


class SpritesTab(CommandTab):
    def __init__(self, parent=None):
        super().__init__(SPRITE_DEVICES, parent)

    def _build_ui(self):
        super()._build_ui()
        group = QtWidgets.QGroupBox("Sprites Import / Export")
        g = QtWidgets.QGridLayout(group)
        self.input_folder = QtWidgets.QLineEdit()
        self.sprites_folder = QtWidgets.QLineEdit()
        self.output_folder = QtWidgets.QLineEdit()
        self.png_check = QtWidgets.QCheckBox("Also export PNG")
        self.recursive_check = QtWidgets.QCheckBox("Recursive")
        self.pick_input_btn = QtWidgets.QPushButton("Pick Digimon GFX Folder")
        self.pick_sprites_btn = QtWidgets.QPushButton("Pick Sprites Folder")
        self.pick_output_btn = QtWidgets.QPushButton("Pick Output Folder")
        for b in [self.pick_input_btn, self.pick_sprites_btn, self.pick_output_btn]:
            b.setStyleSheet(SECONDARY_BTN_STYLE)
        self.export_btn = QtWidgets.QPushButton("Export Sprites")
        self.import_btn = QtWidgets.QPushButton("Import Sprites")
        self.export_btn.setStyleSheet(EXPORT_BTN_STYLE)
        self.import_btn.setStyleSheet(IMPORT_BTN_STYLE)
        g.addWidget(QtWidgets.QLabel("Input sd/gfx/digimon folder:"), 0, 0)
        g.addWidget(self.input_folder, 0, 1)
        g.addWidget(self.pick_input_btn, 0, 2)
        g.addWidget(QtWidgets.QLabel("Sprites folder:"), 1, 0)
        g.addWidget(self.sprites_folder, 1, 1)
        g.addWidget(self.pick_sprites_btn, 1, 2)
        g.addWidget(QtWidgets.QLabel("Import output folder:"), 2, 0)
        g.addWidget(self.output_folder, 2, 1)
        g.addWidget(self.pick_output_btn, 2, 2)
        opts = QtWidgets.QHBoxLayout()
        opts.addWidget(self.png_check)
        opts.addWidget(self.recursive_check)
        opts.addStretch(1)
        g.addLayout(opts, 3, 1, 1, 2)
        g.addWidget(self.export_btn, 4, 1)
        g.addWidget(self.import_btn, 4, 2)
        g.setColumnStretch(1, 1)
        self.body.addWidget(group)
        self.body.addStretch(1)
        self.type_combo.currentIndexChanged.connect(self.update_defaults)
        self.pick_input_btn.clicked.connect(lambda: self.pick_dir(self.input_folder, "Select sd/gfx/digimon/<device> folder"))
        self.pick_sprites_btn.clicked.connect(lambda: self.pick_dir(self.sprites_folder, "Select sprites folder"))
        self.pick_output_btn.clicked.connect(lambda: self.pick_dir(self.output_folder, "Select output folder"))
        self.export_btn.clicked.connect(self.export_sprites)
        self.import_btn.clicked.connect(self.import_sprites)
        self.update_defaults()

    def update_defaults(self):
        dev = self.device()
        self.input_folder.setText(str(APP_ROOT / "sd" / "gfx" / "digimon" / dev))
        self.sprites_folder.setText(str(APP_ROOT / "sprites" / dev))
        self.output_folder.setText(str(APP_ROOT / "sd" / "gfx" / "digimon" / dev))

    def pick_dir(self, edit, title):
        path = QtWidgets.QFileDialog.getExistingDirectory(self, title, edit.text() or str(APP_ROOT))
        if path:
            edit.setText(path)

    def export_sprites(self):
        args = [self.input_folder.text().strip(), "-o", self.sprites_folder.text().strip()]
        if self.png_check.isChecked():
            args.append("--png")
        if self.recursive_check.isChecked():
            args.append("--recursive")
        self.run_script("export_sprites.py", args, f"Export Sprites ({self.device_label()})")

    def import_sprites(self):
        args = [self.input_folder.text().strip(), self.sprites_folder.text().strip(), "-o", self.output_folder.text().strip()]
        if self.recursive_check.isChecked():
            args.append("--recursive")
        self.run_script("import_sprites.py", args, f"Import Sprites ({self.device_label()})")


class CutinsTab(CommandTab):
    def __init__(self, parent=None):
        super().__init__(ALL_DEVICES, parent)

    def _build_ui(self):
        super()._build_ui()
        group = QtWidgets.QGroupBox("Cut-ins Import / Export")
        g = QtWidgets.QGridLayout(group)
        self.input_folder = QtWidgets.QLineEdit()
        self.cutins_folder = QtWidgets.QLineEdit()
        self.output_folder = QtWidgets.QLineEdit()
        self.png_check = QtWidgets.QCheckBox("Also export PNG")
        self.recursive_check = QtWidgets.QCheckBox("Recursive")
        self.pick_input_btn = QtWidgets.QPushButton("Pick Cutin Folder")
        self.pick_cutins_btn = QtWidgets.QPushButton("Pick Cutins Folder")
        self.pick_output_btn = QtWidgets.QPushButton("Pick Output Folder")
        for b in [self.pick_input_btn, self.pick_cutins_btn, self.pick_output_btn]:
            b.setStyleSheet(SECONDARY_BTN_STYLE)
        self.export_btn = QtWidgets.QPushButton("Export Cut-ins")
        self.import_btn = QtWidgets.QPushButton("Import Cut-ins")
        self.export_btn.setStyleSheet(EXPORT_BTN_STYLE)
        self.import_btn.setStyleSheet(IMPORT_BTN_STYLE)
        g.addWidget(QtWidgets.QLabel("Input sd/gfx/cutin folder:"), 0, 0)
        g.addWidget(self.input_folder, 0, 1)
        g.addWidget(self.pick_input_btn, 0, 2)
        g.addWidget(QtWidgets.QLabel("Cutins folder:"), 1, 0)
        g.addWidget(self.cutins_folder, 1, 1)
        g.addWidget(self.pick_cutins_btn, 1, 2)
        g.addWidget(QtWidgets.QLabel("Import output folder:"), 2, 0)
        g.addWidget(self.output_folder, 2, 1)
        g.addWidget(self.pick_output_btn, 2, 2)
        opts = QtWidgets.QHBoxLayout()
        opts.addWidget(self.png_check)
        opts.addWidget(self.recursive_check)
        opts.addStretch(1)
        g.addLayout(opts, 3, 1, 1, 2)
        g.addWidget(self.export_btn, 4, 1)
        g.addWidget(self.import_btn, 4, 2)
        g.setColumnStretch(1, 1)
        self.body.addWidget(group)
        self.body.addStretch(1)
        self.type_combo.currentIndexChanged.connect(self.update_defaults)
        self.pick_input_btn.clicked.connect(lambda: self.pick_dir(self.input_folder, "Select sd/gfx/cutin/<device> folder"))
        self.pick_cutins_btn.clicked.connect(lambda: self.pick_dir(self.cutins_folder, "Select cutins folder"))
        self.pick_output_btn.clicked.connect(lambda: self.pick_dir(self.output_folder, "Select output folder"))
        self.export_btn.clicked.connect(self.export_cutins)
        self.import_btn.clicked.connect(self.import_cutins)
        self.update_defaults()

    def update_defaults(self):
        dev = self.device()
        self.input_folder.setText(str(APP_ROOT / "sd" / "gfx" / "cutin" / dev))
        self.cutins_folder.setText(str(APP_ROOT / "cutins" / dev))
        self.output_folder.setText(str(APP_ROOT / "sd" / "gfx" / "cutin" / dev))

    def pick_dir(self, edit, title):
        path = QtWidgets.QFileDialog.getExistingDirectory(self, title, edit.text() or str(APP_ROOT))
        if path:
            edit.setText(path)

    def export_cutins(self):
        args = [self.input_folder.text().strip(), "-o", self.cutins_folder.text().strip()]
        if self.png_check.isChecked():
            args.append("--png")
        if self.recursive_check.isChecked():
            args.append("--recursive")
        self.run_script("export_cutins.py", args, f"Export Cut-ins ({self.device_label()})")

    def import_cutins(self):
        args = [self.input_folder.text().strip(), self.cutins_folder.text().strip(), "-o", self.output_folder.text().strip()]
        if self.recursive_check.isChecked():
            args.append("--recursive")
        self.run_script("import_cutins.py", args, f"Import Cut-ins ({self.device_label()})")

class ProfileImagesTab(CommandTab):
    def __init__(self, parent=None):
        super().__init__(ALL_DEVICES, parent)

    def _build_ui(self):
        super()._build_ui()

        group = QtWidgets.QGroupBox("Profile Images / Profile Pages")
        g = QtWidgets.QGridLayout(group)

        self.profile_root = QtWidgets.QLineEdit()
        self.export_dir = QtWidgets.QLineEdit()
        self.manifest = QtWidgets.QLineEdit()

        self.no_backup_check = QtWidgets.QCheckBox("No backup on import")
        self.no_backup_check.setChecked(True)

        self.pick_profile_root_btn = QtWidgets.QPushButton("Pick sd/profile")
        self.pick_export_dir_btn = QtWidgets.QPushButton("Pick Profile Images Folder")
        self.pick_manifest_btn = QtWidgets.QPushButton("Pick Manifest CSV")

        for b in [
            self.pick_profile_root_btn,
            self.pick_export_dir_btn,
            self.pick_manifest_btn,
        ]:
            b.setStyleSheet(SECONDARY_BTN_STYLE)

        self.export_btn = QtWidgets.QPushButton("Export Profile Images")
        self.import_btn = QtWidgets.QPushButton("Import Profile Images")

        self.export_btn.setStyleSheet(EXPORT_BTN_STYLE)
        self.import_btn.setStyleSheet(IMPORT_BTN_STYLE)

        g.addWidget(QtWidgets.QLabel("Profile root:"), 0, 0)
        g.addWidget(self.profile_root, 0, 1)
        g.addWidget(self.pick_profile_root_btn, 0, 2)

        g.addWidget(QtWidgets.QLabel("Profile images folder:"), 1, 0)
        g.addWidget(self.export_dir, 1, 1)
        g.addWidget(self.pick_export_dir_btn, 1, 2)

        g.addWidget(QtWidgets.QLabel("Manifest CSV:"), 2, 0)
        g.addWidget(self.manifest, 2, 1)
        g.addWidget(self.pick_manifest_btn, 2, 2)

        opts = QtWidgets.QHBoxLayout()
        opts.addWidget(self.no_backup_check)
        opts.addStretch(1)

        g.addLayout(opts, 3, 1, 1, 2)

        g.addWidget(self.export_btn, 4, 0)
        g.addWidget(self.import_btn, 4, 1)

        g.setColumnStretch(1, 1)

        self.body.addWidget(group)
        self.body.addStretch(1)

        self.type_combo.currentIndexChanged.connect(self.update_defaults)

        self.pick_profile_root_btn.clicked.connect(
            lambda: self.pick_dir(self.profile_root, "Select sd/profile folder")
        )

        self.pick_export_dir_btn.clicked.connect(
            lambda: self.pick_dir(self.export_dir, "Select profile_images folder")
        )

        self.pick_manifest_btn.clicked.connect(self.pick_manifest)

        self.export_btn.clicked.connect(self.export_profiles)
        self.import_btn.clicked.connect(self.import_profiles)

        self.update_defaults()

    def update_defaults(self):
        self.profile_root.setText(str(APP_ROOT / "sd" / "profile"))
        self.export_dir.setText(str(APP_ROOT / "profile_images"))
        self.manifest.setText(
            str(APP_ROOT / "profile_images" / "profile_pages_manifest.csv")
        )

    def pick_dir(self, edit, title):
        path = QtWidgets.QFileDialog.getExistingDirectory(
            self,
            title,
            edit.text() or str(APP_ROOT),
        )

        if path:
            edit.setText(path)

    def pick_manifest(self):
        path, _ = QtWidgets.QFileDialog.getSaveFileName(
            self,
            "Select manifest CSV",
            self.manifest.text(),
            "CSV files (*.csv);;All files (*)",
        )

        if path:
            self.manifest.setText(path)

    def export_profiles(self):
        self.run_script(
            "profile_page_tool.py",
            [
                "--mode",
                "export",
                "--profile-root",
                self.profile_root.text().strip(),
                "--export-dir",
                self.export_dir.text().strip(),
                "--manifest",
                self.manifest.text().strip(),
            ],
            "Export Profile Images",
        )

    def import_profiles(self):
        args = [
            "--mode",
            "import",
            "--profile-root",
            self.profile_root.text().strip(),
            "--export-dir",
            self.export_dir.text().strip(),
            "--manifest",
            self.manifest.text().strip(),
        ]

        if self.no_backup_check.isChecked():
            args.append("--no-backup")

        self.run_script(
            "profile_page_tool.py",
            args,
            "Import Profile Images",
        )

class AnalyzerCutinsTab(CommandTab):
    def __init__(self, parent=None):
        devices = [
            ("dvc", "Digivice Color"),
            ("d3c", "D-3 Color"),
            ("vb", "Vital Bracelet"),
            ("dmc", "Digital Monster Color"),
            ("penc", "Pendulum Color"),
            ("dm20", "Digital Monster 20th"),
            ("dmx", "Digital Monster X"),
            ("pen20", "Pendulum 20th"),
            ("penz", "Pendulum Z"),
            ("all", "All Devices"),
        ]

        super().__init__(devices, parent)

    def _build_ui(self):
        super()._build_ui()

        group = QtWidgets.QGroupBox(
            "Generate Analyzer Cut-ins and Import"
        )

        g = QtWidgets.QGridLayout(group)

        self.run_btn = QtWidgets.QPushButton(
            "Generate and Import Analyzer Cut-ins"
        )

        self.run_btn.setStyleSheet(IMPORT_BTN_STYLE)

        g.addWidget(self.run_btn, 1, 1)

        g.setColumnStretch(1, 1)

        self.body.addWidget(group)
        self.body.addStretch(1)

        self.run_btn.clicked.connect(self.run_make_import)

    def run_make_import(self):
        args = [
            "--fit",
            "crop",
            "--data-source",
            "terminal",
        ]

        if self.device() == "all":
            args.append("--all-devices")
        else:
            args.extend([
                "--device",
                self.device(),
            ])

        self.run_script(
            "make_and_import_all_analyzer_cutins.py",
            args,
            "Generate and Import Analyzer Cut-ins",
        )


class MainWindow(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        ensure_root_dirs()
        self.setWindowTitle("Pico Terminal Modifier GUI")
        self.resize(980, 700)
        tabs = QtWidgets.QTabWidget()
        tabs.addTab(SpritesTab(), "Sprites")
        tabs.addTab(CutinsTab(), "Cut-ins")
        tabs.addTab(AnalyzerCutinsTab(), "Digimon Analyzer Cut-ins")
        tabs.addTab(ProfileImagesTab(), "Profile Images")
        tabs.addTab(DataTab(), "Data")
        self.setCentralWidget(tabs)


def apply_dark_palette(app: QtWidgets.QApplication):
    app.setStyle("Fusion")
    palette = QtGui.QPalette()
    base_color = QtGui.QColor(45, 45, 45)
    alt_base = QtGui.QColor(60, 60, 60)
    text_color = QtGui.QColor(220, 220, 220)
    disabled_text = QtGui.QColor(127, 127, 127)
    highlight = QtGui.QColor(64, 128, 255)
    palette.setColor(QtGui.QPalette.Window, base_color)
    palette.setColor(QtGui.QPalette.WindowText, text_color)
    palette.setColor(QtGui.QPalette.Base, QtGui.QColor(30, 30, 30))
    palette.setColor(QtGui.QPalette.AlternateBase, alt_base)
    palette.setColor(QtGui.QPalette.ToolTipBase, text_color)
    palette.setColor(QtGui.QPalette.ToolTipText, text_color)
    palette.setColor(QtGui.QPalette.Text, text_color)
    palette.setColor(QtGui.QPalette.Button, alt_base)
    palette.setColor(QtGui.QPalette.ButtonText, text_color)
    palette.setColor(QtGui.QPalette.BrightText, QtGui.QColor(255, 0, 0))
    palette.setColor(QtGui.QPalette.Highlight, highlight)
    palette.setColor(QtGui.QPalette.HighlightedText, QtGui.QColor(0, 0, 0))
    palette.setColor(QtGui.QPalette.Disabled, QtGui.QPalette.Text, disabled_text)
    palette.setColor(QtGui.QPalette.Disabled, QtGui.QPalette.ButtonText, disabled_text)
    app.setPalette(palette)
    app.setStyleSheet("""
        QWidget { font-size: 10.5pt; }
        QGroupBox { border: 1px solid #666666; border-radius: 8px; margin-top: 10px; padding: 10px; font-weight: 700; }
        QGroupBox::title { subcontrol-origin: margin; left: 12px; padding: 0 4px; }
        QLineEdit, QPlainTextEdit, QComboBox, QSpinBox { background-color: #1e1e1e; color: #eeeeee; border: 1px solid #666666; border-radius: 4px; padding: 4px; }
        QTabWidget::pane { border: 1px solid #555555; }
        QTabBar::tab { background: #333333; color: #dddddd; padding: 8px 14px; border: 1px solid #555555; border-bottom: none; }
        QTabBar::tab:selected { background: #444444; color: white; }
        QScrollBar:vertical { background: #2b2b2b; width: 14px; margin: 0px; }
        QScrollBar::handle:vertical { background: #6ec6ff; min-height: 24px; border-radius: 6px; }
        QScrollBar:horizontal { background: #2b2b2b; height: 14px; margin: 0px; }
        QScrollBar::handle:horizontal { background: #6ec6ff; min-width: 24px; border-radius: 6px; }
        QScrollBar::add-line, QScrollBar::sub-line { width: 0px; height: 0px; }
    """)

def run_embedded_script():
    if len(sys.argv) >= 2 and sys.argv[1].endswith(".py"):
        script_name = Path(sys.argv[1]).stem

        # Remove script argument from argv
        sys.argv = [script_name] + sys.argv[2:]

        import importlib

        try:
            module = importlib.import_module(f"scripts.{script_name}")

            if hasattr(module, "main"):
                module.main()

            sys.exit(0)

        except SystemExit:
            raise

        except Exception:
            # IMPORTANT:
            # Do not print traceback here.
            # The parent script make_and_import_all_analyzer_cutins.py already captures
            # stdout/stderr and writes details into error.log.
            sys.exit(1)

def main():
    app = QtWidgets.QApplication(sys.argv)
    apply_dark_palette(app)
    win = MainWindow()
    win.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    run_embedded_script()
    main()