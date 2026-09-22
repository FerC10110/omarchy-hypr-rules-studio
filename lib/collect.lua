-- Collects Hyprland window rules by RUNNING the config with a stubbed `hl`,
-- the way Hyprland itself loads it. Prints one JSON document on stdout:
--   {"rules":[{"index":0,"file":"...","line":12,"match":{...},"props":{...}}],"error":null}
-- Usage: lua collect.lua <path to hyprland.lua>

local config = arg[1] or (os.getenv("HOME") .. "/.config/hypr/hyprland.lua")
local recorded = {}

-- Hyprland loads the config with ~/.config on package.path (Omarchy's bootstrap
-- sets it); require() inside the config only resolves if we do the same. The
-- config's own directory comes first, its parent second: that is what makes
-- both require("helpers") and require("hypr.rules-studio") find their file.
local dir = config:match("^(.*)/[^/]*$") or "."
local parent = dir:match("^(.*)/[^/]*$") or dir
package.path = dir .. "/?.lua;" .. parent .. "/?.lua;" .. package.path

-- The config reads, calls and concatenates whatever Hyprland exposes, so the
-- stub has to answer all three. Anything missing here stops the load before
-- the first rule is seen.
local function make_stub()
  return setmetatable({}, {
    __index = function() return make_stub() end,
    __call = function() return make_stub() end,
    __concat = function(a, b)
      local function str(v) return type(v) == "table" and "" or tostring(v) end
      return str(a) .. str(b)
    end,
    __tostring = function() return "" end,
  })
end

hl = make_stub()

local SELF = debug.getinfo(1, "S").source

-- A rule's author is the first Lua frame that is neither this collector nor
-- the o.window helper; require() pushes C frames in between.
local function origin()
  for level = 2, 16 do
    local info = debug.getinfo(level, "S")
    if not info then break end
    if info.what ~= "C" and info.source ~= SELF and not info.source:match("helpers%.lua$") then
      return debug.getinfo(level, "Sl")
    end
  end
  return debug.getinfo(2, "Sl")
end

hl.window_rule = function(rules)
  local info = origin()
  recorded[#recorded + 1] = { file = info.source:gsub("^@", ""), line = info.currentline, rules = rules }
end

-- Minimal JSON writer: the values are strings, numbers, booleans and arrays.
local function escape(s)
  return (s:gsub('[%c"\\]', function(c)
    local map = { ['"'] = '\\"', ["\\"] = "\\\\", ["\n"] = "\\n", ["\r"] = "\\r", ["\t"] = "\\t" }
    return map[c] or string.format("\\u%04x", c:byte())
  end))
end

local function is_array(t)
  local n = 0
  for _ in pairs(t) do n = n + 1 end
  return n == #t
end

-- `is_array({})` is true (0 == #{}), so an empty table would otherwise encode
-- as `[]`. `match` and `props` are dicts by contract even when empty, so they
-- are marked with OBJECT_MT to force object encoding regardless of shape.
local OBJECT_MT = {}

local function as_object(t)
  return setmetatable(t, OBJECT_MT)
end

local encode

local function encode_object(t)
  local parts = {}
  local keys = {}
  for key in pairs(t) do keys[#keys + 1] = tostring(key) end
  table.sort(keys)
  for _, key in ipairs(keys) do
    parts[#parts + 1] = '"' .. escape(key) .. '":' .. encode(t[key])
  end
  return "{" .. table.concat(parts, ",") .. "}"
end

encode = function(v)
  local kind = type(v)
  if v == nil then return "null" end
  if kind == "boolean" or kind == "number" then return tostring(v) end
  if kind == "string" then return '"' .. escape(v) .. '"' end
  if kind ~= "table" then return '"' .. escape(tostring(v)) .. '"' end
  if getmetatable(v) ~= OBJECT_MT and is_array(v) then
    local parts = {}
    for _, item in ipairs(v) do parts[#parts + 1] = encode(item) end
    return "[" .. table.concat(parts, ",") .. "]"
  end
  return encode_object(v)
end

local ok, err = pcall(dofile, config)

local out = {}
for index, entry in ipairs(recorded) do
  local match = entry.rules.match or {}
  local props = {}
  for key, value in pairs(entry.rules) do
    if key ~= "match" then props[key] = value end
  end
  out[index] = { index = index - 1, file = entry.file, line = entry.line,
                  match = as_object(match), props = as_object(props) }
end

-- Not `ok and nil or tostring(err)`: when ok is true, `true and nil` is nil,
-- and nil is falsy, so the `or` branch would still fire and stringify the
-- absent error as "nil". An explicit if avoids that classic Lua pitfall.
local error_message = nil
if not ok then error_message = tostring(err) end

io.write(encode({ rules = out, error = error_message }), "\n")
