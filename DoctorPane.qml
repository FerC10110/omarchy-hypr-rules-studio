import QtQuick
import QtQuick.Layouts
import qs.Commons
import qs.Ui

// What is wrong, in plain words, with the file and line to go fix it. The
// engine already writes `title`/`detail` for every problem kind it knows
// about (and any future one), so this view never switches on `kind` - it
// just renders whatever `problems` holds.
Item {
  id: pane
  property var report: null
  property bool checking: false
  property color foreground: Color.foreground
  property string fontFamily: Style.font.family
  readonly property color dim: Qt.darker(foreground, 1.55)

  signal recheckRequested()
  signal purgeRequested()
  signal backRequested()

  readonly property var problems: report && report.problems ? report.problems : []

  ColumnLayout {
    anchors.fill: parent
    spacing: Style.space(8)

    Text {
      Layout.fillWidth: true
      text: pane.checking ? "Checking…"
        : (pane.report === null ? "Not checked yet"
           : (pane.report.healthy
              ? "Your config loads and every rule of yours is in effect."
              : (pane.report.updated_since_last_ok
                 ? "This broke after Hyprland was updated to " + pane.report.hyprland + "."
                 : "Something is wrong:")))
      wrapMode: Text.Wrap
      textFormat: Text.PlainText
      color: pane.foreground
      font.family: pane.fontFamily
      font.pixelSize: Style.font.body
    }

    ListView {
      Layout.fillWidth: true
      Layout.fillHeight: true
      clip: true
      spacing: Style.space(6)
      model: pane.problems

      delegate: Column {
        required property var modelData
        width: ListView.view ? ListView.view.width : 0

        Text {
          width: parent.width
          text: modelData.title
          wrapMode: Text.Wrap
          textFormat: Text.PlainText
          color: Color.urgent
          font.family: pane.fontFamily
          font.pixelSize: Style.font.bodySmall
        }

        Text {
          width: parent.width
          text: modelData.detail
          wrapMode: Text.Wrap
          textFormat: Text.PlainText
          color: pane.dim
          font.family: pane.fontFamily
          font.pixelSize: Style.font.caption
        }
      }
    }

    RowLayout {
      Layout.fillWidth: true
      spacing: Style.space(8)

      // A broken config must never be a dead end: this is the only way back
      // to the Inspector (and from there the Editor's "My rules" list) while
      // it stays unhealthy, since the panel stops auto-routing here once the
      // user has left on purpose.
      Button {
        text: "See your windows anyway"
        bordered: true
        foreground: pane.foreground
        fontFamily: pane.fontFamily
        onClicked: pane.backRequested()
      }

      Button {
        text: "Check again"
        bordered: true
        foreground: pane.foreground
        fontFamily: pane.fontFamily
        onClicked: pane.recheckRequested()
      }

      Item { Layout.fillWidth: true }

      Button {
        text: "Remove everything I wrote"
        bordered: true
        // I7: a corrupt store forces rule_count to 0, which would otherwise
        // hide the one button that can fix it - show it whenever there is
        // something to purge, or the engine could not even tell.
        visible: pane.report !== null && (pane.report.rule_count > 0 || pane.report.state_error === true)
        foreground: Color.urgent
        fontFamily: pane.fontFamily
        onClicked: pane.purgeRequested()
      }
    }
  }
}
