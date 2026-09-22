-- A miniature stand-in for the user's ~/.config/hypr/hyprland.lua.
require("helpers")
o.window(".*", { tag = "+default-opacity" })
require("apps.term")
o.window({ tag = "default-opacity" }, { opacity = "0.985 0.96" })
