from typing import Optional
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QLabel, QSpinBox, QPushButton, QComboBox, QLineEdit, QTableWidget,
    QTableWidgetItem, QHeaderView, QAbstractItemView, QGroupBox,
    QStatusBar, QToolBar,
)
from PySide6.QtCore import Qt, QTimer, Signal, Slot


class SlaveSimulatorWindow(QMainWindow):
    log_received = Signal(str)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Modbus Slave Simulator")
        self.setMinimumSize(600, 400)
        self.resize(700, 500)

        self._server = None
        self._running = False

        cw = QWidget()
        self.setCentralWidget(cw)
        layout = QVBoxLayout(cw)

        conn_group = QGroupBox("Connection")
        conn = QGridLayout(conn_group)
        conn.addWidget(QLabel("Mode"), 0, 0)
        self._mode_combo = QComboBox()
        self._mode_combo.addItems(["TCP", "RTU"])
        conn.addWidget(self._mode_combo, 0, 1)
        conn.addWidget(QLabel("IP"), 0, 2)
        self._ip_input = QLineEdit("127.0.0.1")
        self._ip_input.setInputMask("000.000.000.000;_")
        conn.addWidget(self._ip_input, 0, 3)
        conn.addWidget(QLabel("Port"), 0, 4)
        self._port_input = QLineEdit("5020")
        self._port_input.setMaxLength(5)
        self._port_input.setFixedWidth(60)
        conn.addWidget(self._port_input, 0, 5)
        self._start_btn = QPushButton("Start Server")
        self._start_btn.clicked.connect(self._toggle_server)
        conn.addWidget(self._start_btn, 0, 6)
        layout.addWidget(conn_group)

        data_group = QGroupBox("Data Table")
        data_layout = QVBoxLayout(data_group)
        table_controls = QHBoxLayout()
        table_controls.addWidget(QLabel("Table:"))
        self._table_combo = QComboBox()
        self._table_combo.addItems(["Coils", "Discrete Inputs", "Holding Registers", "Input Registers"])
        self._table_combo.currentIndexChanged.connect(self._refresh_table)
        table_controls.addWidget(self._table_combo)
        table_controls.addWidget(QLabel("Start Addr:"))
        self._addr_spin = QSpinBox()
        self._addr_spin.setRange(0, 65535)
        table_controls.addWidget(self._addr_spin)
        table_controls.addWidget(QLabel(" Len:"))
        self._len_spin = QSpinBox()
        self._len_spin.setRange(1, 100)
        self._len_spin.setValue(20)
        self._len_spin.valueChanged.connect(self._refresh_table)
        table_controls.addStretch()
        data_layout.addLayout(table_controls)

        self._data_table = QTableWidget()
        self._data_table.setColumnCount(3)
        self._data_table.setHorizontalHeaderLabels(["Address", "Hex", "Value"])
        self._data_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        self._data_table.setEditTriggers(QAbstractItemView.DoubleClicked)
        self._data_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        data_layout.addWidget(self._data_table)
        layout.addWidget(data_group)

        self._set_value_btn = QPushButton("Set Value")
        self._set_value_btn.clicked.connect(self._set_value)
        layout.addWidget(self._set_value_btn)

        self._log = QStatusBar()
        self._log_label = QLabel("Stopped")
        self._log.addWidget(self._log_label, 1)
        layout.addWidget(self._log)

    def _toggle_server(self) -> None:
        if self._running:
            self._stop_server()
        else:
            self._start_server()

    def _start_server(self) -> None:
        import threading
        ip = self._ip_input.text().replace(" ", "")
        port = int(self._port_input.text())
        self._ip_input.setEnabled(False)
        self._port_input.setEnabled(False)
        self._start_btn.setText("Stop Server")
        self._log_label.setText(f"Starting TCP server on {ip}:{port}...")
        self._thread = threading.Thread(target=self._run_server, args=(ip, port), daemon=True)
        self._thread.start()
        QTimer.singleShot(500, lambda: self._log_label.setText(f"Server running on {ip}:{port}"))

    def _run_server(self, ip: str, port: int) -> None:
        from pymodbus.datastore import ModbusSequentialDataBlock, ModbusServerContext, ModbusDeviceContext
        from pymodbus.server import StartTcpServer
        block = ModbusSequentialDataBlock(0, [0] * 100)
        coil_block = ModbusSequentialDataBlock(0, [False] * 100)
        context = ModbusServerContext(
            slaves={
                1: ModbusDeviceContext(
                    di=coil_block,  # discrete inputs
                    co=coil_block,  # coils
                    ir=block,       # input registers
                    hr=block,       # holding registers
                )
            },
            single=False,
        )
        self._running = True
        try:
            StartTcpServer(context=context, address=(ip, port), defer_start=False)
        except Exception as e:
            self._log_label.setText(f"Error: {e}")
        finally:
            self._running = False

    def _stop_server(self) -> None:
        from pymodbus.server import ServerStop
        try:
            ServerStop()
        except Exception:
            pass
        self._running = False
        self._ip_input.setEnabled(True)
        self._port_input.setEnabled(True)
        self._start_btn.setText("Start Server")
        self._log_label.setText("Stopped")

    def _refresh_table(self) -> None:
        start = self._addr_spin.value()
        length = self._len_spin.value()
        table_type = self._table_combo.currentIndex()
        is_bool = table_type < 2
        self._data_table.setRowCount(length)
        for i in range(length):
            addr = start + i
            self._data_table.setItem(i, 0, QTableWidgetItem(f"{addr:04X}h"))
            self._data_table.setItem(i, 1, QTableWidgetItem("00"))
            self._data_table.setItem(i, 2, QTableWidgetItem("0"))
        self._data_table.resizeColumnsToContents()

    def _set_value(self) -> None:
        row = self._data_table.currentRow()
        if row < 0:
            return
        val_item = self._data_table.item(row, 2)
        hex_item = self._data_table.item(row, 1)
        if not val_item:
            return
        try:
            val = int(val_item.text())
            hex_item.setText(f"{val:04X}" if self._table_combo.currentIndex() >= 2 else ("01" if val else "00"))
        except ValueError:
            pass
