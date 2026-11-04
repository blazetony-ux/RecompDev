-- Experimental MAME 0.289 Lua *frame observer*. Not an instruction or complete I/O oracle.
-- Source: original-ROM execution by an independently installed MAME binary.
-- Run ONLY from Capture-MAME-SMS.py; required environment supplied by launcher.
local destination = os.getenv('RECOMPDEV_MAME_FRAME_OUTPUT')
local bus_destination = os.getenv('RECOMPDEV_MAME_BUS_OUTPUT')
local limit = tonumber(os.getenv('RECOMPDEV_MAME_FRAME_LIMIT') or '')
if not destination or not limit or limit < 1 or limit > 1200 or limit ~= math.floor(limit) then
    error('Missing bounded RecompDev MAME frame-capture environment')
end
local output = assert(io.open(destination, 'wb'))
local bus_file = assert(io.open(bus_destination, 'wb'))
local bus_count = 0
local count = 0
local finished = false
local function state_number(cpu, key)
    local entry = cpu.state and cpu.state[key]
    if entry == nil then return nil end
    return tonumber(entry.value)
end
local function capture()
    if finished then return end
    local cpu = manager.machine.devices[':maincpu']
    if not cpu then error('MAME system does not expose :maincpu') end
    local pc = state_number(cpu,'PC') or state_number(cpu,'CURPC')
    if not pc then error('MAME CPU does not expose PC; cannot capture reliable frame observations') end
    count = count + 1
    local parts = {string.format('{"type":"frame","ordinal":%d,"pc":%d', count, pc)}
    for _, key in ipairs({'AF','BC','DE','HL','SP'}) do
        local value = state_number(cpu,key)
        if value then parts[#parts+1] = string.format(',"%s":%d', string.lower(key), value) end
    end
    parts[#parts+1] = '}\n'
    assert(output:write(table.concat(parts)))
    assert(output:flush())
    if count >= limit then
        finished = true
        assert(output:close())
        assert(bus_file:close())
        manager.machine:exit()
    end
end
-- Install a non-mutating Z80 I/O pass-through tap. Observe only effects that
-- both engines can describe without guessing VDP internal palette/VRAM state.
-- MAME's current Lua address-space/tap API is version-dependent; fail if absent.
local cpu = assert(manager.machine.devices[':maincpu'], 'Missing :maincpu')
local io_space = assert(cpu.spaces and cpu.spaces['io'], 'Missing Z80 io address space')
local function port_write(offset, value, mask)
    if finished then return end
    local port = offset & 0xff
    local kind = nil
    if (port & 0xc1) == 0x81 then kind = 'VDP_CONTROL_WRITE'
    elseif (port & 0xc0) == 0x40 then kind = 'PSG_WRITE' end
    if not kind then return end
    bus_count = bus_count + 1
    if bus_count > 200000 then error('Bounded MAME bus capture exceeded') end
    local pc = state_number(cpu, 'PC') or state_number(cpu, 'CURPC') or 0
    assert(bus_file:write(string.format('{"type":"bus","ordinal":%d,"kind":"%s","address":%d,"value":%d,"pc":%d}\n',
        bus_count, kind, port, value & 0xff, pc & 0xffff)))
end
recompdev_bus_tap = io_space:install_write_tap(0, io_space.address_mask, 'recompdev-io-writes', port_write)
-- Keep a global reference to the subscription; no video callback guesses.
recompdev_frame_subscription = emu.add_machine_frame_notifier(capture)
