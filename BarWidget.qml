import QtQuick
import qs.Commons
import qs.Ui

// Bar entry point. The icon is all the bar sees; the panel is loaded lazily
// and injected with the bar context, like Runbook and Save Them All.
BarWidget {
  id: root
  moduleName: "io.github.ferc10110.hypr-rules-studio"

  readonly property bool opened: panelLoader.item ? panelLoader.item.opened === true : false
  readonly property bool configBroken: panelLoader.item ? panelLoader.item.configBroken === true : false

  function open() { if (panelLoader.item) panelLoader.item.open() }
  function close() { if (panelLoader.item) panelLoader.item.close() }
  function togglePanel() { if (panelLoader.item) panelLoader.item.toggle() }

  function injectPanel() {
    var target = panelLoader.item
    if (!target) return
    if ("bar" in target) target.bar = root.bar
    if ("settings" in target) target.settings = root.settings
    if ("anchorItem" in target) target.anchorItem = button
    if ("hostWidget" in target) target.hostWidget = root
  }

  implicitWidth: button.implicitWidth
  implicitHeight: button.implicitHeight

  onBarChanged: injectPanel()
  onSettingsChanged: injectPanel()

  Loader {
    id: panelLoader
    active: true
    source: Qt.resolvedUrl("Panel.qml")
    visible: false
    onLoaded: {
      root.injectPanel()
      Qt.callLater(root.injectPanel)
    }
  }

  BarIconButton {
    id: button
    anchors.fill: parent
    bar: root.bar
    text: "\u{F05B0}"
    slotSize: Style.bar.statusSlot
    tooltipText: root.configBroken ? "Hypr Rules Studio · config errors" : "Hypr Rules Studio"
    active: root.configBroken
    onPressed: function(b) { root.togglePanel() }
  }
}
