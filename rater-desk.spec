# PyInstaller recipe: one windowed executable with the icon and assets inside.
#   pyinstaller --noconfirm rater-desk.spec
# PyInstaller builds for the OS it runs on, so the Windows .exe comes from
# build-windows.bat (on a Windows PC) or build-windows.sh (Wine, from Linux).

a = Analysis(
    ['main.py'],
    datas=[('assets', 'assets')],
    # Exclude optional local seed data and test dependencies from the executable.
    # New installations use the default platform records in starter.py.
    excludes=['seed', 'pytest'],
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='Rater Desk',
    icon='assets/icon.ico',
    console=False,
    upx=False,
)
