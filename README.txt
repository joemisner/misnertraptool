# misnertraptool

Misner Trap Tool
================

Misner Trap Tool v2017.05.10 by Joe Misner
http://tools.misner.net/

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



Building
--------

The following dependencies are required to build the application:
- Misner Trap Tool source
- Python v2.7.13, https://www.python.org/
- Inno Setup v5.5.9, http://www.jrsoftware.org/
- Python module 'PyInstaller' v3.2.1, https://pypi.python.org/pypi/PyInstaller
- Python module 'PySide' v1.2.4, https://pypi.python.org/pypi/PySide
- Python module 'pywin32' build 214, https://pypi.python.org/pypi/pywin32
- Python module 'PySNMP' v4.3.1, https://pypi.python.org/pypi/pysnmp

1. In a Command Prompt window, change to the directory containing this git project, for example:
```
cd c:\misnertraptool\
```

2. Convert the PySide graphical user interface file `misnertraptool.ui` into Python:
```
c:\Python27\Scripts\pyside-uic.exe -x misnertraptool.ui -o misnertraptoolui.py
```
  * Assumption is that Python 2.7 is installed in `c:\Python27\`

3. Package the project with all dependencies using PyInstaller:
```
C:\Python27\python.exe -O c:\Python27\Scripts\pyinstaller.exe misnertraptool.spec -y
```
  * Assumption is that Python 2.7 is installed in `c:\Python27\`
  * Resulting package will be stored in the subdirectory `dist\Misner Trap Tool\`

4. Compile the PyInstaller package into an installer executable using Inno Setup:
```
"C:\Program Files (x86)\Inno Setup 5\iscc.exe" innosetup.iss
```
  * Assumption is that Inno Setup 5 is installed in `C:\Program Files (x86)\Inno Setup 5\`

5. Resulting installer executable in the format `Setup_MisnerTrapTool_xxxxxxxx.exe` is created.



Changelog
---------

2017.05.10 - initial public version



License
-------

Copyright (C) 2015-2017 Joe Misner <joe@misner.net>

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
