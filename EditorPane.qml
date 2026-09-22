import QtQuick
import QtQuick.Layouts
import qs.Commons
import qs.Ui

// A rule as a form: what to match on the left, what to change on the right.
// Prefilled from the window the Inspector had selected, or from `rule` when
// the "My rules" list below is used to edit a saved one. The engine
// validates again on save; `complete` only decides when the buttons go live.
Item {
  id: pane
  property var window: null            // the window this rule was started from
  property var rule: null              // an existing studio rule, or null for a new one
  property var mine: []                // this user's saved rules, one row each (Task 9)
  property color foreground: Color.foreground
  property color accent: Color.accent
  readonly property color dim: Qt.darker(foreground, 1.55)
  property string fontFamily: Style.font.family

  signal saveRequested(var fields)
  signal previewRequested(var props)
  signal removeRequested(string id)
  signal ruleSelected(string id)
  signal newRuleRequested()
  signal cancelled()

  // Only the boolean props need state of their own: Toggle is stateless and
  // relies on the caller to hold `checked`. The text fields below are their
  // own source of truth (set imperatively in load(), read directly in
  // fields()/complete) so a plain `text: pane.something` binding never has
  // to survive the user typing into it.
  property bool wantFloat: false
  property bool wantPin: false
  property bool wantNoFocus: false

  // No form field edits these: they only exist so editing a rule that has
  // them does not silently strip them on save (Minor). Carried through
  // fields() unchanged from whatever `rule` had.
  property string comment: ""
  property string initialClass: ""
  property string initialTitle: ""

  // I5: what a person would reasonably type for "WxH" - digits, an x or X
  // (optionally spaced), digits. "1200*800" or anything else is not a size
  // and is refused rather than silently dropped.
  function parseSize(text) {
    if (text === "") return null
    var match = /^\s*(\d+)\s*[xX]\s*(\d+)\s*$/.exec(text)
    if (!match) return null
    var w = parseInt(match[1], 10), h = parseInt(match[2], 10)
    if (isNaN(w) || isNaN(h)) return null
    return [w, h]
  }

  // Mirrors the engine's OPACITY_RE (bin/hypr-rules-studio): one to three
  // numbers, Hyprland's active/inactive/fullscreen opacity shape.
  readonly property var opacityPattern: /^\d+(\.\d+)?(\s+\d+(\.\d+)?){0,2}$/

  readonly property var parsedSize: pane.parseSize(sizeField.text)
  readonly property bool sizeOk: sizeField.text === "" || parsedSize !== null
  readonly property bool opacityOk: opacityField.text === "" || opacityPattern.test(opacityField.text)

  // Filling the form from a window or an existing rule happens here, so the
  // fields stay plain values the user can type over afterwards.
  function load() {
    if (rule) {
      classField.text = (rule.match && rule.match["class"]) || ""
      titleField.text = (rule.match && rule.match.title) || ""
      initialClass = (rule.match && rule.match.initial_class) || ""
      initialTitle = (rule.match && rule.match.initial_title) || ""
      comment = rule.comment || ""
      var props = rule.props || {}
      wantFloat = props.float === true
      wantPin = props.pin === true
      wantNoFocus = props.no_focus === true
      sizeField.text = props.size ? (props.size[0] + "x" + props.size[1]) : ""
      workspaceField.text = props.workspace || ""
      opacityField.text = props.opacity || ""
    } else {
      classField.text = window ? ("^(" + window["class"] + ")$") : ""
      titleField.text = ""
      initialClass = ""; initialTitle = ""; comment = ""
      wantFloat = false; wantPin = false; wantNoFocus = false
      sizeField.text = ""; workspaceField.text = ""; opacityField.text = ""
    }
  }

  // The engine validates too; this is only so the buttons can go quiet.
  // I5: a filled Size/Opacity field that does not parse must not just be
  // silently dropped by fields() below - it keeps the form incomplete
  // instead, with the warning text next to the field saying why.
  readonly property bool complete: (classField.text !== "" || titleField.text !== "")
    && (wantFloat || wantPin || wantNoFocus
        || sizeField.text !== "" || workspaceField.text !== "" || opacityField.text !== "")
    && sizeOk && opacityOk

  function fields() {
    var match = {}
    if (classField.text !== "") match["class"] = classField.text
    if (titleField.text !== "") match.title = titleField.text
    if (initialClass !== "") match.initial_class = initialClass
    if (initialTitle !== "") match.initial_title = initialTitle
    var props = {}
    if (wantFloat) props.float = true
    if (wantPin) props.pin = true
    if (wantNoFocus) props.no_focus = true
    if (workspaceField.text !== "") props.workspace = workspaceField.text
    if (opacityField.text !== "" && opacityOk) props.opacity = opacityField.text
    if (sizeField.text !== "" && parsedSize !== null) props.size = parsedSize
    var out = { "match": match, "props": props }
    if (rule) out.id = rule.id
    if (comment !== "") out.comment = comment
    return out
  }

  onWindowChanged: load()
  onRuleChanged: load()
  Component.onCompleted: load()

  component FieldLabel: Text {
    Layout.fillWidth: true
    textFormat: Text.PlainText
    color: pane.dim
    font.family: pane.fontFamily
    font.pixelSize: Style.font.caption
  }

  component FieldWarning: Text {
    Layout.fillWidth: true
    wrapMode: Text.Wrap
    textFormat: Text.PlainText
    color: Color.urgent
    font.family: pane.fontFamily
    font.pixelSize: Style.font.caption
  }

  ColumnLayout {
    anchors.fill: parent
    spacing: Style.space(8)

    RowLayout {
      Layout.fillWidth: true
      spacing: Style.space(8)

      Text {
        Layout.fillWidth: true
        text: pane.rule ? "Edit rule" : "New rule"
        textFormat: Text.PlainText
        color: pane.foreground
        font.family: pane.fontFamily
        font.pixelSize: Style.font.body
        font.bold: true
      }

      Button {
        text: "New rule"
        bordered: true
        visible: pane.rule !== null
        foreground: pane.foreground
        fontFamily: pane.fontFamily
        onClicked: pane.newRuleRequested()
      }
    }

    // The only way to reach the Delete button above is picking a saved rule
    // here first - Task 9 closed a gap where the panel could add rules but
    // never edit or remove one individually.
    ColumnLayout {
      Layout.fillWidth: true
      spacing: Style.space(4)
      visible: pane.mine.length > 0

      PanelSectionHeader { Layout.fillWidth: true; text: "My rules"; foreground: pane.foreground; fontFamily: pane.fontFamily }

      ListView {
        Layout.fillWidth: true
        Layout.preferredHeight: Math.min(pane.mine.length, 3) * Style.space(34)
        clip: true
        spacing: Style.space(2)
        model: pane.mine

        delegate: CursorSurface {
          id: ruleRow
          required property var modelData
          width: ListView.view ? ListView.view.width : 0
          height: Style.space(32)
          current: pane.rule !== null && pane.rule.id === ruleRow.modelData.id
          hasCursor: ruleMouse.containsMouse
          foreground: pane.foreground
          accent: pane.accent

          MouseArea {
            id: ruleMouse
            anchors.fill: parent
            hoverEnabled: true
            onClicked: pane.ruleSelected(ruleRow.modelData.id)
          }

          Column {
            anchors.fill: parent
            anchors.margins: Style.space(4)

            Text {
              width: parent.width
              text: (ruleRow.modelData.match && ruleRow.modelData.match["class"])
                || (ruleRow.modelData.match && ruleRow.modelData.match.title) || "(no match)"
              elide: Text.ElideRight
              textFormat: Text.PlainText
              color: pane.foreground
              font.family: pane.fontFamily
              font.pixelSize: Style.font.bodySmall
            }

            Text {
              width: parent.width
              text: ruleRow.modelData.props_text + (ruleRow.modelData.comment ? "   " + ruleRow.modelData.comment : "")
              elide: Text.ElideRight
              textFormat: Text.PlainText
              color: pane.dim
              font.family: pane.fontFamily
              font.pixelSize: Style.font.caption
            }
          }
        }
      }

      PanelSeparator { Layout.fillWidth: true; foreground: pane.foreground }
    }

    PanelSectionHeader { Layout.fillWidth: true; text: "Match on"; foreground: pane.foreground; fontFamily: pane.fontFamily }

    FieldLabel { text: "Class (regex)" }
    TextField {
      id: classField
      Layout.fillWidth: true
      placeholderText: "^(kitty)$"
      foreground: pane.foreground
      accent: pane.accent
      // TextField's `accepted` signal fires on Enter but never marks the raw
      // key event accepted, so it would otherwise keep going up to
      // PanelKeyCatcher as a panel-navigation key; swallow it here and use
      // `accepted` itself to walk to the next field.
      Keys.onReturnPressed: function(event) { event.accepted = true }
      Keys.onEnterPressed: function(event) { event.accepted = true }
      Keys.onEscapePressed: function(event) { pane.cancelled(); event.accepted = true }
      onAccepted: titleField.forceActiveFocus()
    }

    FieldLabel { text: "Title (regex, optional)" }
    TextField {
      id: titleField
      Layout.fillWidth: true
      placeholderText: ""
      foreground: pane.foreground
      accent: pane.accent
      Keys.onReturnPressed: function(event) { event.accepted = true }
      Keys.onEnterPressed: function(event) { event.accepted = true }
      Keys.onEscapePressed: function(event) { pane.cancelled(); event.accepted = true }
      onAccepted: sizeField.forceActiveFocus()
    }

    PanelSeparator { Layout.fillWidth: true; foreground: pane.foreground }
    PanelSectionHeader { Layout.fillWidth: true; text: "Change"; foreground: pane.foreground; fontFamily: pane.fontFamily }

    Toggle {
      Layout.fillWidth: true
      label: "Float"
      checked: pane.wantFloat
      foreground: pane.foreground
      accent: pane.accent
      fontFamily: pane.fontFamily
      onClicked: pane.wantFloat = !pane.wantFloat
    }

    Toggle {
      Layout.fillWidth: true
      label: "Pin"
      checked: pane.wantPin
      foreground: pane.foreground
      accent: pane.accent
      fontFamily: pane.fontFamily
      onClicked: pane.wantPin = !pane.wantPin
    }

    Toggle {
      Layout.fillWidth: true
      label: "No focus"
      description: "Do not steal focus when it opens"
      checked: pane.wantNoFocus
      foreground: pane.foreground
      accent: pane.accent
      fontFamily: pane.fontFamily
      onClicked: pane.wantNoFocus = !pane.wantNoFocus
    }

    RowLayout {
      Layout.fillWidth: true
      spacing: Style.space(8)

      ColumnLayout {
        Layout.fillWidth: true
        spacing: Style.space(4)
        FieldLabel { text: "Size (WxH pixels)" }
        TextField {
          id: sizeField
          Layout.fillWidth: true
          placeholderText: "1200x800"
          foreground: pane.foreground
          accent: pane.accent
          Keys.onReturnPressed: function(event) { event.accepted = true }
          Keys.onEnterPressed: function(event) { event.accepted = true }
          Keys.onEscapePressed: function(event) { pane.cancelled(); event.accepted = true }
          onAccepted: workspaceField.forceActiveFocus()
        }
        FieldWarning {
          visible: sizeField.text !== "" && !pane.sizeOk
          text: "Use WxH, like 1200x800."
        }
      }

      ColumnLayout {
        Layout.fillWidth: true
        spacing: Style.space(4)
        FieldLabel { text: "Workspace" }
        TextField {
          id: workspaceField
          Layout.fillWidth: true
          placeholderText: "5"
          foreground: pane.foreground
          accent: pane.accent
          Keys.onReturnPressed: function(event) { event.accepted = true }
          Keys.onEnterPressed: function(event) { event.accepted = true }
          Keys.onEscapePressed: function(event) { pane.cancelled(); event.accepted = true }
          onAccepted: opacityField.forceActiveFocus()
        }
      }

      ColumnLayout {
        Layout.fillWidth: true
        spacing: Style.space(4)
        FieldLabel { text: "Opacity" }
        TextField {
          id: opacityField
          Layout.fillWidth: true
          placeholderText: "0.9"
          foreground: pane.foreground
          accent: pane.accent
          Keys.onReturnPressed: function(event) { event.accepted = true }
          Keys.onEnterPressed: function(event) { event.accepted = true }
          Keys.onEscapePressed: function(event) { pane.cancelled(); event.accepted = true }
          onAccepted: if (pane.complete) pane.saveRequested(pane.fields())
        }
        FieldWarning {
          visible: opacityField.text !== "" && !pane.opacityOk
          text: "Use one to three numbers, like 0.9 or 0.9 0.6."
        }
      }
    }

    Item { Layout.fillHeight: true }

    RowLayout {
      Layout.fillWidth: true
      spacing: Style.space(8)
      Button {
        text: "Test on this window"
        bordered: true
        enabled: pane.complete && pane.window !== null
        foreground: pane.foreground
        fontFamily: pane.fontFamily
        onClicked: pane.previewRequested(pane.fields().props)
      }
      Button {
        text: "Save"
        bordered: true
        enabled: pane.complete
        foreground: pane.accent
        fontFamily: pane.fontFamily
        onClicked: pane.saveRequested(pane.fields())
      }
      Button {
        text: "Delete"
        bordered: true
        visible: pane.rule !== null
        foreground: Color.urgent
        fontFamily: pane.fontFamily
        onClicked: pane.removeRequested(pane.rule.id)
      }
      Item { Layout.fillWidth: true }
      Button {
        text: "Cancel"
        bordered: true
        foreground: pane.foreground
        fontFamily: pane.fontFamily
        onClicked: pane.cancelled()
      }
    }
  }
}
