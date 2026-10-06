"""Qt overlay matching the original Cocoa MonitorBar controls and geometry."""
from collections import deque
import os
from pathlib import Path
import sys

from PyQt5.QtCore import Qt, QRectF, QSize, QThread, QTimer, pyqtSignal, QLockFile, QStandardPaths
from PyQt5.QtGui import QColor, QFont, QPainter, QPainterPath, QPen, QIcon, QPixmap
from PyQt5.QtWidgets import (QApplication, QWidget, QMenu, QColorDialog,
                             QSlider, QWidgetAction, QSystemTrayIcon)
from . import __version__
from .metrics import SystemMetrics, discover_gpus, gpu_sample
from .settings import KEYS, load, save


class Sampler(QThread):
    sampled = pyqtSignal(dict, list, str)

    def __init__(self, gpu):
        super().__init__()
        self.gpu = gpu

    def run(self):
        metrics = SystemMetrics()
        devices = discover_gpus()
        tick = 0
        while not self.isInterruptionRequested():
            values = metrics.sample()
            device = next((d for d in devices if d['id'] == self.gpu), None)
            # An explicitly selected disconnected GPU remains unavailable.
            if self.gpu is None:
                device = devices[0] if devices else None
            values['GPU'], message = gpu_sample(device)
            self.sampled.emit(values, devices, message)
            for _ in range(10):
                if self.isInterruptionRequested():
                    return
                self.msleep(100)
            tick += 1
            if tick % 30 == 0:
                devices = discover_gpus()


class Overlay(QWidget):
    def __init__(self, start_worker=True):
        super().__init__(None, Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setWindowTitle('MonitorBar')
        self.setMouseTracking(True)
        self.cfg = load()
        self.values = {key: None for key in KEYS}
        self.history = {key: deque(maxlen=60) for key in KEYS}
        self.devices = []
        self.gpu_message = 'Détection GPU…'
        self.drag = None
        self.hover = False
        self.worker = None
        self.tray = None
        self.save_timer = QTimer(self)
        self.save_timer.setSingleShot(True)
        self.save_timer.timeout.connect(self.persist)
        self.resize_bar()
        if self.cfg['position']:
            self.move(*self.cfg['position'])
            self.clamp_position()
        else:
            self.center()
        self.show()
        self.create_tray()
        if start_worker:
            self.worker = Sampler(self.cfg['gpu'])
            self.worker.sampled.connect(self.receive)
            self.worker.start()

    def preferred_size(self):
        c = self.cfg
        n, s = len(c['indicators']), c['scale']
        if c['layout'] == 1:
            return QSize(round(132*s+24), round(34*n*s))
        gap = 8 if c['layout'] == 2 else 0
        return QSize(round(((116+c['spacing'])*n+gap*(n-1))*s+24), round(34*s))

    def resize_bar(self):
        self.setFixedSize(self.preferred_size())
        self.clamp_position()
        self.update()

    def screen_area(self):
        screen = QApplication.screenAt(self.frameGeometry().center()) or QApplication.primaryScreen()
        return screen.availableGeometry()

    def clamp_position(self):
        area = self.screen_area()
        self.move(max(area.left(), min(self.x(), area.right()+1-self.width())),
                  max(area.top(), min(self.y(), area.bottom()+1-self.height())))

    def center(self):
        area = QApplication.primaryScreen().availableGeometry()
        self.move(area.center().x()-self.width()//2, area.center().y()-self.height()//2)

    def show_bar(self):
        self.cfg['background'] = True
        self.cfg['opacity'] = max(.65, self.cfg['opacity'])
        self.center()
        self.show()
        self.raise_()
        self.changed()

    def persist(self):
        self.cfg['position'] = [self.x(), self.y()]
        try:
            save(self.cfg)
        except OSError as exc:
            print(f'MonitorBar : sauvegarde impossible : {exc}', file=sys.stderr)

    def changed(self):
        self.resize_bar()
        self.save_timer.start(250)

    def receive(self, values, devices, message):
        self.values, self.devices, self.gpu_message = values, devices, message
        for key in KEYS:
            self.history[key].append(values.get(key))
        self.setToolTip('CPU : activité globale • RAM : mémoire utilisée\nGPU : ' + message + '\nClic droit : réglages')
        self.update()

    def create_tray(self):
        if not QSystemTrayIcon.isSystemTrayAvailable():
            return
        pix = QPixmap(32, 32)
        pix.fill(Qt.transparent)
        painter = QPainter(pix)
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor('#34c759'))
        for i, height in enumerate((12, 24, 18)):
            painter.drawRoundedRect(3+i*10, 28-height, 6, height, 2, 2)
        painter.end()
        self.tray = QSystemTrayIcon(QIcon(pix), self)
        self.tray.setToolTip('MonitorBar — CPU / RAM / GPU')
        self.tray_menu = QMenu()
        self.tray_menu.aboutToShow.connect(lambda: self.populate(self.tray_menu))
        self.tray.setContextMenu(self.tray_menu)
        self.tray.activated.connect(lambda reason: self.show_bar() if reason == QSystemTrayIcon.Trigger else None)
        self.tray.show()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        c, s = self.cfg, self.cfg['scale']
        background = QColor(0, 0, 0, round(c['opacity']*255))
        p.setPen(Qt.NoPen)
        if c['background'] and c['layout'] != 2:
            p.setBrush(background)
            p.drawRoundedRect(QRectF(self.rect()), 17*s, 17*s)
        font = QFont('DejaVu Sans Mono')
        font.setPixelSize(round(13*s))
        font.setWeight(QFont.DemiBold)
        p.setFont(font)
        for i, key in enumerate(c['indicators']):
            width = 116+c['spacing']
            cell = (QRectF(0, i*34*s, 132*s, 34*s) if c['layout'] == 1 else
                    QRectF(i*(width+(8 if c['layout'] == 2 else 0))*s, 0, width*s, 34*s))
            if c['background'] and c['layout'] == 2:
                p.setPen(Qt.NoPen)
                p.setBrush(background)
                p.drawRoundedRect(cell, 17*s, 17*s)
            value = self.values[key]
            color = QColor(c['colors'][key])
            if c['load_colors'] and value is not None:
                color = QColor('#ff453a' if value >= 85 else '#ff9f0a' if value >= 60 else '#34c759')
            label = {'CPU': '⚙', 'RAM': '▤', 'GPU': '◇'}[key] if c['icons'] else key
            text = f'{label}: {value:.0f}%' if value is not None else f'{label}: —'
            graph = key in c['graphs']
            text_rect = QRectF(cell.x(), cell.y()+(1*s if graph else 0), cell.width(), 22*s if graph else cell.height())
            # Multiple translucent passes provide a small glow without a whole-window effect.
            glow = QColor(color if c['neon'] else Qt.black)
            glow.setAlpha(65 if c['neon'] else 160)
            p.setPen(glow)
            for dx, dy in ((-s, 0), (s, 0), (0, -s), (0, s)):
                p.drawText(text_rect.translated(dx, dy), Qt.AlignCenter, text)
            p.setPen(color)
            p.drawText(text_rect, Qt.AlignCenter, text)
            if graph:
                path, started = QPainterPath(), False
                for j, v in enumerate(self.history[key]):
                    if v is None:
                        started = False
                        continue
                    x = cell.x()+14*s+(j/59)*(cell.width()-28*s)
                    y = cell.y()+30*s-v*.09*s
                    if started:
                        path.lineTo(x, y)
                    else:
                        path.moveTo(x, y)
                    started = True
                p.setPen(QPen(color, s))
                p.drawPath(path)
        if self.hover and not c['locked']:
            p.setBrush(Qt.NoBrush)
            p.setPen(QColor(255, 255, 255, 115))
            p.drawRoundedRect(QRectF(self.rect()).adjusted(1, 1, -1, -1), 12*s, 12*s)
        p.end()

    def enterEvent(self, event):
        self.hover = True
        self.update()

    def leaveEvent(self, event):
        self.hover = False
        self.update()

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton and not self.cfg['locked']:
            self.drag = (event.globalPos(), self.pos(), self.cfg['scale'], self.width(), event.x() >= self.width()-24)

    def mouseMoveEvent(self, event):
        resizing = event.x() >= self.width()-24
        self.setCursor(Qt.ArrowCursor if self.cfg['locked'] else Qt.SizeHorCursor if resizing else Qt.OpenHandCursor)
        if self.drag and not self.cfg['locked']:
            start, position, scale, width, resizing = self.drag
            delta = event.globalPos()-start
            if resizing:
                self.cfg['scale'] = min(2.5, max(.6, scale*(1+delta.x()/width)))
                self.resize_bar()
            else:
                self.move(position+delta)

    def mouseReleaseEvent(self, event):
        if not self.drag:
            return
        self.drag = None
        if self.cfg['snap']:
            area = self.screen_area().adjusted(10, 10, -10, -10)
            x, y = self.x(), self.y()
            for candidate in (area.left(), area.right()+1-self.width()):
                if abs(x-candidate) < 20:
                    x = candidate
            for candidate in (area.top(), area.bottom()+1-self.height()):
                if abs(y-candidate) < 20:
                    y = candidate
            self.move(x, y)
        self.clamp_position()
        self.persist()

    def contextMenuEvent(self, event):
        menu = QMenu(self)
        self.populate(menu)
        menu.exec_(event.globalPos())
        menu.deleteLater()

    def action(self, menu, title, callback, checked=None, enabled=True):
        action = menu.addAction(title)
        action.setEnabled(enabled)
        if checked is not None:
            action.setCheckable(True)
            action.setChecked(checked)
        action.triggered.connect(lambda _checked=False: callback())
        return action

    def set_value(self, key, value):
        self.cfg[key] = value
        self.changed()

    def toggle(self, key):
        self.set_value(key, not self.cfg[key])

    def scale(self, delta):
        if not self.cfg['locked']:
            self.set_value('scale', max(.6, min(2.5, self.cfg['scale']+delta)) if delta else 1)

    def slider(self, menu, key, maximum, multiplier=1):
        slider = QSlider(Qt.Horizontal)
        slider.setRange(0, maximum)
        slider.setValue(round(self.cfg[key]*multiplier))
        slider.setMinimumWidth(220)
        slider.setAccessibleName(menu.title())
        action = QWidgetAction(menu)
        action.setDefaultWidget(slider)
        menu.addAction(action)
        def change(value):
            if key == 'opacity':
                self.cfg['background'] = True
            self.set_value(key, value/multiplier)
        slider.valueChanged.connect(change)
        return slider

    def color(self, target):
        value = QColorDialog.getColor(QColor(self.cfg['colors'][target or 'CPU']), self, 'Couleur des indicateurs')
        if value.isValid():
            for key in ([target] if target else KEYS):
                self.cfg['colors'][key] = value.name()
            self.cfg['load_colors'] = False
            self.changed()

    def theme(self, name):
        neon, terminal = name == 'Néon', name == 'Terminal'
        self.cfg.update(neon=neon, load_colors=False, background=True,
                        opacity=.75 if terminal else .55 if neon else .25)
        colors = ['#32d7ff', '#bf5af2', '#ff9f0a'] if neon else ['#34c759' if terminal else '#ffffff']*3
        self.cfg['colors'] = dict(zip(KEYS, colors))
        self.changed()

    def visibility(self, key):
        indicators = self.cfg['indicators']
        if key in indicators:
            if len(indicators) > 1:
                indicators.remove(key)
        else:
            indicators.append(key)
        self.changed()

    def graph(self, key):
        graphs = self.cfg['graphs']
        graphs.remove(key) if key in graphs else graphs.append(key)
        self.changed()

    def reorder(self, key, first):
        items = self.cfg['indicators']
        if key in items:
            items.remove(key)
            items.insert(0 if first else len(items), key)
            self.changed()

    def select_gpu(self, identifier):
        self.cfg['gpu'] = identifier
        self.history['GPU'].clear()
        self.values['GPU'] = None
        if self.worker:
            self.worker.gpu = identifier
        self.changed()

    def populate(self, menu):
        menu.clear()
        c = self.cfg
        self.action(menu, 'Afficher la barre au centre', self.show_bar)
        menu.addSeparator()
        for title, delta in [('Agrandir la barre', .15), ('Réduire la barre', -.15), ('Taille normale', 0)]:
            self.action(menu, title, lambda d=delta: self.scale(d), enabled=not c['locked'])
        self.action(menu, 'Lueur néon', lambda: self.toggle('neon'), c['neon'])
        self.action(menu, 'Couleur de tous les indicateurs…', lambda: self.color(None))
        themes = menu.addMenu('Thèmes')
        for name in ['Terminal', 'Discret', 'Néon']:
            self.action(themes, name, lambda n=name: self.theme(n))
        self.action(menu, 'Fond semi-transparent', lambda: self.toggle('background'), c['background'])
        self.slider(menu.addMenu('Opacité du fond'), 'opacity', 100, 100)
        self.action(menu, 'Couleurs selon la charge', lambda: self.toggle('load_colors'), c['load_colors'])
        self.action(menu, 'Icônes à la place des libellés', lambda: self.toggle('icons'), c['icons'])
        layout = menu.addMenu('Disposition')
        for i, title in enumerate(['Barre horizontale', 'Colonne verticale', 'Capsules séparées']):
            self.action(layout, title, lambda i=i: self.set_value('layout', i), c['layout'] == i)
        spacing = menu.addMenu('Espacement des indicateurs')
        self.slider(spacing, 'spacing', 80).setEnabled(c['layout'] != 1)
        self.action(spacing, 'Espacement normal', lambda: self.set_value('spacing', 16))
        indicators = menu.addMenu('Indicateurs')
        for key in KEYS:
            sub = indicators.addMenu(key)
            shown = key in c['indicators']
            self.action(sub, 'Afficher', lambda k=key: self.visibility(k), shown, not shown or len(c['indicators']) > 1)
            self.action(sub, 'Couleur…', lambda k=key: self.color(k))
            self.action(sub, 'Courbe des 60 derniers relevés', lambda k=key: self.graph(k), key in c['graphs'])
            self.action(sub, 'Placer en premier', lambda k=key: self.reorder(k, True), enabled=shown)
            self.action(sub, 'Placer en dernier', lambda k=key: self.reorder(k, False), enabled=shown)
        gpu_menu = menu.addMenu('Carte GPU')
        self.action(gpu_menu, 'Automatique (première carte détectée)', lambda: self.select_gpu(None), c['gpu'] is None)
        for device in self.devices:
            self.action(gpu_menu, device['name'], lambda d=device: self.select_gpu(d['id']), c['gpu'] == device['id'])
        menu.addSeparator()
        for key, title in [('snap', 'Aligner aux bords de l’écran'), ('locked', 'Verrouiller position et taille')]:
            self.action(menu, title, lambda k=key: self.toggle(k), c[key])
        self.action(menu, self.gpu_message, lambda: None, enabled=False)
        self.action(menu, f'MonitorBar Ubuntu {__version__}', lambda: None, enabled=False)
        self.action(menu, 'Quitter', self.close)

    def closeEvent(self, event):
        self.save_timer.stop()
        self.persist()
        if self.worker:
            self.worker.requestInterruption()
            self.worker.wait()  # subprocess calls have bounded timeouts
        if self.tray:
            self.tray.hide()
        event.accept()
        QApplication.instance().quit()


def main():
    # Prefer XWayland under GNOME Wayland: native Wayland restricts window positioning.
    if os.environ.get('WAYLAND_DISPLAY') and os.environ.get('DISPLAY'):
        os.environ.setdefault('QT_QPA_PLATFORM', 'xcb')
    app = QApplication(sys.argv)
    app.setApplicationName('MonitorBar')
    app.setOrganizationName('MonitorBar')
    runtime = QStandardPaths.writableLocation(QStandardPaths.RuntimeLocation)
    lock = QLockFile(str(Path(runtime) / 'monitorbar.lock'))
    if not lock.tryLock(100):
        print('MonitorBar est déjà lancé. Clic droit sur la barre ou son icône pour les réglages.')
        return 0
    window = Overlay()
    app.screenAdded.connect(lambda _: window.clamp_position())
    app.screenRemoved.connect(lambda _: window.clamp_position())
    if '--show-bar' in sys.argv:
        window.show_bar()
    result = app.exec_()
    lock.unlock()
    return result
