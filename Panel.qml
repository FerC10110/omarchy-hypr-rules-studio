import QtQuick
import QtQuick.Layouts
import Quickshell
import Quickshell.Io
import qs.Commons
import qs.Ui

// Hypr Rules Studio panel: a thin face over bin/hypr-rules-studio. Three
// views share this one panel, switched by `view`: the Inspector (lists open
// windows and, for the selected one, every rule that applies to it, in
// config order, with the file and line that wrote it), the Editor (a rule
// as a form, plus the "My rules" list to edit or delete a saved one), and
// the Doctor (why the config isn't doing what you expect).
Panel {
  id: studio   // not `root`: inside a Component handed to KeyboardPanel, `root` resolves to it
  moduleName: "io.github.ferc10110.hypr-rules-studio"
  ipcTarget: "io.github.ferc10110.hypr-rules-studio"
  manageIpc: true

  property var anchorItem: null
  property var hostWidget: null

  // ---- state owned by this panel
  property string view: "inspector"           // inspector | editor | doctor
  property var windows: []
  property string windowsError: ""             // why `windows` might be stale/empty, in the engine's own words
  property string selectedAddress: ""
  property var explained: null                // the "explain" payload for the selection
  property string explainError: ""            // why `explained` is null, in the engine's own words
  property var mine: []                        // this user's saved rules, for the Editor's list (Task 9)
  property var editingRule: null               // the rule the Editor form is loaded from, or null for "new"
  property var report: null                    // the last `doctor` payload
  property bool checking: false
  // Task 5 declared this as a plain `false`; Task 9 turns it into a binding
  // off the doctor report (QML refuses a second `property` for the same name).
  property bool configBroken: report !== null && report.healthy === false
  property string notice: ""
  property bool noticeIsError: false

  property int viewWidth: 900
  property int viewHeight: 560

  readonly property var selectedWindow: {
    for (var i = 0; i < windows.length; i++)
      if (windows[i].address === selectedAddress) return windows[i]
    return null
  }

  readonly property color foreground: bar ? bar.foreground : Color.foreground
  // Bar.qml does not expose an `accent` property (only foreground/urgent do);
  // guard the read so this falls back cleanly instead of assigning undefined.
  readonly property color accent: (bar && bar.accent !== undefined) ? bar.accent : Color.accent
  readonly property color urgent: bar ? bar.urgent : Color.urgent
  readonly property color dim: Qt.darker(foreground, 1.55)
  readonly property string fontFamily: bar ? bar.fontFamily : Style.font.family
  readonly property string monoFamily: Style.fontFamily

  function pluginPath(relative) {
    var url = String(Qt.resolvedUrl(relative))
    return url.indexOf("file://") === 0 ? decodeURIComponent(url.substring(7)) : url
  }

  function refresh() {
    engineCall(["windows"], undefined, function(payload) {
      if (!payload || payload.error !== undefined) {
        // Distinct from "no windows are open": Hyprland could not be asked
        // at all, so windows stays whatever it was rather than being wiped
        // to [] and rendered as the (false) "no windows" empty state.
        windowsError = (payload && payload.error) ? payload.error : "Could not list your windows."
        return
      }
      windowsError = ""
      windows = payload.windows
      if (selectedAddress === "" && windows.length > 0) selectedAddress = windows[0].address
      explain()
    })
  }

  function explain() {
    if (selectedAddress === "") { explained = null; explainError = ""; return }
    engineCall(["explain", selectedAddress], undefined, function(payload) {
      if (payload && payload.error === undefined) {
        explained = payload
        explainError = ""
      } else {
        // Most commonly: the config doesn't load, so collect_rules failed -
        // the same failure the Doctor reports. Without this, the Inspector
        // would just go blank with no clue why, right when the user is most
        // likely to be looking at it (the Doctor's "See your windows
        // anyway" link routes here specifically for this scenario).
        explained = null
        explainError = (payload && payload.error) ? payload.error : "Could not read your rules."
      }
    })
  }

  function select(address) { selectedAddress = address }

  // Entry points into the Editor. The pencil always starts a fresh rule;
  // picking a row in the "My rules" list (Task 9) loads that one instead,
  // which is what makes EditorPane's existing Delete button reachable.
  function startEdit() {
    editingRule = null
    view = "editor"
    loadMine()
  }

  function selectRule(id) {
    for (var i = 0; i < mine.length; i++) {
      if (mine[i].id === id) { editingRule = mine[i]; return }
    }
  }

  function newRule() { editingRule = null }

  function cancelEdit() {
    editingRule = null
    view = "inspector"
  }

  // Tab / Shift+Tab (PanelKeyCatcher.tabRequested) cycle the three views in
  // the order a person reads them: what applies now, what you can change,
  // what is wrong (C1). Landing on the Editor sets it up the same way the
  // pencil does (fresh rule, "My rules" loaded), so it is never stale.
  function cycleView(direction) {
    var order = ["inspector", "editor", "doctor"]
    var at = order.indexOf(view)
    if (at === -1) at = 0
    var next = order[(at + direction + order.length) % order.length]
    if (next === "editor" && view !== "editor") { editingRule = null; loadMine() }
    view = next
  }

  function loadMine() {
    engineCall(["mine"], undefined, function(payload) {
      if (payload && payload.error === undefined) mine = payload.rules || []
    })
  }

  // Editing an existing rule is remove-then-add: the engine has no in-place
  // update, only add_rule (always a fresh id) and remove_rule. A new rule
  // (no id) skips straight to save-rule. If the removal fails, the add must
  // not run at all - otherwise a rename/tweak that fails to remove the old
  // rule would silently add a duplicate instead of editing it. finishEngine
  // already put the error in `notice`; the form is left exactly as it was.
  function saveRule(fields) {
    if (fields.id) {
      engineCall(["remove-rule", fields.id], undefined, function(payload) {
        if (!payload || payload.error !== undefined) return
        doSaveRule(fields)
      })
    } else {
      doSaveRule(fields)
    }
  }

  function doSaveRule(fields) {
    engineCall(["save-rule"], fields, function(payload) {
      if (!payload || payload.error !== undefined) return
      mine = payload.rules || []
      editingRule = null
      showNotice("Saved. Run `hyprctl reload` to apply it.")
      view = "inspector"
      explain()
    })
  }

  function previewRule(props) {
    if (selectedAddress === "") return
    engineCall(["preview", selectedAddress], { "props": props }, function(payload) {
      // An engine error already reaches the notice through finishEngine
      // (in urgent color); this only has to describe a payload that came
      // back clean but did, or didn't, actually change anything.
      if (!payload || payload.error !== undefined) return
      var applied = payload.applied || []
      var skipped = payload.skipped || []
      var failed = payload.failed || {}
      var failedKeys = Object.keys(failed)
      // I4: nothing here is undone when the panel closes or the config
      // reloads without this rule saved - every notice that reports a real
      // change on the window says so plainly, never implying it reverts.
      var stays = " This stays on the window until you change it back or reload."
      if (applied.length === 0 && failedKeys.length === 0) {
        // Nothing was dispatched at all - saying "Tried it" here would
        // read as if the window changed when it didn't.
        showNotice(skipped.length > 0
          ? "Nothing here can be tried live; these only work through the config: " + skipped.join(", ")
          : "Nothing to try.")
      } else if (failedKeys.length > 0) {
        // I3: a property failing partway through must not hide what the
        // properties before it already did to the window.
        var detail = failedKeys.map(function(key) { return key + ": " + failed[key] }).join("; ")
        showNotice(applied.length > 0
          ? "Tried " + applied.join(", ") + ", but " + detail + "." + stays
          : "Nothing took: " + detail, true)
      } else if (skipped.length > 0) {
        showNotice("Tried it." + stays + " These only work through the config: " + skipped.join(", "))
      } else {
        showNotice("Tried it on this window." + stays)
      }
    })
  }

  function removeRule(id) {
    engineCall(["remove-rule", id], undefined, function(payload) {
      if (!payload || payload.error !== undefined) return
      mine = payload.rules || []
      editingRule = null
      showNotice("Removed.")
      view = "inspector"
      explain()
    })
  }

  function showNotice(text, isError) {
    notice = text
    noticeIsError = isError === true
    // An error is the only account the panel can give of a failure, and it
    // arrives when you are looking at the window, not at the notice. Five
    // seconds was not enough to read one: errors now stay until the next
    // notice replaces them. Confirmations still clear themselves.
    if (noticeIsError) noticeTimer.stop()
    else noticeTimer.restart()
  }

  function checkHealth() {
    checking = true
    engineCall(["doctor"], undefined, function(payload) {
      checking = false
      // The whole point of the Doctor is finding out from the bar icon, not
      // from a misbehaving window three days later: land on it the moment a
      // report *turns* unhealthy, unless a rule is being edited (never yank
      // the form out from under someone mid-edit). This is a one-time route
      // on the transition, not a lock: once the user leaves the Doctor
      // (there is a way back to the Inspector even while broken - see
      // DoctorPane's "See your windows anyway", and the ⚕ button and Tab
      // cycle in the header reach it again on purpose at any time - C1).
      // Recovering is the same idea in reverse: only the transition back to
      // healthy sends the Doctor's "all good" screen to the Inspector, so a
      // Doctor visited on purpose while already healthy (or an Editor in
      // progress) is left alone.
      var wasUnhealthy = report !== null && report.healthy === false
      report = (payload && payload.error === undefined) ? payload : null
      var isUnhealthy = report !== null && report.healthy === false
      if (isUnhealthy && !wasUnhealthy) {
        if (view !== "editor") view = "doctor"
      } else if (!isUnhealthy && wasUnhealthy && view === "doctor") {
        view = "inspector"
      }
    })
  }

  function purgeAll() {
    engineCall(["purge"], undefined, function(payload) {
      // finishEngine already put an engine error in `notice` (urgent red)
      // and restarted the timer; nothing left to do here on failure. Minor:
      // this used to assign `notice` directly on success too, which could
      // leave a *previous* error's red color and a timer that had already
      // fired stuck on screen forever - showNotice is the only path that
      // resets both.
      if (payload && payload.error !== undefined) return
      mine = []
      showNotice("Removed. Reload your Hyprland config to get back to how it was.")
      checkHealth()
    })
  }

  onSelectedAddressChanged: explain()
  onOpenedChanged: if (opened) { refresh(); checkHealth() }

  // The bar icon has to be able to warn before anyone opens the panel, so
  // the check runs once at startup and again whenever the panel is opened.
  Component.onCompleted: checkHealth()

  Timer { id: noticeTimer; interval: 9000; onTriggered: studio.notice = "" }

  // ---- engine: one Process for every call, one call in flight, a queue of
  // pending calls. Copied from Runbook's Panel.qml verbatim.
  property var engineQueue: []
  property var engineCurrent: null

  function engineCall(args, stdinJson, onDone) {
    engineQueue.push({ args: args, stdin: stdinJson, onDone: onDone })
    engineQueue = engineQueue
    pumpEngine()
  }

  function pumpEngine() {
    if (engineCurrent !== null || engineQueue.length === 0) return
    engineCurrent = engineQueue.shift()
    engineQueue = engineQueue
    engineProc.command = [pluginPath("bin/hypr-rules-studio")].concat(engineCurrent.args)
    engineProc.running = true
  }

  function finishEngine(text) {
    var call = engineCurrent
    engineCurrent = null
    var payload = null
    try { payload = JSON.parse(String(text || "")) } catch (e) { payload = { error: "Engine returned no JSON" } }
    if (payload && payload.error !== undefined) showNotice(payload.error, true)
    if (call && call.onDone) call.onDone(payload)
    pumpEngine()
  }

  Process {
    id: engineProc
    stdinEnabled: true
    onStarted: {
      var call = studio.engineCurrent
      // The engine reads exactly one line, so the pipe can stay open.
      // `undefined` is the "no stdin" sentinel; an explicit `null` must
      // still be written as the literal JSON `null` line so the engine's
      // stdin.readline() is not left blocked forever (which would deadlock
      // this shared, serialized Process for every later queued call).
      if (call && call.stdin !== undefined) write(JSON.stringify(call.stdin) + "\n")
    }
    stdout: StdioCollector {
      waitForEnd: true
      onStreamFinished: studio.finishEngine(text)
    }
    stderr: StdioCollector { waitForEnd: true }
  }

  KeyboardPanel {
    id: panel
    anchorItem: studio.anchorItem
    owner: studio.hostWidget || studio
    bar: studio.bar
    open: studio.opened
    focusTarget: keyCatcher
    contentWidth: panel.fittedContentWidth(studio.viewWidth)
    contentHeight: panel.cappedContentHeight(studio.viewHeight)

    PanelKeyCatcher {
      id: keyCatcher
      anchors.fill: parent
      // The editor is a form full of text fields: j/k/x and friends must
      // reach them as ordinary keystrokes, not the Inspector's list cursor.
      blocked: studio.view === "editor"
      onCloseRequested: studio.close()
      // C1: Tab / Shift+Tab cycle Inspector -> Editor -> Doctor and back;
      // previously only onCloseRequested was wired up, so moveRequested/
      // activateRequested/tabRequested/textKey were all silently discarded.
      onTabRequested: function(direction) { studio.cycleView(direction) }

      ColumnLayout {
        anchors.fill: parent
        anchors.margins: Style.space(12)
        spacing: Style.space(8)

        PanelHero {
          Layout.fillWidth: true
          title: "Hypr Rules Studio"
          meta: studio.windows.length === 1 ? "1 window" : studio.windows.length + " windows"
          foreground: studio.foreground
          fontFamily: studio.fontFamily

          // C1: the only way to reach the Doctor when the config is
          // healthy - without it, DoctorPane's healthy-state text and
          // "Remove everything I wrote" are both unreachable. Visible (and
          // reachable) from every view, since PanelHero sits above the
          // view-conditional panes below; disabled rather than hidden when
          // already on the Doctor, so it never reads as a dead click.
          trailingControl: Component {
            PanelActionButton {
              iconText: "⚕"
              tooltipText: "Doctor"
              enabled: studio.view !== "doctor"
              foreground: studio.foreground
              hoverColor: studio.accent
              onClicked: studio.view = "doctor"
            }
          }
        }

        Text {
          Layout.fillWidth: true
          visible: studio.notice !== ""
          text: studio.notice
          wrapMode: Text.Wrap
          textFormat: Text.PlainText
          color: studio.noticeIsError ? studio.urgent : studio.dim
          font.family: studio.fontFamily
          font.pixelSize: Style.font.bodySmall
        }

        InspectorPane {
          Layout.fillWidth: true
          Layout.fillHeight: true
          visible: studio.view === "inspector"
          windows: studio.windows
          windowsError: studio.windowsError
          selectedAddress: studio.selectedAddress
          explained: studio.explained
          explainError: studio.explainError
          foreground: studio.foreground
          accent: studio.accent
          fontFamily: studio.fontFamily
          monoFamily: studio.monoFamily
          onSelected: function(address) { studio.select(address) }
          onEditRequested: studio.startEdit()
        }

        EditorPane {
          Layout.fillWidth: true
          Layout.fillHeight: true
          visible: studio.view === "editor"
          window: studio.selectedWindow
          rule: studio.editingRule
          mine: studio.mine
          foreground: studio.foreground
          accent: studio.accent
          fontFamily: studio.fontFamily
          onSaveRequested: function(fields) { studio.saveRule(fields) }
          onPreviewRequested: function(props) { studio.previewRule(props) }
          onRemoveRequested: function(id) { studio.removeRule(id) }
          onRuleSelected: function(id) { studio.selectRule(id) }
          onNewRuleRequested: studio.newRule()
          onCancelled: studio.cancelEdit()
        }

        DoctorPane {
          Layout.fillWidth: true
          Layout.fillHeight: true
          visible: studio.view === "doctor"
          report: studio.report
          checking: studio.checking
          foreground: studio.foreground
          fontFamily: studio.fontFamily
          onRecheckRequested: studio.checkHealth()
          onPurgeRequested: studio.purgeAll()
          onBackRequested: studio.view = "inspector"
        }
      }
    }
  }
}
