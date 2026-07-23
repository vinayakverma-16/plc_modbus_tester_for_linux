import os
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QFrame, QGridLayout,
    QLabel, QToolBar, QPushButton, QComboBox, QSpinBox, QLineEdit,
    QStatusBar, QMenuBar, QMenu, QMessageBox, QInputDialog,
    QApplication, QTableView, QHeaderView,
)
from PySide6.QtCore import Qt, Slot, QSettings, QTimer, Signal
from PySide6.QtGui import QAction, QKeySequence, QPixmap, QPalette, QColor, QIcon
from PySide6.QtWidgets import QDialog

from modbus.client import ModbusClient
from modbus.models import ConnectionSettings, PollSettings, ConnectionType, Parity, ModbusFunction
from utils.session import SessionManager
from utils.profiles import ProfileManager
from ui.register_view import RegisterView
from ui.dialogs import SettingsModbusRTUDialog, SettingsModbusTCPDialog, SettingsDialog, BusMonitorWindow
from ui.slave_simulator import SlaveSimulatorWindow


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("PLC Modbus Tester")
        self.setMinimumSize(560, 360)
        self.resize(700, 480)
        self._first_show = True

        self._client = ModbusClient()
        self._session_mgr = SessionManager()
        self._profile_mgr = ProfileManager()
        self._dark_mode = False
        self._settings = ConnectionSettings()
        self._poll_settings = PollSettings()

        self._build_actions()
        self._build_menu_bar()
        self._build_toolbar()
        self._build_central()
        self._build_status_bar()
        self._connect_signals()

    def _build_actions(self) -> None:
        self._actions = {}

        def a(name, text, icon=None, checkable=False, shortcut=None):
            act = QAction(text, self)
            if icon:
                act.setIcon(QIcon(icon))
            act.setCheckable(checkable)
            if shortcut:
                act.setShortcut(shortcut)
            self._actions[name] = act
            return act

        a("Connect", "Connect", checkable=True)
        a("ReadWrite", "Read / Write")
        a("Scan", "Scan", checkable=True)
        a("ClearTable", "Clear Table")
        a("ResetCounters", "Reset Counters")
        a("LogFile", "Log File")
        a("BusMonitor", "Bus Monitor")
        a("ModbusRTU", "Modbus RTU...")
        a("ModbusTCP", "Modbus TCP...")
        a("Settings", "Settings...")
        a("ModbusManual", "Modbus Manual")
        a("About", "About...")
        a("Exit", "Exit", shortcut=QKeySequence.Quit)
        a("SlaveSimulator", "Slave Simulator")

    def _setup_frames(self) -> None:
        self._frames = {}

    def _build_menu_bar(self) -> None:
        mb = self.menuBar()
        mb.setNativeMenuBar(False)

        file_menu = mb.addMenu("&File")
        file_menu.addAction(self._actions["Exit"])

        options_menu = mb.addMenu("&Options")
        options_menu.addAction(self._actions["ModbusRTU"])
        options_menu.addAction(self._actions["ModbusTCP"])
        options_menu.addSeparator()
        options_menu.addAction(self._actions["Settings"])

        commands_menu = mb.addMenu("&Commands")
        commands_menu.addAction(self._actions["Connect"])
        commands_menu.addAction(self._actions["ReadWrite"])
        commands_menu.addAction(self._actions["Scan"])
        commands_menu.addAction(self._actions["ClearTable"])
        commands_menu.addAction(self._actions["ResetCounters"])

        view_menu = mb.addMenu("&View")
        view_menu.addAction(self._actions["LogFile"])
        view_menu.addAction(self._actions["BusMonitor"])
        view_menu.addSeparator()
        view_menu.addAction("Slave Simulator", self._on_slave_simulator)

        help_menu = mb.addMenu("&Help")
        help_menu.addAction(self._actions["ModbusManual"])
        help_menu.addAction("Exception Codes", self._on_exception_codes)
        help_menu.addSeparator()
        help_menu.addAction(self._actions["About"])

    def _build_toolbar(self) -> None:
        tb = QToolBar("Main")
        tb.setMovable(False)
        tb.setFloatable(False)
        tb.setObjectName("MainToolBar")
        self.addToolBar(tb)

        acts = [
            "Connect", "ReadWrite", "Scan", "ClearTable", "ResetCounters",
            None, "LogFile", "BusMonitor",
            None, "ModbusRTU", "ModbusTCP", "Settings",
            None, "SlaveSimulator", "ModbusManual", "About", "Exit",
        ]
        for item in acts:
            if item is None:
                tb.addSeparator()
            else:
                tb.addAction(self._actions[item])

    def _build_central(self) -> None:
        cw = QWidget()
        layout = QVBoxLayout(cw)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)

        frame1 = QFrame()
        frame1.setFrameShape(QFrame.StyledPanel)
        fl1 = QGridLayout(frame1)
        fl1.setContentsMargins(8, 4, 8, 4)
        fl1.setSpacing(6)

        fl1.addWidget(QLabel("Modbus Mode"), 0, 0)
        self._mode_combo = QComboBox()
        self._mode_combo.addItems(["RTU", "TCP"])
        fl1.addWidget(self._mode_combo, 0, 1)

        self._slave_label = QLabel("Slave Addr")
        fl1.addWidget(self._slave_label, 0, 2)
        self._slave_spin = QSpinBox()
        self._slave_spin.setRange(1, 255)
        self._slave_spin.setValue(1)
        self._slave_spin.setFixedWidth(70)
        fl1.addWidget(self._slave_spin, 0, 3)

        fl1.addWidget(QLabel("Scan Rate (ms)"), 0, 4)
        self._interval_spin = QSpinBox()
        self._interval_spin.setRange(100, 10000)
        self._interval_spin.setSingleStep(100)
        self._interval_spin.setValue(1000)
        self._interval_spin.setFixedWidth(80)
        fl1.addWidget(self._interval_spin, 0, 5)
        fl1.setColumnStretch(6, 1)

        self._rtu_widget = QWidget()
        rtu = QHBoxLayout(self._rtu_widget)
        rtu.setContentsMargins(0, 0, 0, 0)
        rtu.setSpacing(6)
        rtu.addWidget(QLabel("Port"))
        self._rtu_port_combo = QComboBox()
        self._rtu_port_combo.setEditable(True)
        self._rtu_port_combo.setMinimumWidth(100)
        rtu.addWidget(self._rtu_port_combo)
        rtu.addWidget(QLabel("Baud"))
        self._rtu_baud_combo = QComboBox()
        for b in ["9600", "19200", "38400", "57600", "115200"]:
            self._rtu_baud_combo.addItem(b)
        self._rtu_baud_combo.setFixedWidth(80)
        rtu.addWidget(self._rtu_baud_combo)
        rtu.addWidget(QLabel("Data"))
        self._rtu_data_combo = QComboBox()
        self._rtu_data_combo.addItems(["8", "7"])
        self._rtu_data_combo.setFixedWidth(55)
        rtu.addWidget(self._rtu_data_combo)
        rtu.addWidget(QLabel("Stop"))
        self._rtu_stop_combo = QComboBox()
        self._rtu_stop_combo.addItems(["1", "2"])
        self._rtu_stop_combo.setFixedWidth(55)
        rtu.addWidget(self._rtu_stop_combo)
        rtu.addWidget(QLabel("Parity"))
        self._rtu_parity_combo = QComboBox()
        self._rtu_parity_combo.addItems(["None", "Even", "Odd"])
        self._rtu_parity_combo.setFixedWidth(80)
        rtu.addWidget(self._rtu_parity_combo)
        rtu.addStretch()
        fl1.addWidget(self._rtu_widget, 1, 0, 1, 6)

        self._tcp_widget = QWidget()
        tcp = QHBoxLayout(self._tcp_widget)
        tcp.setContentsMargins(0, 0, 0, 0)
        tcp.setSpacing(6)
        tcp.addWidget(QLabel("IP Address"))
        self._tcp_ip_input = QLineEdit("127.0.0.1")
        self._tcp_ip_input.setInputMask("000.000.000.000;_")
        self._tcp_ip_input.setFixedWidth(140)
        tcp.addWidget(self._tcp_ip_input)
        tcp.addWidget(QLabel("Port"))
        self._tcp_port_input = QLineEdit("502")
        self._tcp_port_input.setMaxLength(5)
        self._tcp_port_input.setFixedWidth(60)
        tcp.addWidget(self._tcp_port_input)
        tcp.addStretch()
        self._tcp_widget.setVisible(False)
        fl1.addWidget(self._tcp_widget, 1, 0, 1, 6)
        layout.addWidget(frame1)

        frame2 = QFrame()
        frame2.setFrameShape(QFrame.StyledPanel)
        fl2 = QGridLayout(frame2)
        fl2.setContentsMargins(8, 4, 8, 4)
        fl2.setSpacing(6)
        fl2.addWidget(QLabel("Function Code"), 0, 0)
        self._fc_combo = QComboBox()
        self._fc_combo.setMinimumWidth(220)
        for fc in ModbusFunction:
            self._fc_combo.addItem(f"FC{fc.value:02d} {fc.name.replace('_', ' ').title()}", fc.value)
        fl2.addWidget(self._fc_combo, 0, 1)
        fl2.addWidget(QLabel("Format"), 0, 2)
        self._format_combo = QComboBox()
        self._format_combo.addItems(["Binary", "Decimal", "Hex"])
        self._format_combo.setCurrentIndex(1)
        self._format_combo.setFixedWidth(90)
        fl2.addWidget(self._format_combo, 0, 3)
        fl2.setColumnStretch(4, 1)

        fl2.addWidget(QLabel("Scan From"), 1, 0)
        self._addr_spin = QSpinBox()
        self._addr_spin.setRange(0, 65535)
        self._addr_spin.setFixedWidth(90)
        fl2.addWidget(self._addr_spin, 1, 1)
        fl2.addWidget(QLabel("Scan To"), 1, 2)
        self._addr_to_spin = QSpinBox()
        self._addr_to_spin.setRange(0, 65535)
        self._addr_to_spin.setValue(9)
        self._addr_to_spin.setFixedWidth(90)
        fl2.addWidget(self._addr_to_spin, 1, 3)
        self._qty_label = QLabel("Qty")
        fl2.addWidget(self._qty_label, 1, 4)
        self._qty_spin = QSpinBox()
        self._qty_spin.setRange(1, 125)
        self._qty_spin.setValue(10)
        self._qty_spin.setFixedWidth(70)
        fl2.addWidget(self._qty_spin, 1, 5)
        fl2.setColumnStretch(6, 1)
        layout.addWidget(frame2)

        self._register_view = RegisterView()
        self._register_view._table.verticalHeader().setVisible(False)
        self._register_view._table.horizontalHeader().setVisible(False)
        layout.addWidget(self._register_view, 1)

        self.setCentralWidget(cw)

    def _build_status_bar(self) -> None:
        sb = self.statusBar()
        sb.setObjectName("StatusBar")
        self._status_ind = QLabel()
        self._status_ind.setFixedSize(14, 14)
        self._status_ind.setStyleSheet("background-color: #888; border-radius: 7px; border: 1px solid #555;")
        sb.addWidget(self._status_ind)

        self._status_text = QLabel("Disconnected")
        sb.addWidget(self._status_text, 10)

        self._status_packets = QLabel("Packets : 0")
        self._status_packets.setStyleSheet("color: blue;")
        sb.addPermanentWidget(self._status_packets)

        self._status_errors = QLabel("Errors : 0")
        self._status_errors.setStyleSheet("color: red;")
        sb.addPermanentWidget(self._status_errors)

    def _connect_signals(self) -> None:
        worker = self._client.worker

        self._actions["Connect"].toggled.connect(self._on_connect_toggled)
        self._actions["ReadWrite"].triggered.connect(self._on_read_write)
        self._actions["Scan"].toggled.connect(self._on_scan_toggled)
        self._actions["ClearTable"].triggered.connect(self._on_clear)
        self._actions["ResetCounters"].triggered.connect(self._on_reset_counters)
        self._actions["LogFile"].triggered.connect(self._on_log_file)
        self._actions["BusMonitor"].triggered.connect(self._on_bus_monitor)
        self._actions["ModbusRTU"].triggered.connect(self._on_modbus_rtu)
        self._actions["ModbusTCP"].triggered.connect(self._on_modbus_tcp)
        self._actions["Settings"].triggered.connect(self._on_settings)
        self._actions["ModbusManual"].triggered.connect(self._on_modbus_manual)
        self._actions["About"].triggered.connect(self._on_about)
        self._actions["SlaveSimulator"].triggered.connect(self._on_slave_simulator)

        self._mode_combo.currentIndexChanged.connect(self._on_mode_changed)
        self._fc_combo.currentIndexChanged.connect(self._on_fc_changed)
        self._format_combo.currentIndexChanged.connect(self._on_format_changed)
        self._slave_spin.valueChanged.connect(self._on_slave_changed)
        self._addr_spin.valueChanged.connect(self._on_addr_changed)
        self._qty_spin.valueChanged.connect(self._on_qty_changed)
        self._interval_spin.valueChanged.connect(self._on_interval_changed)
        self._addr_to_spin.valueChanged.connect(self._on_addr_to_changed)
        self._rtu_port_combo.currentIndexChanged.connect(self._on_status_changed)
        self._rtu_baud_combo.currentIndexChanged.connect(self._on_status_changed)
        self._rtu_data_combo.currentIndexChanged.connect(self._on_status_changed)
        self._rtu_stop_combo.currentIndexChanged.connect(self._on_status_changed)
        self._rtu_parity_combo.currentIndexChanged.connect(self._on_status_changed)
        self._tcp_ip_input.textChanged.connect(self._on_status_changed)
        self._tcp_port_input.textChanged.connect(self._on_status_changed)

        worker.connection_changed.connect(self._on_connection_changed)
        worker.data_received.connect(self._register_view.update_data)
        worker.error_occurred.connect(self._on_error)
        worker.stats_updated.connect(self._on_stats_updated)

    def _on_mode_changed(self, idx: int) -> None:
        is_rtu = idx == 0
        self._rtu_widget.setVisible(is_rtu)
        self._tcp_widget.setVisible(not is_rtu)
        self._slave_label.setText("Slave Addr" if is_rtu else "Unit ID")
        if is_rtu:
            self._scan_com_ports()
        self._update_status_text()

    def _on_fc_changed(self, idx: int) -> None:
        fc = self._fc_combo.currentData()
        if fc in (ModbusFunction.READ_COILS.value, ModbusFunction.READ_INPUTS.value,
                  ModbusFunction.WRITE_SINGLE_COIL.value, ModbusFunction.WRITE_MULTIPLE_COILS.value):
            self._qty_label.setText("Number of Coils")
            if fc in (ModbusFunction.WRITE_SINGLE_COIL.value,):
                self._qty_spin.setValue(1)
                self._qty_spin.setEnabled(False)
            else:
                self._qty_spin.setEnabled(True)
        else:
            self._qty_label.setText("Number of Registers")
            if fc in (ModbusFunction.WRITE_SINGLE_REGISTER.value,):
                self._qty_spin.setValue(1)
                self._qty_spin.setEnabled(False)
            else:
                self._qty_spin.setEnabled(True)

    def _scan_com_ports(self) -> None:
        current = self._rtu_port_combo.currentText()
        self._rtu_port_combo.clear()
        try:
            import serial.tools.list_ports
            for p in serial.tools.list_ports.comports():
                self._rtu_port_combo.addItem(f"{p.device} - {p.description}")
        except Exception:
            pass
        if current:
            idx = self._rtu_port_combo.findText(current.split(" - ")[0], Qt.MatchFlag.MatchStartsWith)
            if idx >= 0:
                self._rtu_port_combo.setCurrentIndex(idx)

    def _on_format_changed(self, idx: int) -> None:
        pass

    def _on_slave_changed(self, val: int) -> None:
        pass

    def _on_addr_changed(self, val: int) -> None:
        if val > self._addr_to_spin.value():
            self._addr_to_spin.setValue(val)

    def _on_addr_to_changed(self, val: int) -> None:
        if val < self._addr_spin.value():
            self._addr_spin.setValue(val)

    def _on_qty_changed(self, val: int) -> None:
        pass

    def _on_interval_changed(self, val: int) -> None:
        pass

    def _on_status_changed(self) -> None:
        self._update_status_text()

    def _get_connection_settings(self) -> ConnectionSettings:
        if self._mode_combo.currentIndex() == 0:
            self._settings.connection_type = ConnectionType.RTU
            port_text = self._rtu_port_combo.currentText().split(" - ")[0]
            self._settings.com_port = port_text
            self._settings.baud_rate = int(self._rtu_baud_combo.currentText())
            self._settings.data_bits = int(self._rtu_data_combo.currentText())
            self._settings.stop_bits = float(self._rtu_stop_combo.currentText())
            parity_map = {"None": Parity.NONE, "Even": Parity.EVEN, "Odd": Parity.ODD}
            self._settings.parity = parity_map[self._rtu_parity_combo.currentText()]
        else:
            self._settings.connection_type = ConnectionType.TCP
            self._settings.host = self._tcp_ip_input.text().replace(" ", "")
            self._settings.port = int(self._tcp_port_input.text())
        self._settings.slave_id = self._slave_spin.value()
        return self._settings

    def _get_poll_settings(self) -> PollSettings:
        s = PollSettings()
        s.function_code = ModbusFunction(self._fc_combo.currentData())
        s.start_address = self._addr_spin.value()
        qty = self._addr_to_spin.value() - self._addr_spin.value() + 1
        max_qty = 2000 if s.function_code in (ModbusFunction.READ_COILS, ModbusFunction.READ_INPUTS) else 125
        s.quantity = min(qty, max_qty)
        s.poll_interval_ms = self._interval_spin.value()
        s.continuous = True
        return s

    @Slot(bool)
    def _on_connect_toggled(self, checked: bool) -> None:
        if checked:
            self._settings = self._get_connection_settings()
            self._client.connect(self._settings)
        else:
            self._client.disconnect()

    @Slot()
    def _on_read_write(self) -> None:
        poll = self._get_poll_settings()
        self._client.worker._poll_settings = poll
        registers = self._client.read_once()
        if registers:
            self._register_view.update_data(registers)

    @Slot(bool)
    def _on_scan_toggled(self, checked: bool) -> None:
        if checked:
            self._client.start_polling(self._get_poll_settings())
        else:
            self._client.stop_polling()

    @Slot()
    def _on_clear(self) -> None:
        self._register_view.clear_registers()

    @Slot()
    def _on_reset_counters(self) -> None:
        self._client.worker._stats.packets_sent = 0
        self._client.worker._stats.packets_received = 0
        self._client.worker._stats.errors = 0
        self._update_status_text()

    @Slot()
    def _on_log_file(self) -> None:
        import os.path
        log_path = os.path.join(os.path.dirname(__file__), "..", "QModMaster.log")
        if os.path.exists(log_path):
            import subprocess
            subprocess.Popen(["xdg-open", log_path])

    @Slot()
    def _on_bus_monitor(self) -> None:
        from ui.packet_monitor import PacketMonitor
        self._bus_monitor = BusMonitorWindow(self._client.worker)
        self._bus_monitor.show()

    @Slot()
    def _on_modbus_rtu(self) -> None:
        dlg = SettingsModbusRTUDialog(self._settings, self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            self._settings = dlg.get_settings()
            self._update_status_text()

    @Slot()
    def _on_modbus_tcp(self) -> None:
        dlg = SettingsModbusTCPDialog(self._settings, self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            self._settings = dlg.get_settings()
            self._update_status_text()

    @Slot()
    def _on_settings(self) -> None:
        dlg = SettingsDialog(self._settings, self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            self._settings = dlg.get_settings()

    @Slot()
    def _on_modbus_manual(self) -> None:
        import os.path, sys
        base = os.path.dirname(sys.executable) if getattr(sys, 'frozen', False) else os.path.join(os.path.dirname(__file__), "..")
        man_path = os.path.join(base, "ManModbus", "index.html")
        if os.path.exists(man_path):
            import subprocess
            subprocess.Popen(["xdg-open", man_path])

    @Slot()
    def _on_slave_simulator(self) -> None:
        self._slave_sim = SlaveSimulatorWindow(self)
        self._slave_sim.show()

    @Slot()
    def _on_exception_codes(self) -> None:
        from ui.dialogs import ExceptionCodesDialog
        dlg = ExceptionCodesDialog(self)
        dlg.exec()

    @Slot()
    def _on_about(self) -> None:
        QMessageBox.about(
            self, "About",
            "QModMaster\n\n"
            "A free Qt-based implementation of a ModBus master application.\n\n"
            "Built with Python + PySide6 + pymodbus"
        )

    @Slot(bool, str)
    def _on_connection_changed(self, connected: bool, msg: str) -> None:
        if connected:
            self._status_ind.setStyleSheet("background-color: #00cc00; border-radius: 7px; border: 1px solid #009900;")
            self._actions["Connect"].setChecked(True)
            self._actions["ReadWrite"].setEnabled(True)
            self._actions["Scan"].setEnabled(True)
            self._mode_combo.setEnabled(False)
        else:
            self._status_ind.setStyleSheet("background-color: #cc0000; border-radius: 7px; border: 1px solid #990000;")
            self._actions["Connect"].setChecked(False)
            self._actions["ReadWrite"].setEnabled(False)
            self._actions["Scan"].setEnabled(False)
            self._actions["Scan"].setChecked(False)
            self._mode_combo.setEnabled(True)
        self._update_status_text()

    @Slot(str)
    def _on_error(self, msg: str) -> None:
        pass

    @Slot(object)
    def _on_stats_updated(self, stats) -> None:
        self._status_packets.setText(f"Packets : {stats.packets_sent + stats.packets_received}")
        self._status_errors.setText(f"Errors : {stats.errors}")

    def _update_status_text(self) -> None:
        if self._mode_combo.currentIndex() == 0:
            port = self._rtu_port_combo.currentText().split(" - ")[0]
            baud = self._rtu_baud_combo.currentText()
            data = self._rtu_data_combo.currentText()
            stop = self._rtu_stop_combo.currentText()
            parity = self._rtu_parity_combo.currentText()
            msg = f"RTU : {port} | {baud},{data},{stop},{parity}"
        else:
            ip = self._tcp_ip_input.text().replace(" ", "")
            port = self._tcp_port_input.text()
            msg = f"TCP : {ip}:{port}"
        self._status_text.setText(msg)

    def showEvent(self, event) -> None:
        if self._first_show:
            self._first_show = False
            s = QSettings("PLCModbusTester", "MainWindow")
            geo = s.value("geometry")
            if geo:
                self.restoreGeometry(geo)
        super().showEvent(event)

    def closeEvent(self, event) -> None:
        s = QSettings("PLCModbusTester", "MainWindow")
        s.setValue("geometry", self.saveGeometry())
        self._client.cleanup()
        super().closeEvent(event)
