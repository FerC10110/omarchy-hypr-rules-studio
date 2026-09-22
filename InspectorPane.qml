import QtQuick
import QtQuick.Layouts
import qs.Commons
import qs.Ui

// Left: the open windows. Right: what you end up with (the final value of
// every property a rule touches, one row per property) and, below it, every
// rule that applies to the selected window, in config order, with the file
// and line that wrote it, and which property wins. The pencil is the one
// control this view offers: it asks the panel to switch to the editor
// (Task 7).
Item {
  id: pane
  property var windows: []
  property string windowsError: ""     // why `windows` might not reflect reality, straight from the engine
  property string selectedAddress: ""
  property var explained: null
  property string explainError: ""     // why `explained` is null, straight from the engine
  property color foreground: Color.foreground
  property color accent: Color.accent
  readonly property color dim: Qt.darker(foreground, 1.55)
  property string fontFamily: Style.font.family
  property string monoFamily: Style.fontFamily

  signal selected(string address)
  signal editRequested()

  readonly property var applied: explained && explained.applied ? explained.applied : []
  readonly property bool tagMismatch: explained && explained.tags ? explained.tags.mismatch === true : false

  // I1: one row per property `resolve()` found a final value for, each
  // already carrying its own display string and file:line (engine-built,
  // not formatted here) - sorted by property name for a stable order.
  readonly property var effectiveRows: {
    var out = []
    var eff = pane.explained && pane.explained.effective ? pane.explained.effective : {}
    var keys = Object.keys(eff).sort()
    for (var i = 0; i < keys.length; i++) {
      out.push(eff[keys[i]])
    }
    return out
  }

  RowLayout {
    anchors.fill: parent
    spacing: Style.space(12)

    ListView {
      Layout.preferredWidth: Style.space(260)
      Layout.fillHeight: true
      clip: true
      model: pane.windows

      delegate: CursorSurface {
        id: row
        required property var modelData
        width: ListView.view ? ListView.view.width : 0
        height: Style.space(30)
        current: modelData.address === pane.selectedAddress
        hasCursor: rowMouse.containsMouse
        foreground: pane.foreground
        accent: pane.accent

        MouseArea {
          id: rowMouse
          anchors.fill: parent
          hoverEnabled: true
          onClicked: pane.selected(row.modelData.address)
        }

        Text {
          anchors.fill: parent
          anchors.margins: Style.space(6)
          verticalAlignment: Text.AlignVCenter
          text: row.modelData["class"] + " · " + row.modelData.title
          elide: Text.ElideRight
          textFormat: Text.PlainText
          color: pane.foreground
          font.family: pane.fontFamily
          font.pixelSize: Style.font.body
        }
      }
    }

    ColumnLayout {
      Layout.fillWidth: true
      Layout.fillHeight: true
      spacing: Style.space(6)

      RowLayout {
        Layout.fillWidth: true
        spacing: Style.space(6)

        Text {
          Layout.fillWidth: true
          visible: pane.explained !== null
          text: pane.explained ? "class " + pane.explained.window["class"]
            + "   title " + pane.explained.window.title
            + (pane.explained.tags.simulated.length > 0 ? "   tags " + pane.explained.tags.simulated.join(", ") : "") : ""
          wrapMode: Text.Wrap
          textFormat: Text.PlainText
          color: pane.dim
          font.family: pane.monoFamily
          font.pixelSize: Style.font.bodySmall
        }

        PanelActionButton {
          iconText: "✎"
          tooltipText: "New rule for this window"
          // Only needs a window selected, not a successful `explain` - a new
          // rule's form only reads the window itself (for its class), so
          // this must not lock up when the config fails to load and
          // `explained` stays null for every window (that's the "See your
          // windows anyway" / "My rules" path back in while broken).
          enabled: pane.selectedAddress !== ""
          foreground: pane.foreground
          hoverColor: pane.accent
          onClicked: pane.editRequested()
        }
      }

      Text {
        Layout.fillWidth: true
        visible: pane.tagMismatch
        text: "The tags I work out do not match the ones Hyprland reports, so a rule below may be wrong."
        wrapMode: Text.Wrap
        textFormat: Text.PlainText
        color: Color.urgent
        font.family: pane.fontFamily
        font.pixelSize: Style.font.bodySmall
      }

      // I2: Hyprland being unreachable is a different fact from "no windows
      // are open" - showing the empty-state text for both left a confident,
      // false claim on screen (the notice that carries the real error is
      // wiped after 5s by noticeTimer, so it cannot be relied on here).
      Text {
        Layout.fillWidth: true
        visible: pane.windowsError !== ""
        text: "I can't list your windows: " + pane.windowsError
        wrapMode: Text.Wrap
        textFormat: Text.PlainText
        color: Color.urgent
        font.family: pane.fontFamily
        font.pixelSize: Style.font.bodySmall
      }

      Text {
        Layout.fillWidth: true
        visible: pane.windows.length === 0 && pane.windowsError === ""
        text: "No windows are open right now."
        wrapMode: Text.Wrap
        textFormat: Text.PlainText
        color: pane.dim
        font.family: pane.fontFamily
        font.pixelSize: Style.font.bodySmall
      }

      // Most commonly: the config doesn't load, so there is no way to know
      // what applies to this window - the same failure the Doctor reports.
      // Without this the list below would just go blank with no explanation.
      Text {
        Layout.fillWidth: true
        visible: pane.selectedAddress !== "" && pane.explainError !== ""
        text: "I can't tell you what applies to this window: " + pane.explainError
        wrapMode: Text.Wrap
        textFormat: Text.PlainText
        color: Color.urgent
        font.family: pane.fontFamily
        font.pixelSize: Style.font.bodySmall
      }

      Text {
        Layout.fillWidth: true
        visible: pane.explained !== null && pane.applied.length === 0
        text: "No rule in your config applies to this window."
        wrapMode: Text.Wrap
        textFormat: Text.PlainText
        color: pane.dim
        font.family: pane.fontFamily
        font.pixelSize: Style.font.bodySmall
      }

      // I1: "what you end up with" - the final value of every property a
      // rule touches, one row per property, each naming the file:line that
      // set it last. The list below is history; this is what actually
      // happens to the window.
      Column {
        Layout.fillWidth: true
        spacing: Style.space(2)
        visible: pane.effectiveRows.length > 0

        PanelSectionHeader { width: parent.width; text: "What you end up with"; foreground: pane.foreground; fontFamily: pane.fontFamily }

        Repeater {
          model: pane.effectiveRows
          delegate: Column {
            required property var modelData
            width: parent.width

            Text {
              width: parent.width
              text: modelData.text + (modelData.certain ? "" : "   (maybe)")
              wrapMode: Text.Wrap
              textFormat: Text.PlainText
              color: pane.foreground
              font.family: pane.monoFamily
              font.pixelSize: Style.font.bodySmall
            }

            Text {
              width: parent.width
              text: modelData.source + " · " + modelData.file + ":" + modelData.line
              elide: Text.ElideMiddle
              textFormat: Text.PlainText
              color: pane.dim
              font.family: pane.fontFamily
              font.pixelSize: Style.font.caption
            }
          }
        }

        PanelSeparator { width: parent.width; foreground: pane.foreground }
      }

      ListView {
        Layout.fillWidth: true
        Layout.fillHeight: true
        clip: true
        spacing: Style.space(4)
        model: pane.applied

        delegate: Column {
          required property var modelData
          width: ListView.view ? ListView.view.width : 0

          Text {
            width: parent.width
            text: modelData.props_text + (modelData.certain ? "" : "   (maybe)")
            wrapMode: Text.Wrap
            textFormat: Text.PlainText
            color: pane.foreground
            font.family: pane.monoFamily
            font.pixelSize: Style.font.bodySmall
          }

          Text {
            width: parent.width
            text: modelData.source + " · " + modelData.file + ":" + modelData.line
            elide: Text.ElideMiddle
            textFormat: Text.PlainText
            color: pane.dim
            font.family: pane.fontFamily
            font.pixelSize: Style.font.caption
          }
        }
      }
    }
  }
}
