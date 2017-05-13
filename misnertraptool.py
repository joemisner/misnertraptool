#!/usr/bin/env python
"""
misnertraptool.py - Misner Trap Tool
Copyright (C) 2015-2017 Joe Misner <joe@misner.net>
http://tools.misner.net/

This program is free software; you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation; either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program; if not, write to the Free Software Foundation,
Inc., 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301  USA

Dependencies:
- Python v2.7.13, https://www.python.org/
- Python module 'pywin32' build 214, https://pypi.python.org/pypi/pywin32
- Python module 'PySNMP' v4.3.1, https://pypi.python.org/pypi/pysnmp
- Python module 'PySide' v1.2.4, https://pypi.python.org/pypi/PySide
- Python module 'misnertraptoolui.py'
"""

import sys
import os
import time
import subprocess
import shelve
import socket
import win32com.client
import win32api
import win32gui
from collections import deque
from pysnmp.entity import engine
from pysnmp.entity.rfc3413 import context
from pysnmp.entity.rfc3413.oneliner import ntforg
from pysnmp.proto import rfc1902
from pysnmp.error import PySnmpError
from pyasn1.type import univ
from PySide import QtCore, QtGui
from misnertraptoolui import Ui_MainWindow

# Debug PySNMP issues
#from pysnmp import debug
#debug.setLogger(debug.Debug('mibbuild'))
#debug.setLogger(debug.Debug('all'))

__version__ = '2017.05.10'

script_path = os.path.dirname(sys.argv[0])

DEFAULT_COMMUNITY_STRING = 'public'
DEFAULT_AGENT_ADDRESS = 'localhost'
DEFAULT_DESTINATION_ADDRESS = 'localhost:162'
DEFAULT_SOURCE_OID = '1.3.6.1.4.1.3.1.1'

CREATE_NO_WINDOW = 0x8000000  # Flag which suppresses console window output
COMBO_HISTORY = 10
CONFIG_FILE = 'misnertraptool.cfg'

SPECIFIC_TRAP_TYPE = '1'
OID_TYPES = {
    0: ["Integer", 'i'],
    1: ["Unsigned", 'u'],
    2: ["Counter32", 'c'],
    3: ["String", 's'],
   #4: ["Hex String", 'x'],
   #5: ["Decimal String", 'd'],
    4: ["Null Object", 'n'],
    5: ["OID", 'o'],
    6: ["Time Ticks", 't'],
    7: ["IP Address", 'a']
  #10: ["Bits", 'b']
}

HELP_TEXT = """
Graphically build and send SNMP notifications to a remote SNMP
manager, including Traps and InformRequests. Allows saving of traps
for future use, as well as building snmptrap arguments for sending
from a remote system. Supports SNMP versions 1, 2c, and 3.

misnertraptool.exe [notification.ntf]

Features:
- Notifications include SNMPv1/2c/3 Trap and SNMPv2/3 InformRequest
- Send notification using included PySNMP engine or Net-SNMP snmptrap
- Save completed notifications to file for future use
- Forward built notification to a SecureCRT or PuTTY window to source
  the notification from a remote host using Net-SNMP snmptrap
- Track notification activities in output log
- Input fields keep history of last ten sent values in drop-down box,
  as well as persistent values from when the application was last run

To utilize Net-SNMP snmptrap for sending notifications from the local
machine, both snmptrap.exe and netsnmp.dll from the Net-SNMP
distribution must be included in this tool's directory or in the
local PATH environment variable. Otherwise, this tool's executable is
portable, and the included PySNMP engine may be used. OpenSSL
installation may be required when using SNMPv3 USM hashing and
encryption algorithms.

Send To notification destinations:
- 'Destination Address' sends the notification directly to a
  destination address using the internal PySNMP engine
- 'snmptrap: Local Executable' sends the notification using a local
  snmptrap.exe executable
- 'snmptrap: Output Only' sends the completed snmptrap command
  syntax to the Output tab only
- 'snmptrap: SecureCRT' sends the completed snmptrap command
  syntax to the SecureCRT window
- 'snmptrap: PuTTY' sends the completed snmptrap command
  syntax to the PuTTY window
"""

ABOUT_TEXT = """
<html>
<h3>Misner Trap Tool</h3>
Version %s
<p>
Copyright (C) 2015-2017 Joe Misner &lt;<a href="mailto:joe@misner.net">joe@misner.net</a>&gt;
<a href="http://tools.misner.net/">http://tools.misner.net/</a>
<p>
This program is free software; you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation; either version 3 of the License, or
(at your option) any later version.
<p>
This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.
<p>
You should have received a copy of the GNU General Public License
along with this program; if not, write to the Free Software Foundation,
Inc., 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301  USA
<p>
Click the "Show Details" button below for complete license information.
</html>
"""

class MainWindow(QtGui.QMainWindow):
    """Object class for the main window"""
    def __init__(self):
        """Executed when the MainWindow() object is created"""
        # GUI Setup
        QtGui.QMainWindow.__init__(self)
        self.ui = Ui_MainWindow()
        self.ui.setupUi(self)
        self.setFixedSize(self.size())
        self.show()
        
        # Force slot triggers to properly disable fields
        self.comboNotificationType_activated()
        self.comboAuthProtocol_activated()
        self.comboPrivProtocol_activated()
        
        # Build 'Varbinds' table
        delegate = ComboDelegate(self)
        self.ui.tableVarbinds.setItemDelegateForColumn(1, delegate)
        self.ui.tableVarbinds.itemDelegateForColumn(1)
        self.ui.tableVarbinds.setColumnWidth(0, 150)
        self.ui.tableVarbinds.setColumnWidth(1, 100)
        self.ui.tableVarbinds.setColumnWidth(2, 150)
        
        # Populate combobox history from persistent storage
        try:    self.ui.comboCommunityString.addItems(config['comboCommunityString_history'])
        except: self.ui.comboCommunityString.addItem(DEFAULT_COMMUNITY_STRING)
        try:    self.ui.comboAgentAddress.addItems(config['comboAgentAddress_history'])
        except: self.ui.comboAgentAddress.addItem(DEFAULT_AGENT_ADDRESS)
        try:    self.ui.comboDestinationAddress.addItems(config['comboDestinationAddress_history'])
        except: self.ui.comboDestinationAddress.addItem(DEFAULT_DESTINATION_ADDRESS)
        try:    self.ui.comboSourceOID.addItems(config['comboSourceOID_history'])
        except: self.ui.comboSourceOID.addItem(DEFAULT_SOURCE_OID)
        try:    self.ui.comboSecurityName.addItems(config['comboSecurityName_history'])
        except: pass
        try:    self.ui.comboContext.addItems(config['comboContext_history'])
        except: pass
        try:    self.ui.comboAuthKey.addItems(config['comboAuthKey_history'])
        except: pass
        try:    self.ui.comboPrivKey.addItems(config['comboPrivKey_history'])
        except: pass
        
        # Clear the edit section of the comboboxes, still retaining the previously loaded history
        self.ui.comboCommunityString.clearEditText()
        self.ui.comboAgentAddress.clearEditText()
        self.ui.comboDestinationAddress.clearEditText()
        self.ui.comboSourceOID.clearEditText()
        self.ui.comboSecurityName.clearEditText()
        self.ui.comboContext.clearEditText()
        self.ui.comboAuthKey.clearEditText()
        self.ui.comboPrivKey.clearEditText()
        
        # Assign default value to placeholder
        self.ui.editSpecificType.setPlaceholderText(SPECIFIC_TRAP_TYPE)
        
        # Qt Signals
        self.ui.comboNotificationType.activated.connect(self.comboNotificationType_activated)
        self.ui.comboGenericType.activated.connect(self.comboGenericType_activated)
        self.ui.comboAuthProtocol.activated.connect(self.comboAuthProtocol_activated)
        self.ui.comboPrivProtocol.activated.connect(self.comboPrivProtocol_activated)
        
        self.ui.buttonVarbindAdd.clicked.connect(self.buttonVarbindAdd_clicked)
        self.ui.buttonVarbindClearAll.clicked.connect(self.buttonVarbindClearAll_clicked)
        self.ui.buttonVarbindRemove.clicked.connect(self.buttonVarbindRemove_clicked)
        
        self.ui.buttonClearAll.clicked.connect(self.buttonClearAll_clicked)
        self.ui.buttonSend.clicked.connect(self.buttonSend_clicked)
        
        self.ui.actionOpen.triggered.connect(self.actionOpen_triggered)
        self.ui.actionSaveAs.triggered.connect(self.actionSaveAs_triggered)
        self.ui.actionExit.triggered.connect(self.close)
        self.ui.actionHelp.triggered.connect(self.actionHelp_triggered)
        self.ui.actionAbout.triggered.connect(self.actionAbout_triggered)
        
        # Validate path to snmptrap.exe first by trying script directory, then OS path
        if os.path.exists(os.path.join(script_path, 'snmptrap.exe')):
            self.snmptrap_path = os.path.join(script_path, 'snmptrap.exe')
            s = self.snmptrap_path
        else:
            try:
                subprocess.call("snmptrap.exe", creationflags=CREATE_NO_WINDOW)
                self.snmptrap_path = 'snmptrap.exe'
                s = "local PATH environment variable"
            except OSError as e:
                if e.errno == os.errno.ENOENT:
                    s = "unable to locate local Net-SNMP snmptrap executable"
                else:
                    s = "unable to call local executable"
                self.ui.comboSendTo.removeItem(1)
        self.outputtab_msg('snmptrap.exe used: %s' % (s), timestamp=False)
        
        # Validate path to MIBs directory
        if os.path.exists(os.path.join(script_path, 'mibs')):
            self.mibs_path = os.path.join(script_path, 'mibs')
            self.outputtab_msg('MIBs used: %s' % (self.mibs_path), timestamp=False)
        else:
            self.mibs_path = ''
        
        # Configure Win32 API shell
        if sys.platform == 'win32':
            self.shell = win32com.client.Dispatch("Wscript.Shell")
        
        # Load form values from previous session
        self.open_notification(from_config=True)
        
        # Check if a notification file was passed as an argument and load it
        if len(sys.argv) > 1:
            filename             = sys.argv[1]
            script_path_filename = os.path.join(script_path, filename)
            if filename[-4:] == '.ntf':
                if os.path.exists(filename):
                    msg = "Opening notification file from argument: %s" % os.path.normpath(filename)
                    self.open_notification(filename)
                elif os.path.exists(script_path_filename):
                    msg = "Opening notification file from argument: %s" % os.path.normpath(script_path_filename)
                    self.open_notification(script_path_filename)
                else:
                    msg = "Unable to locate notification file from argument: %s" % os.path.normpath(filename)
                self.outputtab_msg(msg, timestamp=False)
            else:
                msg = "Invalid argument: %s" % ' '.join(sys.argv[1:])
                self.outputtab_msg(msg, timestamp=False)
    
    def closeEvent(self, event):
        """Executed just before the main window is closed"""
        # Save form values for a future session
        self.save_notification(to_config=True)
    
    # Qt slots
    def actionOpen_triggered(self):
        """File > Open dialog box"""
        filename, _ = QtGui.QFileDialog.getOpenFileName(self, "Open", script_path,
                                                        "Notification Files (*.ntf);;All Files (*.*)")
        if not filename:
            return
        
        # Check with user before loading data and overwriting existing fields
        clicked = QtGui.QMessageBox.question(self, "Misner Trap Tool", "Are you sure you want to overwrite all fields?",
                                             QtGui.QMessageBox.Yes | QtGui.QMessageBox.No)
        if not clicked == QtGui.QMessageBox.StandardButton.Yes:
            return
        
        self.open_notification(filename)
    
    def actionSaveAs_triggered(self):
        """File > Save As... dialog box"""
        filename, _ = QtGui.QFileDialog.getSaveFileName(self, "Save", script_path,
                                                        "Notification Files (*.ntf);;All Files (*.*)")
        if not filename:
            return
        
        self.save_notification(filename)
    
    def actionHelp_triggered(self):
        """Help > Help dialog box"""
        QtGui.QMessageBox.about(self, "Help", HELP_TEXT)
    
    def actionAbout_triggered(self):
        """Help > About dialog box"""
        try:
            with open('LICENSE.txt', 'r') as f:
                license = f.read()
        except:
            license = "LICENSE.txt file missing"

        dialog = QtGui.QMessageBox(self)
        dialog.setIconPixmap(':/favorites.png')
        dialog.setWindowTitle("About")
        dialog.setText(ABOUT_TEXT % __version__)
        dialog.setDetailedText(license)
        dialog.exec_()

    def comboNotificationType_activated(self):
        """Notification Type combobox clicked"""
        generic_trap_type = self.ui.comboGenericType.currentText()
        notification_type = self.ui.comboNotificationType.currentText()
        if 'SNMPv1' in notification_type:
            self.ui.boxSNMPv3.setEnabled(False)
            self.ui.comboCommunityString.setEnabled(True)
            self.ui.comboAgentAddress.setEnabled(True)
            self.ui.comboGenericType.setEnabled(True)
            if generic_trap_type == '6 - Enterprise Specific':
                self.ui.editSpecificType.setEnabled(True)
        if 'SNMPv2c' in notification_type:
            self.ui.boxSNMPv3.setEnabled(False)
            self.ui.comboCommunityString.setEnabled(True)
            self.ui.comboAgentAddress.setEnabled(False)
            self.ui.comboGenericType.setEnabled(False)
            self.ui.editSpecificType.setEnabled(False)
        if 'SNMPv3' in notification_type:
            self.ui.boxSNMPv3.setEnabled(True)
            self.ui.comboCommunityString.setEnabled(False)
            self.ui.comboAgentAddress.setEnabled(False)
            self.ui.comboGenericType.setEnabled(False)
            self.ui.editSpecificType.setEnabled(False)
    
    def comboGenericType_activated(self):
        """Generic Type combobox clicked"""
        generic_trap_type = self.ui.comboGenericType.currentText()
        notification_type = self.ui.comboNotificationType.currentText()
        if generic_trap_type == '6 - Enterprise Specific' and notification_type == 'SNMPv1 Trap':
            self.ui.editSpecificType.setEnabled(True)
        else:
            self.ui.editSpecificType.setEnabled(False)
    
    def comboAuthProtocol_activated(self):
        """Authentication Protocol combobox clicked"""
        auth_protocol = self.ui.comboAuthProtocol.currentText()
        if auth_protocol == 'None':
            self.ui.comboPrivProtocol.setEnabled(False)
            self.ui.comboAuthKey.setEnabled(False)
            self.ui.comboPrivKey.setEnabled(False)
        else:
            self.ui.comboPrivProtocol.setEnabled(True)
            self.ui.comboAuthKey.setEnabled(True)
            self.comboPrivProtocol_activated()
    
    def comboPrivProtocol_activated(self):
        """Privacy Protocol combobox clicked"""
        priv_protocol = self.ui.comboPrivProtocol.currentText()
        if priv_protocol == 'None':
            self.ui.comboPrivKey.setEnabled(False)
        else:
            self.ui.comboPrivKey.setEnabled(True)
    
    def buttonClearAll_clicked(self):
        """Clear All button clicked"""
        dialog_answer = QtGui.QMessageBox.question(self, "Misner Trap Tool",
                                                   "Are you sure you want to clear all fields?",
                                                   QtGui.QMessageBox.Yes | QtGui.QMessageBox.No)
        if dialog_answer == QtGui.QMessageBox.StandardButton.Yes:
            self.ui.comboNotificationType.setCurrentIndex(0)
            self.ui.comboCommunityString.clearEditText()
            self.ui.comboAgentAddress.clearEditText()
            self.ui.comboDestinationAddress.clearEditText()
            self.ui.comboSourceOID.clearEditText()
            self.ui.comboGenericType.setCurrentIndex(6)
            self.ui.editSpecificType.setEnabled(True)
            self.ui.editSpecificType.setText('')
            self.ui.comboSecurityName.clearEditText()
            self.ui.comboContext.clearEditText()
            self.ui.comboAuthProtocol.setCurrentIndex(0)
            self.ui.comboPrivProtocol.setCurrentIndex(0)
            self.ui.comboAuthKey.clearEditText()
            self.ui.comboPrivKey.clearEditText()
            self.varbind_clearall(skip_dialog=True)
            self.ui.comboSendTo.setCurrentIndex(0)
        self.comboNotificationType_activated()
        self.comboGenericType_activated()
        self.comboAuthProtocol_activated()
        self.comboPrivProtocol_activated()
    
    def buttonSend_clicked(self):
        """Send button clicked"""
        self.send_notification()
    
    def buttonVarbindAdd_clicked(self):
        """Add Varbind button clicked"""
        self.varbind_add()
    
    def buttonVarbindClearAll_clicked(self):
        """Clear All Varbinds button clicked"""
        self.varbind_clearall()
    
    def buttonVarbindRemove_clicked(self):
        """Remove Varbind button clicked"""
        self.varbind_remove()
    
    # Convenience methods
    def combobox_history_add(self, combobox, config_key):
        """Add new entry into top of combobox history"""
        current_text = combobox.currentText()
        if current_text == '': return
        
        # Build a list of items in the combobox
        item_total = combobox.count()
        items = []
        for item in range(0, item_total):
            items.append(combobox.itemText(item))
        
        # Add the new address as the first entry in the combobox history, and causing the last entry to fall off
        history = deque(items, COMBO_HISTORY)
        if current_text in history: # If entry already exists, remove it first before adding as first entry
            history.remove(current_text)
        history.appendleft(current_text)
        
        # Rebuild the combobox in the new order
        combobox.clear()
        combobox.addItems(history)
        
        # Save combobox history to config file
        try:    config[config_key] = history
        except: pass
    
    def outputtab_msg(self, msg, timestamp=True):
        """Sends a message to the Output tab"""
        if timestamp:
            self.ui.editOutput.appendPlainText("%s: %s" % (time.strftime("%x %X"), msg))
        else:
            self.ui.editOutput.appendPlainText(msg)
        # Auto scroll output
        self.ui.editOutput.textCursor().movePosition(QtGui.QTextCursor.End, QtGui.QTextCursor.MoveAnchor)
    
    def statusbar_msg(self, msg):
        """Sends a message to the statusbar"""
        self.ui.statusbar.showMessage(msg)

    def window_error(self, text):
        """Error dialog box"""
        QtGui.QMessageBox.warning(self, "Error", text, QtGui.QMessageBox.Ok)
        self.statusbar_msg('Error occurred during previous operation')
    
    # Notification methods
    def open_notification(self, filename=None, from_config=False):
        """Open notification file"""
        # The from_config argument is used when loading on application startup from the config file
        try:
            if from_config:
                ntf_file = config
            else:
                ntf_file = shelve.open(filename)
            
            # Place data on current fields from loaded
            self.ui.comboNotificationType.setCurrentIndex(ntf_file['notification_type'])
            self.ui.comboCommunityString.setEditText(ntf_file['community_string'])
            self.ui.comboAgentAddress.setEditText(ntf_file['agent_address'])
            self.ui.comboDestinationAddress.setEditText(ntf_file['destination_address'])
            self.ui.comboSourceOID.setEditText(ntf_file['source_oid'])
            self.ui.comboGenericType.setCurrentIndex(ntf_file['generic_trap_type'])
            self.ui.editSpecificType.setText(ntf_file['specific_trap_type'])
            self.ui.comboSecurityName.setEditText(ntf_file['security_name'])
            self.ui.comboContext.setEditText(ntf_file['context_name'])
            self.ui.comboAuthProtocol.setCurrentIndex(ntf_file['auth_protocol'])
            self.ui.comboAuthKey.setEditText(ntf_file['auth_key'])
            self.ui.comboPrivProtocol.setCurrentIndex(ntf_file['priv_protocol'])
            self.ui.comboPrivKey.setEditText(ntf_file['priv_key'])
            
            # Build the varbinds table
            self.varbind_clearall(skip_dialog=True)
            for row in range(0, len(ntf_file['varbinds'])):
                self.varbind_add()
                self.ui.tableVarbinds.setItem(row, 0, QtGui.QTableWidgetItem())
                self.ui.tableVarbinds.setItem(row, 1, QtGui.QTableWidgetItem())
                self.ui.tableVarbinds.setItem(row, 2, QtGui.QTableWidgetItem())
                self.ui.tableVarbinds.item(row, 0).setText(ntf_file['varbinds'][row][0])
                self.ui.tableVarbinds.item(row, 1).setText(ntf_file['varbinds'][row][1])
                self.ui.tableVarbinds.item(row, 2).setText(ntf_file['varbinds'][row][2])
            
            if not from_config:
                ntf_file.close()
        except:
            if not from_config:
                self.window_error("Unable to load values from %s" % os.path.normpath(filename))
        else:
            if not from_config:
                self.statusbar_msg("Opened notification file: %s" % os.path.normpath(filename))
        finally:
            # Force slot triggers to properly disable fields
            self.comboNotificationType_activated()
            self.comboGenericType_activated()
            self.comboAuthProtocol_activated()
            self.comboPrivProtocol_activated()
    
    def save_notification(self, filename=None, to_config=False):
        """Save notification file"""
        # The to_config argument is used when automatically saving on application shutdown to the config file
        
        # Grab values from varbinds table
        row_total = self.ui.tableVarbinds.rowCount()
        varbinds = []
        for row in range(0, row_total):
            try:    oid  = self.ui.tableVarbinds.item(row, 0).text()
            except: oid  = ''
            datatype     = self.ui.tableVarbinds.item(row, 1).text()
            try:    data = self.ui.tableVarbinds.item(row, 2).text()
            except: data = ''
            varbind = [oid, datatype, data]
            varbinds.append(varbind)
        
        # Package data into file
        try:
            if to_config:
                ntf_file = config
            else:
                ntf_file = shelve.open(filename)
            ntf_file['notification_type']   = self.ui.comboNotificationType.currentIndex()
            ntf_file['community_string']    = self.ui.comboCommunityString.currentText()
            ntf_file['agent_address']       = self.ui.comboAgentAddress.currentText()
            ntf_file['destination_address'] = self.ui.comboDestinationAddress.currentText()
            ntf_file['source_oid']          = self.ui.comboSourceOID.currentText()
            ntf_file['generic_trap_type']   = self.ui.comboGenericType.currentIndex()
            ntf_file['specific_trap_type']  = self.ui.editSpecificType.displayText()
            ntf_file['security_name']       = self.ui.comboSecurityName.currentText()
            ntf_file['context_name']        = self.ui.comboContext.currentText()
            ntf_file['auth_protocol']       = self.ui.comboAuthProtocol.currentIndex()
            ntf_file['auth_key']            = self.ui.comboAuthKey.currentText()
            ntf_file['priv_protocol']       = self.ui.comboPrivProtocol.currentIndex()
            ntf_file['priv_key']            = self.ui.comboPrivKey.currentText()
            ntf_file['varbinds']            = varbinds
            
            if not to_config:
                ntf_file.close()
        except:
            if not to_config:
                self.window_error("Unable to save %s" % os.path.normpath(filename))
        else:
            if not to_config:
                self.statusbar_msg("Saved notification file: %s" % os.path.normpath(filename))
    
    def send_notification(self):
        """Send notification to specified destination"""
        self.statusbar_msg('Building notification...')
        
        # Create variables based on current form values
        notification_type   = self.ui.comboNotificationType.currentText()
        community_string    = self.ui.comboCommunityString.currentText()
        agent_address       = self.ui.comboAgentAddress.currentText()
        destination_address = self.ui.comboDestinationAddress.currentText()
        source_oid          = self.ui.comboSourceOID.currentText()
        generic_trap_type   = int(self.ui.comboGenericType.currentText()[0])
        specific_trap_type  = self.ui.editSpecificType.displayText()
        security_name       = self.ui.comboSecurityName.currentText()
        context_name        = self.ui.comboContext.currentText()
        auth_protocol       = self.ui.comboAuthProtocol.currentText()
        auth_key            = self.ui.comboAuthKey.currentText()
        priv_protocol       = self.ui.comboPrivProtocol.currentText()
        priv_key            = self.ui.comboPrivKey.currentText()
        send_to             = self.ui.comboSendTo.currentText()
        
        # If form values are missing, fill them in using defaults from script constants
        if not specific_trap_type:
            specific_trap_type = SPECIFIC_TRAP_TYPE
        
        # Check for issues with the form fields
        if not community_string and not 'SNMPv3' in notification_type:
            self.window_error('Error building notification:\n\n'
                              'Community string must be filled in.')
            return
        if not agent_address and notification_type == 'SNMPv1 Trap':
            self.window_error('Error building notification:\n\n'
                              'Agent address must be filled in.')
            return
        if not destination_address:
            self.window_error('Error building notification:\n\n'
                              'Destination address must be filled in.')
            return
        if not source_oid:
            if 'SNMPv1' in notification_type and generic_trap_type < 6:
                source_oid = '1.3.6.1.6.3.1.1.5'  # Use default enterprise OID for non-enterprise specific SNMPv1 traps
            else:
                self.window_error('Error building notification:\n\n'
                                  'Source OID must be filled in.')
                return
        if not character_test(source_oid, '0123456789.'):
            self.window_error('Error building notification:\n\n'
                              'Source Object ID must be a dotted set of numbers.')
            return
        if not specific_trap_type.isdigit() and generic_trap_type == 6 and notification_type == 'SNMPv1 Trap':
            self.window_error('Error building notification:\n\n'
                              'Specific trap type must be numeric.')
            return
        if not security_name and 'SNMPv3' in notification_type:
            self.window_error('Error building notification:\n\n'
                              'User / Security Name must be filled in.')
            return
        if len(auth_key) < 8 and auth_protocol != 'None' and 'SNMPv3' in notification_type:
            self.window_error('Error building notification:\n\n'
                              'Authentication key must be at least 8 characters.')
            return
        if len(priv_key) < 8 and auth_protocol != 'None' and priv_protocol != 'None' and 'SNMPv3' in notification_type:
            self.window_error('Error building notification:\n\n'
                              'Privacy key must be at least 8 characters.')
            return
        
        # Add form values to combobox history
        self.combobox_history_add(self.ui.comboCommunityString, 'comboCommunityString_history')
        self.combobox_history_add(self.ui.comboAgentAddress, 'comboAgentAddress_history')
        self.combobox_history_add(self.ui.comboDestinationAddress, 'comboDestinationAddress_history')
        self.combobox_history_add(self.ui.comboSourceOID, 'comboSourceOID_history')
        self.combobox_history_add(self.ui.comboSecurityName, 'comboSecurityName_history')
        self.combobox_history_add(self.ui.comboContext, 'comboContext_history')
        self.combobox_history_add(self.ui.comboAuthKey, 'comboAuthKey_history')
        self.combobox_history_add(self.ui.comboPrivKey, 'comboPrivKey_history')
        
        # Parse destination address into host and port
        if ':' in destination_address:
            host, port = destination_address.split(':')
            if not port.isdigit():
                self.window_error('Error building notification:\n\n'
                                  'Port number is not valid.')
                return
        else:
            host = destination_address
            port = '162'
        transport_target = ntforg.UdpTransportTarget((host, int(port)))
        
        # Resolve host DNS, checking address validity in the process
        try:
            host = socket.gethostbyname(host)
        except:
            self.window_error('Error building notification:\n\n'
                              'Destination address is not valid.')
            return
        try:
            agent_address = socket.gethostbyname(agent_address)
        except:
            self.window_error('Error building notification:\n\n'
                              'Agent address is not valid.')
            return
        
        # Process notification using included PySNMP module
        if send_to == 'Destination Address':
            # Trap or Inform PDU
            if 'Trap' in notification_type:
                pdu = 'trap'
            if 'Inform' in notification_type:
                pdu = 'inform'
            
            # If using SNMPv1, integrate the generic and specific trap types into the source OID,
            # and separate the enterprise_oid
            if notification_type == 'SNMPv1 Trap':
                snmp_model = 0  # SNMPv1
                enterprise_oid = source_oid
                if generic_trap_type < 6:
                    source_oid = '1.3.6.1.6.3.1.1.5.%s' % (generic_trap_type + 1)
                if generic_trap_type == 6:
                    source_oid = '%s.0.%s' % (enterprise_oid, specific_trap_type)
            else:
                snmp_model = 1  # SNMPv2c
                enterprise_oid = ''
            
            # Avoid "pyasn1.error.PyAsn1Error: Invalid sub-ID" exception
            # by converting source and enterprise OIDs to string
            source_oid = str(source_oid)
            enterprise_oid = str(enterprise_oid)
            
            # Determine authentication information based on community string (SNMPv1/2c)
            # or user-based security model (SNMPv3)
            if ('SNMPv1' or 'SNMPv2c') in notification_type:
                authentication = ntforg.CommunityData(community_string, mpModel=snmp_model)
            if 'SNMPv3' in notification_type:
                # Map selected protocols to ntforg objects
                if auth_protocol == 'MD5':     auth_protocol = ntforg.usmHMACMD5AuthProtocol
                if auth_protocol == 'SHA-1':   auth_protocol = ntforg.usmHMACSHAAuthProtocol
                if priv_protocol == 'DES':     priv_protocol = ntforg.usmDESPrivProtocol
                if priv_protocol == '3DES':    priv_protocol = ntforg.usm3DESEDEPrivProtocol
                if priv_protocol == 'AES-128': priv_protocol = ntforg.usmAesCfb128Protocol
                if priv_protocol == 'AES-192': priv_protocol = ntforg.usmAesCfb192Protocol
                if priv_protocol == 'AES-256': priv_protocol = ntforg.usmAesCfb256Protocol
                # Built USM authentication object
                if auth_protocol == 'None':    # No authentication, no privacy
                    authentication = ntforg.UsmUserData(security_name)
                elif priv_protocol == 'None':  # Authentication, no privacy
                    authentication = ntforg.UsmUserData(security_name, auth_key, authProtocol=auth_protocol)
                else:                          # Authentication and privacy
                    authentication = ntforg.UsmUserData(security_name, auth_key, priv_key,
                                                        authProtocol=auth_protocol, privProtocol=priv_protocol)
            
            # Compile a list of all the varbinds in the table
            row_total = self.ui.tableVarbinds.rowCount()
            varbinds = []
            for row in range(0, row_total):
                try:
                    oid      = str(self.ui.tableVarbinds.item(row, 0).text().strip())
                    datatype = str(self.ui.tableVarbinds.item(row, 1).text().strip())
                    data     = str(self.ui.tableVarbinds.item(row, 2).text().strip())
                except AttributeError:
                    self.window_error('Error building notification:\n\n'
                                      'Varbind row %s is missing a value.' % str(row + 1))
                    return
                if not character_test(oid, '0123456789.'):
                    self.window_error('Error building notification:\n\n'
                                      'OID in varbind row %s must be a single dotted set of numbers.' % str(row + 1))
                    return
                datatype = OID_TYPES[int(datatype)][0]
                try:
                    if datatype == 'Integer':           varbind = (oid, rfc1902.Integer(data))
                    elif datatype == 'Unsigned':        varbind = (oid, rfc1902.Unsigned32(data))
                    elif datatype == 'Counter32':       varbind = (oid, rfc1902.Counter32(data))
                    elif datatype == 'String':          varbind = (oid, rfc1902.OctetString(data))
                    #elif datatype == 'Hex String':     varbind = (oid, rfc1902.OctetString(data))
                    #elif datatype == 'Decimal String': varbind = (oid, rfc1902.OctetString(data))
                    elif datatype == 'Null Object':     varbind = (oid, univ.Null())
                    elif datatype == 'OID':             varbind = (oid, univ.ObjectIdentifier(data))
                    elif datatype == 'Time Ticks':      varbind = (oid, rfc1902.TimeTicks(data))
                    elif datatype == 'IP Address':      varbind = (oid, rfc1902.IpAddress(data))
                    #elif datatype == 'Bits':           varbind = (oid, rfc1902.Bits(data))
                    else:                               raise
                except:
                    self.window_error('Error building notification:\n\n'
                                      'Varbind row %s contains an invalid data value.' % str(row + 1))
                    return
                varbinds.append(varbind)
            
            # Append the standard varbinds (SNMPv1 only)
            if 'SNMPv1' in notification_type:
                varbinds.append(('1.3.6.1.2.1.1.3.0', 0))                   # SNMPv1 Time Stamp / Uptime (always zero)
                varbinds.append(('1.3.6.1.6.3.18.1.3.0', agent_address))    # SNMPv1 Agent Address
                varbinds.append(('1.3.6.1.6.3.1.1.4.3.0', enterprise_oid))  # SNMPv1 Enterprise OID
            
            # Send the notification using the PySNMP engine
            self.statusbar_msg('Sending notification...')
            if ('SNMPv1' or 'SNMPv2c') in notification_type:
                self.outputtab_msg('Sending notification to %s: '
                                   'notification_type="%s" community_string="%s" source_oid="%s"'
                                   % (destination_address, notification_type, community_string, source_oid))
            else:
                self.outputtab_msg('Sending notification to %s: '
                                   'notification_type="%s" security_name="%s" source_oid="%s"'
                                   % (destination_address, notification_type, security_name, source_oid))
            try:
                if context_name != '' and 'SNMPv3' in notification_type: # Custom context name when using SNMPv3
                    snmpEngine = engine.SnmpEngine()
                    snmpContext = context.SnmpContext(snmpEngine)
                    snmpContext.registerContextName(context_name, snmpContext.getMibInstrum())
                    ntfOrg = ntforg.NotificationOriginator(snmpEngine, snmpContext)
                    errorIndication = ntfOrg.sendNotification(authentication, transport_target,
                                                              pdu, source_oid, *varbinds, contextName=context_name)
                else:
                    ntfOrg = ntforg.NotificationOriginator()
                    errorIndication = ntfOrg.sendNotification(authentication, transport_target,
                                                              pdu, source_oid, *varbinds)
                if errorIndication:
                    if pdu == 'inform' and str(errorIndication) == 'No SNMP response received before timeout':
                        error_msg = 'InformRequest packet received no acknowledgment from %s.' % destination_address
                    else:
                        error_msg = 'Error building notification: %s' % errorIndication
                    self.window_error(error_msg)
                    self.outputtab_msg(error_msg)
                    return
            except PySnmpError as e:
                self.window_error('Exception while sending notification.\n\n%s' % e)
                self.outputtab_msg('Exception while sending notification.')
            except:
                self.window_error('Exception while sending notification.\n\n'
                                  'See log file in current working directory for details.')
                self.outputtab_msg('Exception while sending notification.')
                raise
            else:
                self.outputtab_msg("Notification sent successfully")
                self.statusbar_msg('Notification sent')
        
        # Process notification using external snmptrap program
        if 'snmptrap' in send_to:
            # Trap or Inform PDU; needed to build the options string
            if 'Trap' in notification_type:
                pdu = ''
            if 'Inform' in notification_type:
                pdu = '-Ci '
            
            # Build a string made up of the form values, making up the trap options
            if 'SNMPv1' in notification_type:
                options = "-v 1 -c %s %s %s %s %s %s 0" % (community_string, destination_address, source_oid,
                                                           agent_address, generic_trap_type, specific_trap_type)
            if 'SNMPv2c' in notification_type:
                options = "%s-v 2c -c %s %s 0 %s" % (pdu, community_string, destination_address, source_oid)
            if 'SNMPv3' in notification_type:
                # Translate protocols to terms snmptrap understands
                if auth_protocol == 'SHA-1':   auth_protocol = 'SHA'
                if priv_protocol == 'AES-128': priv_protocol = 'AES'
                # Make security level as required by snmptrap '-l' argument
                if auth_protocol == 'None' and priv_protocol == 'None':
                    security_level = 'noAuthNoPriv'
                    options = "%s-v 3 -n \"%s\" -u %s -l %s %s 0 %s"\
                              % (pdu, context_name, security_name, security_level, destination_address, source_oid)
                if auth_protocol != 'None' and priv_protocol == 'None':
                    security_level = 'authNoPriv'
                    options = "%s-v 3 -n \"%s\" -u %s -l %s -a %s -A %s %s 0 %s"\
                              % (pdu, context_name, security_name, security_level,
                                 auth_protocol, auth_key, destination_address, source_oid)
                if auth_protocol != 'None' and priv_protocol != 'None':
                    unsupported_protocols = ['3DES', 'AES-192', 'AES-256']
                    if priv_protocol in unsupported_protocols:
                        self.window_error('Error building notification:\n\n'
                                          '%s protocol is not supported by snmptrap.' % priv_protocol)
                        return
                    security_level = 'authPriv'
                    options = "%s-v 3 -n \"%s\" -u %s -l %s -a %s -A %s -x %s -X %s %s 0 %s"\
                              % (pdu, context_name, security_name, security_level, auth_protocol,
                                 auth_key, priv_protocol, priv_key, destination_address, source_oid)
        
            # Build a dictionary made up of all the varbinds in the table, then convert to string
            row_total = self.ui.tableVarbinds.rowCount()
            varbinds = []
            for row in range(0, row_total):
                try:
                    oid      =          self.ui.tableVarbinds.item(row, 0).text().strip()
                    datatype =          self.ui.tableVarbinds.item(row, 1).text().strip()
                    data     = '"%s"' % self.ui.tableVarbinds.item(row, 2).text().strip()
                except AttributeError:
                    self.window_error('Error building notification:\n\n'
                                      'Varbind row %s is missing a value.' % str(row + 1))
                    return
                if ' ' in oid:
                    self.window_error('Error building notification:\n\n'
                                      'OID in varbind row %s contains multiple values.' % str(row + 1))
                    return
                datatype = OID_TYPES[int(datatype)][1]
                varbind = '%s %s %s' % (oid, datatype, data)
                varbinds.append(varbind)
            varbinds = ' '.join(varbinds)

            if sys.platform == 'win32':
                # Copy snmptrap command to local SecureCRT window
                if send_to == 'snmptrap: SecureCRT':
                    if not window_available('SecureCRT'):
                        self.window_error('Error building notification:\n\n'
                                          'Unable to locate an available SecureCRT window.')
                        return

                    command = "snmptrap %s %s" % (options, varbinds)
                    self.outputtab_msg('SecureCRT> ' + command)
                    self.statusbar_msg('Sending notification to SecureCRT window...')
                    self.shell.AppActivate("SecureCRT")
                    win32api.Sleep(100)
                    self.shell.SendKeys(command)
                    self.statusbar_msg('Notification sent to SecureCRT window')

                # Copy snmptrap command to local PuTTY window
                if send_to == 'snmptrap: PuTTY':
                    if not window_available('PuTTY'):
                        self.window_error('Error building notification:\n\n'
                                          'Unable to locate an available PuTTY window.')
                        return

                    command = "snmptrap %s %s" % (options, varbinds)
                    self.outputtab_msg('PuTTY> ' + command)
                    self.statusbar_msg('Sending notification to PuTTY window...')
                    self.shell.AppActivate("PuTTY")
                    win32api.Sleep(100)
                    self.shell.SendKeys(command)
                    self.statusbar_msg('Notification sent to PuTTY window')
            
            # Copy snmptrap command to local snmptrap.exe executable
            if send_to == 'snmptrap: Local Executable':
                command = '"%s" -Lo -m ALL -M "%s" %s %s' % (self.snmptrap_path, self.mibs_path, options, varbinds)
                self.outputtab_msg('Local> ' + command)
                self.statusbar_msg('Sending notification to local snmptrap.exe...')
                try:
                    output = subprocess.check_output(command, stderr=subprocess.STDOUT, creationflags=CREATE_NO_WINDOW)
                except subprocess.CalledProcessError as e:
                    if 'Inform' in notification_type and 'snmpinform: Timeout' in e.output:
                        error_msg = 'snmptrap error:\n' \
                                    'InformRequest packet received no acknowledgment from %s.' % destination_address
                    else:
                        error_msg = "snmptrap error %s:\n%s" % (str(e.returncode), e.output)
                    self.window_error(error_msg)
                    self.outputtab_msg(error_msg)
                else:
                    self.outputtab_msg("snmptrap executed successfully%s" % (output))
                    self.statusbar_msg('Notification sent')
            
            # Copy snmptrap command to output only
            if send_to == 'snmptrap: Output Only':
                command = "snmptrap %s %s" % (options, varbinds)
                self.outputtab_msg('OutputOnly> ' + command)
                self.statusbar_msg('snmptrap command sent to output tab')
    
    # Varbinds table row adjustment methods
    def varbind_add(self):
        """Varbind Add button clicked"""
        row_count = self.ui.tableVarbinds.rowCount()
        self.ui.tableVarbinds.setRowCount(row_count + 1)
        self.ui.tableVarbinds.setItem(row_count, 1, QtGui.QTableWidgetItem())
        self.ui.tableVarbinds.item(row_count, 1).setText('0')
        self.ui.tableVarbinds.openPersistentEditor(self.ui.tableVarbinds.item(row_count, 1))
    
    def varbind_clearall(self, skip_dialog=False):
        """Varbind Clear All button clicked"""
        row_total = self.ui.tableVarbinds.rowCount()
        if not skip_dialog:
            dialog_answer = QtGui.QMessageBox.question(
                self, "Misner Trap Tool", "Are you sure you want to remove all varbinds?",
                QtGui.QMessageBox.Yes | QtGui.QMessageBox.No
            )
        if skip_dialog or dialog_answer == QtGui.QMessageBox.StandardButton.Yes:
            for row in range(row_total - 1, -1, -1):
                self.ui.tableVarbinds.removeRow(row)
    
    def varbind_remove(self):
        """Varbind Remove button clicked"""
        current_row = self.ui.tableVarbinds.currentRow()
        varbind = self.ui.tableVarbinds.item(current_row, 0)
        if varbind: # If there is a varbind assigned, ask before removing the row
            dialog_answer = QtGui.QMessageBox.question(
                self, "Misner Trap Tool", "Are you sure you want to remove " + varbind.text() + "?",
                QtGui.QMessageBox.Yes | QtGui.QMessageBox.No
            )
            if dialog_answer == QtGui.QMessageBox.StandardButton.Yes:
                self.ui.tableVarbinds.removeRow(current_row)
        else: # If varbind is blank, remove the row
            self.ui.tableVarbinds.removeRow(current_row)


class ComboDelegate(QtGui.QItemDelegate):
    """Delegate used to create comboboxes in the Varbind Type column"""
    def __init__(self, parent):
        QtGui.QItemDelegate.__init__(self, parent)

    def createEditor(self, parent, option, index):
        combo = QtGui.QComboBox(parent)
        combo_list = []
        for key in OID_TYPES:
            combo_list.append(OID_TYPES[key][0])
        combo.addItems(combo_list)
        combo.setMaxVisibleItems(12)
        return combo

    def setEditorData(self, editor, index):
        value = index.data(QtCore.Qt.DisplayRole)
        try: # Prevents unknown bug causing tracebacks
            editor.setCurrentIndex(int(value))
        except TypeError:
            pass

    def setModelData(self, editor, model, index):
        model.setData(index, editor.currentIndex())

    @QtCore.Slot()
    def currentIndexChanged(self):
        self.commitData.emit(self.sender())


def character_test(text, allowed):
    """Test if the characters in 'text' are all made up of characters in 'allowed'"""
    if text.strip(allowed):
        return False
    else:
        return True


def visible_windows():
    """Returns dictionary of handle:windowname pairs for all visible windows"""
    handles = {}

    def win_enum_handler(hwnd, ctx):
        if win32gui.IsWindowVisible(hwnd):
            handles[hex(hwnd)] = win32gui.GetWindowText(hwnd)
    win32gui.EnumWindows(win_enum_handler, None)

    return handles


def window_available(window_name):
    """"Using previous visible_windows() function, check if window_name is a visible window"""
    windows = visible_windows()
    for handle in windows:
        if window_name in windows[handle]:
            return handle, windows[handle]
    else:
        return False


if __name__ == '__main__':
    config_filename = os.path.join(script_path, CONFIG_FILE)
    try:
        config = shelve.open(config_filename)
    except:
        pass
    
    app = QtGui.QApplication(sys.argv)
    window = MainWindow()
    exitcode = app.exec_()
    
    try:
        config.close()
    except:
        pass

    sys.exit(exitcode)
