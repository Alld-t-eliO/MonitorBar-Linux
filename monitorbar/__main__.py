import sys
if sys.platform != 'linux':
    sys.exit('Cette version de MonitorBar nécessite Ubuntu/Linux.')
try:
    from .app import main
except ModuleNotFoundError as exc:
    if exc.name and exc.name.startswith('PyQt5'):
        sys.exit('Dépendance manquante : sudo apt install python3-pyqt5')
    raise
raise SystemExit(main())
