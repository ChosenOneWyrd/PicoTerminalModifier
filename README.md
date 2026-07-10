Mac Build cmd:
pyinstaller \
  --name "PicoTerminalModifier" \
  --onefile \
  --windowed \
  --add-binary "third_party/tesseract:." \
  --icon "icons/dterminal.icns" \
  --add-data "scripts:scripts" \
  --add-data "generated_images:generated_images" \
  --add-data "Digimon_analyzer_blank.jpg:." \
  scripts/pico_modifier_gui.py

Windows Build cmd:
pyinstaller --name "PicoTerminalModifier" --onefile --noconsole --add-data "third_party\tesseract_win;tesseract_win" --icon "icons/dterminal.icns" --add-data "scripts:scripts" --add-data "generated_images:generated_images" --add-data "Digimon_analyzer_blank.jpg:." scripts/pico_modifier_gui.py