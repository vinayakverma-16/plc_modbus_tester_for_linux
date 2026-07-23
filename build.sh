#!/bin/bash
# Build script for PLC Modbus Tester (Linux)

pip install pyinstaller -q

python -m PyInstaller --onefile --windowed --name "PLC_Modbus_Tester" \
    --add-data "assets:assets" \
    --add-data "ManModbus:ManModbus" \
    --hidden-import "serial.tools.list_ports" \
    --hidden-import "pymodbus.client" \
    --hidden-import "pymodbus.server" \
    --hidden-import "pymodbus.datastore" \
    --clean main.py

echo ""
echo "Build complete! Binary at: dist/PLC_Modbus_Tester"
