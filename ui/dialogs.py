from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QGridLayout, QLabel, QComboBox, QLineEdit,
    QSpinBox, QDialogButtonBox, QMainWindow, QWidget, QListView,
    QPlainTextEdit, QToolBar, QAbstractItemView, QPushButton,
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QIcon, QPixmap, QPalette, QColor, QFont

from modbus.models import ConnectionSettings, ConnectionType, Parity


EXCEPTION_CODES = [
    (1, "Illegal Function", "Function code not recognized or not allowed by the slave"),
    (2, "Illegal Data Address", "Data address specified in the request is out of range"),
    (3, "Illegal Data Value", "Value in the request data field is invalid"),
    (4, "Slave Device Failure", "Irrecoverable error occurred while the slave attempted the action"),
    (5, "Acknowledge", "Request accepted but processing requires long time (poll for completion)"),
    (6, "Slave Device Busy", "Slave is busy processing another command (retry later)"),
    (7, "Negative Acknowledge", "Slave cannot perform the requested function"),
    (8, "Memory Parity Error", "Memory parity error detected in the slave's data store"),
    (9, "Gateway Path Unavailable", "Gateway path to the target device is unavailable"),
    (10, "Gateway Target Device Failed to Respond", "Target device did not respond to the gateway"),
    (11, "Gateway Target Device Not Responding", "Target device is not responding on the network"),
]


class ExceptionCodesDialog(QDialog):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Modbus Exception Codes")
        self.setMinimumSize(520, 360)
        layout = QVBoxLayout(self)
        from PySide6.QtWidgets import QTableWidget, QHeaderView, QAbstractItemView
        table = QTableWidget(len(EXCEPTION_CODES), 3)
        table.setHorizontalHeaderLabels(["Code", "Name", "Description"])
        table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        table.setSelectionBehavior(QAbstractItemView.SelectRows)
        for row, (code, name, desc) in enumerate(EXCEPTION_CODES):
            table.setItem(row, 0, QTableWidgetItem(str(code)))
            table.setItem(row, 1, QTableWidgetItem(name))
            table.setItem(row, 2, QTableWidgetItem(desc))
        layout.addWidget(table)
        buttons = QDialogButtonBox(QDialogButtonBox.Close)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)


class SettingsModbusRTUDialog(QDialog):
    def __init__(self, settings: ConnectionSettings, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Modbus RTU Settings")
        self.setMinimumSize(220, 220)
        self.setMaximumSize(300, 300)
        self._settings = settings

        layout = QVBoxLayout(self)
        grid = QGridLayout()

        grid.addWidget(QLabel("Serial port"), 0, 0)
        self._port_combo = QComboBox()
        self._port_combo.setEditable(True)
        self._scan_ports()
        grid.addWidget(self._port_combo, 0, 1)

        grid.addWidget(QLabel("Baud"), 1, 0)
        self._baud_combo = QComboBox()
        for b in ["110", "300", "600", "1200", "2400", "4800", "9600",
                   "14400", "19200", "28800", "38400", "57600",
                   "115200", "128000", "256000", "921600"]:
            self._baud_combo.addItem(b)
        self._baud_combo.setCurrentText(str(settings.baud_rate))
        grid.addWidget(self._baud_combo, 1, 1)

        grid.addWidget(QLabel("Data Bits"), 2, 0)
        self._data_bits_combo = QComboBox()
        self._data_bits_combo.addItems(["7", "8"])
        self._data_bits_combo.setCurrentText(str(settings.data_bits))
        grid.addWidget(self._data_bits_combo, 2, 1)

        grid.addWidget(QLabel("Stop Bits"), 3, 0)
        self._stop_bits_combo = QComboBox()
        self._stop_bits_combo.addItems(["1", "1.5", "2"])
        self._stop_bits_combo.setCurrentText(str(settings.stop_bits))
        grid.addWidget(self._stop_bits_combo, 3, 1)

        grid.addWidget(QLabel("Parity"), 4, 0)
        self._parity_combo = QComboBox()
        self._parity_combo.addItems(["None", "Odd", "Even"])
        self._parity_combo.setCurrentText(
            {"N": "None", "E": "Even", "O": "Odd"}[settings.parity.value]
        )
        grid.addWidget(self._parity_combo, 4, 1)

        grid.addWidget(QLabel("RTS"), 5, 0)
        self._rts_combo = QComboBox()
        self._rts_combo.addItems(["None", "Up", "Down", "Toggle"])
        grid.addWidget(self._rts_combo, 5, 1)

        layout.addLayout(grid)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _scan_ports(self) -> None:
        self._port_combo.clear()
        try:
            import serial.tools.list_ports
            for p in serial.tools.list_ports.comports():
                self._port_combo.addItem(f"{p.device} - {p.description}")
        except Exception:
            pass
        if self._settings.com_port:
            self._port_combo.setCurrentText(self._settings.com_port)

    def get_settings(self) -> ConnectionSettings:
        self._settings.com_port = self._port_combo.currentText().split(" - ")[0]
        self._settings.baud_rate = int(self._baud_combo.currentText())
        self._settings.data_bits = int(self._data_bits_combo.currentText())
        self._settings.stop_bits = float(self._stop_bits_combo.currentText())
        parity_map = {"None": Parity.NONE, "Odd": Parity.ODD, "Even": Parity.EVEN}
        self._settings.parity = parity_map[self._parity_combo.currentText()]
        return self._settings


class SettingsModbusTCPDialog(QDialog):
    def __init__(self, settings: ConnectionSettings, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Modbus TCP Settings")
        self.setMinimumSize(240, 110)
        self.setMaximumSize(300, 160)
        self._settings = settings

        layout = QVBoxLayout(self)
        grid = QGridLayout()

        grid.addWidget(QLabel("Slave IP"), 1, 0)
        self._ip_input = QLineEdit(settings.host)
        self._ip_input.setInputMask("999.999.999.999;_")
        grid.addWidget(self._ip_input, 1, 1)

        grid.addWidget(QLabel("TCP Port"), 2, 0)
        self._port_input = QLineEdit(str(settings.port))
        self._port_input.setMaxLength(5)
        grid.addWidget(self._port_input, 2, 1)

        layout.addLayout(grid)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def get_settings(self) -> ConnectionSettings:
        self._settings.host = self._ip_input.text().replace(" ", "")
        try:
            self._settings.port = int(self._port_input.text())
        except ValueError:
            pass
        return self._settings


class SettingsDialog(QDialog):
    def __init__(self, settings: ConnectionSettings, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Settings")
        self.setMinimumSize(220, 120)
        self.setMaximumSize(320, 150)
        self._settings = settings

        layout = QVBoxLayout(self)
        grid = QGridLayout()

        grid.addWidget(QLabel("Response Timeout (sec)"), 1, 1)
        self._timeout_spin = QSpinBox()
        self._timeout_spin.setRange(0, 20)
        self._timeout_spin.setValue(settings.timeout)
        grid.addWidget(self._timeout_spin, 1, 2)

        grid.addWidget(QLabel("Max No Of Bus Monitor Lines"), 0, 1)
        self._max_lines_spin = QSpinBox()
        self._max_lines_spin.setRange(1, 500)
        self._max_lines_spin.setSingleStep(50)
        self._max_lines_spin.setValue(50)
        grid.addWidget(self._max_lines_spin, 0, 2)

        grid.addWidget(QLabel("Base Addr"), 2, 1)
        self._base_addr_spin = QSpinBox()
        self._base_addr_spin.setRange(0, 1)
        self._base_addr_spin.setValue(0)
        grid.addWidget(self._base_addr_spin, 2, 2)

        layout.addLayout(grid)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def get_settings(self) -> ConnectionSettings:
        self._settings.timeout = self._timeout_spin.value()
        return self._settings


class BusMonitorWindow(QMainWindow):
    def __init__(self, worker, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Bus Monitor")
        self.setMinimumSize(560, 360)
        self.resize(600, 400)

        self._worker = worker
        self._packets = []
        self._max_lines = 50

        cw = QWidget()
        self.setCentralWidget(cw)
        layout = QVBoxLayout(cw)

        lbl_raw = QLabel("Raw Data")
        lbl_raw.setFont(QFont("", 0, QFont.Weight.Bold))
        layout.addWidget(lbl_raw)

        self._list = QListView()
        self._list.setFont(QFont("Consolas", 9))
        self._list.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self._list.setAlternatingRowColors(True)
        self._list.setSelectionMode(QAbstractItemView.SingleSelection)
        self._list.setSelectionBehavior(QAbstractItemView.SelectRows)
        layout.addWidget(self._list)

        lbl_pdu = QLabel("PDU")
        lbl_pdu.setFont(QFont("", 0, QFont.Weight.Bold))
        layout.addWidget(lbl_pdu)

        self._pdu_view = QPlainTextEdit()
        self._pdu_view.setFont(QFont("Consolas", 9))
        self._pdu_view.setReadOnly(True)
        self._pdu_view.setTextInteractionFlags(Qt.NoTextInteraction)
        layout.addWidget(self._pdu_view)

        tb = self.addToolBar("Bus Monitor")
        tb.setObjectName("BusMonitorToolBar")
        clear_act = tb.addAction("Clear")
        clear_act.triggered.connect(self._clear)
        save_act = tb.addAction("Save")
        save_act.triggered.connect(self._save)

        from PySide6.QtCore import QStringListModel
        self._model = QStringListModel()
        self._list.setModel(self._model)

        self._worker.packet_logged.connect(self._on_packet)

    def _parse_pdu(self, hex_str: str) -> str:
        parts = hex_str.strip().split()
        if not parts:
            return "No data"
        lines = []
        if len(parts) >= 2:
            fc_byte = int(parts[1], 16)
            is_exception = fc_byte >= 0x80
            fc = fc_byte & 0x7F
            fc_name = {
                1: "Read Coils", 2: "Read Discrete Inputs", 3: "Read Holding Registers",
                4: "Read Input Registers", 5: "Write Single Coil", 6: "Write Single Register",
                15: "Write Multiple Coils", 16: "Write Multiple Registers",
            }.get(fc, f"FC{fc:02d}")
            lines.append(f"Function Code: {fc_byte:02X}h ({'EXCEPTION: ' if is_exception else ''}{fc_name})")
            if is_exception and len(parts) > 2:
                exc_code = int(parts[2], 16)
                exc_names = {
                    1: "Illegal Function", 2: "Illegal Data Address", 3: "Illegal Data Value",
                    4: "Slave Device Failure", 5: "Acknowledge", 6: "Slave Device Busy",
                    7: "Negative Acknowledge", 8: "Memory Parity Error",
                    9: "Gateway Path Unavailable", 10: "Gateway Target Failed to Respond",
                    11: "Gateway Target Device Not Responding",
                }
                lines.append(f"  Exception: {exc_code} - {exc_names.get(exc_code, 'Unknown')}")
        if len(parts) >= 3 and not (len(parts) >= 2 and int(parts[1], 16) >= 0x80):
            addr_bytes = parts[2:4] if len(parts) > 3 else parts[2:]
            if addr_bytes:
                lines.append(f"  Address: {' '.join(addr_bytes)}h")
            if len(parts) > 4:
                data_bytes = parts[4:]
                if len(data_bytes) > 2:
                    lines.append(f"  Data ({len(data_bytes)} bytes): {' '.join(data_bytes)}")
        return "\n".join(lines)

    def _on_packet(self, packet) -> None:
        line = f"{packet.timestamp}  {packet.direction}  {packet.hex_data}  {packet.ascii_data}  CRC:{packet.crc}  LEN:{packet.length}"
        self._packets.append(line)
        if len(self._packets) > self._max_lines:
            self._packets.pop(0)
        self._model.setStringList(self._packets)
        self._list.scrollToBottom()
        pdu_text = self._parse_pdu(packet.hex_data)
        self._pdu_view.setPlainText(pdu_text)

    def _clear(self) -> None:
        self._packets.clear()
        self._model.setStringList([])
        self._pdu_view.clear()

    def _save(self) -> None:
        from PySide6.QtWidgets import QFileDialog
        path, _ = QFileDialog.getSaveFileName(self, "Save Bus Log", "bus_monitor.log", "Log Files (*.log)")
        if path:
            with open(path, "w") as f:
                f.write("\n".join(self._packets))
