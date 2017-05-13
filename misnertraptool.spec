# -*- mode: python -*-

import os
import sys

python_dir = os.path.dirname(sys.executable)

# Files to include in collection
added_files1 = [
  ('README.md', '.' ),
  ('LICENSE.txt', '.' )
]
added_files2 = Tree(python_dir + '/Lib/site-packages/pysnmp/smi/mibs',
                    prefix='pysnmp/smi/mibs', excludes='.py')
added_files3 = Tree(python_dir + '/Lib/site-packages/pysnmp/smi/mibs/instances',
                    prefix='pysnmp/smi/mibs/instances', excludes='.py')
added_files4 = Tree(python_dir + '/Lib/site-packages/pysmi',
                    prefix='pysmi', excludes='.py')
added_files5 = Tree('mibs', prefix='mibs')

a = Analysis(
  ['misnertraptool.py'],
  hiddenimports=[
    'pysnmp.smi.exval',
	'pysnmp.cache',
	'pysnmp.smi.mibs',
	'pysnmp.smi.mibs.instances',
	'pysmi'
  ],
  hookspath=None,
  datas=added_files1,
  excludes=[
    'FixTk',
	'tcl',
	'tk',
	'_tkinter',
	'tkinter',
	'Tkinter',
	'certifi'
  ]
)

# Files to exclude from collection
a.binaries = a.binaries - TOC([
  ('sqlite3.dll', None, None),
  ('_sqlite3', None, None),
  ('mfc90.dll', None, None),
  ('mfc90u.dll', None, None),
  ('mfcm90.dll', None, None),
  ('mfcm90u.dll', None, None),
  ('msvcr90.dll', None, None),
  ('msvcm90.dll', None, None),
  ('tcl85.dll', None, None),
  ('tk85.dll', None, None),
  ('Tkinter', None, None),
  ('tk', None, None),
  ('_tkinter', None, None)
])

pyz = PYZ(
  a.pure
)

exe = EXE(
  pyz,
  a.scripts,
  exclude_binaries=True,
  name='misnertraptool',
  debug=False,
  strip=False,
  upx=True,
  console=False,
  icon='favorites.ico'
)

coll = COLLECT(
  exe,
  a.binaries,
  a.zipfiles,
  a.datas,
  added_files2,
  added_files3,
  added_files4,
  added_files5,
  strip=False,
  upx=True,
  name='Misner Trap Tool'
)
