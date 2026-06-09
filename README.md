pyinstaller \
  --name "PicoTerminalModifier" \
  --onefile \
  --windowed \
  --icon "icons/dterminal.icns" \
  --add-data "scripts:scripts" \
  --add-data "generated_images:generated_images" \
  --add-data "Digimon_analyzer_blank.jpg:." \
  scripts/pico_modifier_gui.py

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