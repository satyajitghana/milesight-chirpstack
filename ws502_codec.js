/**
 * =====================================================================
 *
 * Payload Decoder
 *
 * =====================================================================
 */

var RAW_VALUE = 0x00;

// Chirpstack v4
function decodeUplink(input) {
    var decoded = milesightDeviceDecode(input.bytes);
    return { data: decoded };
}

// Chirpstack v3
function Decode(fPort, bytes) {
    return milesightDeviceDecode(bytes);
}

// The Things Network
function Decoder(bytes, port) {
    return milesightDeviceDecode(bytes);
}

function milesightDeviceDecode(bytes) {
    var decoded = {};

    for (var i = 0; i < bytes.length;) {
        var channel_id = bytes[i++];
        var channel_type = bytes[i++];

        // IPSO VERSION
        if (channel_id === 0xff && channel_type === 0x01) {
            decoded.ipso_version = readProtocolVersion(bytes[i]);
            i += 1;
        }
        // HARDWARE VERSION
        else if (channel_id === 0xff && channel_type === 0x09) {
            decoded.hardware_version = readHardwareVersion(bytes.slice(i, i + 2));
            i += 2;
        }
        // FIRMWARE VERSION
        else if (channel_id === 0xff && channel_type === 0x0a) {
            decoded.firmware_version = readFirmwareVersion(bytes.slice(i, i + 2));
            i += 2;
        }
        // TSL VERSION
        else if (channel_id === 0xff && channel_type === 0xff) {
            decoded.tsl_version = readTslVersion(bytes.slice(i, i + 2));
            i += 2;
        }
        // SERIAL NUMBER
        else if (channel_id === 0xff && channel_type === 0x16) {
            decoded.sn = readSerialNumber(bytes.slice(i, i + 8));
            i += 8;
        }
        // LORAWAN CLASS TYPE
        else if (channel_id === 0xff && channel_type === 0x0f) {
            decoded.lorawan_class = readLoRaWANClass(bytes[i]);
            i += 1;
        }
        // RESET EVENT
        else if (channel_id === 0xff && channel_type === 0xfe) {
            decoded.reset_event = readResetEvent(bytes[i]);
            i += 1;
        }
        // DEVICE STATUS
        else if (channel_id === 0xff && channel_type === 0x0b) {
            decoded.device_status = readOnOffStatus(bytes[i]);
            i += 1;
        }
        // VOLTAGE
        else if (channel_id === 0x03 && channel_type === 0x74) {
            decoded.voltage = readUInt16LE(bytes.slice(i, i + 2)) / 10;
            i += 2;
        }
        // ACTIVE POWER
        else if (channel_id === 0x04 && channel_type === 0x80) {
            decoded.active_power = readUInt32LE(bytes.slice(i, i + 4));
            i += 4;
        }
        // POWER FACTOR
        else if (channel_id === 0x05 && channel_type === 0x81) {
            decoded.power_factor = readUInt8(bytes[i]);
            i += 1;
        }
        // POWER CONSUMPTION
        else if (channel_id === 0x06 && channel_type == 0x83) {
            decoded.power_consumption = readUInt32LE(bytes.slice(i, i + 4));
            i += 4;
        }
        // CURRENT
        else if (channel_id === 0x07 && channel_type == 0xc9) {
            decoded.current = readUInt16LE(bytes.slice(i, i + 2));
            i += 2;
        }
        // SWITCH STATE
        else if (channel_id === 0x08 && channel_type === 0x29) {
            var value = bytes[i];
            decoded.switch_1 = readOnOffStatus((value >>> 0) & 0x01);
            decoded.switch_1_change = readYesNoStatus((value >>> 4) & 0x01);
            decoded.switch_2 = readOnOffStatus((value >>> 1) & 0x01);
            decoded.switch_2_change = readYesNoStatus((value >>> 5) & 0x01);
            i += 1;
        }
        // DOWNLINK RESPONSE
        else if (channel_id === 0xfe || channel_id === 0xff) {
            var result = handle_downlink_response(channel_type, bytes, i);
            decoded = Object.assign(decoded, result.data);
            i = result.offset;
        } else {
            break;
        }
    }

    return decoded;
}

function handle_downlink_response(channel_type, bytes, offset) {
    var decoded = {};

    switch (channel_type) {
        case 0x03:
            decoded.report_interval = readUInt16LE(bytes.slice(offset, offset + 2));
            offset += 2;
            break;
        case 0x10:
            decoded.reboot = readYesNoStatus(1);
            offset += 1;
            break;
        case 0x22:
            decoded.delay_task = {};
            decoded.delay_task.frame_count = readUInt8(bytes[offset]);
            decoded.delay_task.delay_time = readUInt16LE(bytes.slice(offset + 1, offset + 3));
            var data = readUInt8(bytes[offset + 3]);
            var switch_bit_offset = { switch_1: 0, switch_2: 1, switch_3: 2 };
            for (var key in switch_bit_offset) {
                if ((data >>> (switch_bit_offset[key] + 4)) & 0x01) {
                    decoded.delay_task[key] = readOnOffStatus((data >> switch_bit_offset[key]) & 0x01);
                }
            }
            offset += 4;
            break;
        case 0x23:
            decoded.cancel_delay_task = readUInt8(bytes[offset]);
            offset += 2;
            break;
        case 0x25:
            var data = readUInt16LE(bytes.slice(offset, offset + 2));
            decoded.child_lock_config = {};
            decoded.child_lock_config.enable = readEnableStatus((data >>> 15) & 0x01);
            decoded.child_lock_config.lock_time = data & 0x7fff;
            offset += 2;
            break;
        case 0x26:
            decoded.power_consumption_enable = readEnableStatus(bytes[offset]);
            offset += 1;
            break;
        case 0x27:
            decoded.clear_power_consumption = readYesNoStatus(1);
            offset += 1;
            break;
        case 0x28:
            decoded.report_status = readYesNoStatus(1);
            offset += 1;
            break;
        case 0x2c:
            decoded.report_attribute = readYesNoStatus(1);
            offset += 1;
            break;
        case 0x2f:
            decoded.led_mode = readLedMode(bytes[offset]);
            offset += 1;
            break;
        case 0x5e:
            decoded.reset_button_enable = readEnableStatus(bytes[offset]);
            offset += 1;
            break;
        default:
            throw new Error("unknown downlink response");
    }

    return { data: decoded, offset: offset };
}

function readProtocolVersion(bytes) {
    var major = (bytes & 0xf0) >> 4;
    var minor = bytes & 0x0f;
    return "v" + major + "." + minor;
}

function readHardwareVersion(bytes) {
    var major = bytes[0] & 0xff;
    var minor = (bytes[1] & 0xff) >> 4;
    return "v" + major + "." + minor;
}

function readFirmwareVersion(bytes) {
    var major = bytes[0] & 0xff;
    var minor = bytes[1] & 0xff;
    return "v" + major + "." + minor;
}

function readTslVersion(bytes) {
    var major = bytes[0] & 0xff;
    var minor = bytes[1] & 0xff;
    return "v" + major + "." + minor;
}

function readSerialNumber(bytes) {
    var temp = [];
    for (var idx = 0; idx < bytes.length; idx++) {
        temp.push(("0" + (bytes[idx] & 0xff).toString(16)).slice(-2));
    }
    return temp.join("");
}

function readLoRaWANClass(type) {
    var class_map = { 0: "Class A", 1: "Class B", 2: "Class C", 3: "Class CtoB" };
    return getDecoderValue(class_map, type);
}

function readResetEvent(status) {
    var status_map = { 0: "normal", 1: "reset" };
    return getDecoderValue(status_map, status);
}

function readOnOffStatus(status) {
    var status_map = { 0: "off", 1: "on" };
    return getDecoderValue(status_map, status);
}

function readYesNoStatus(status) {
    var status_map = { 0: "no", 1: "yes" };
    return getDecoderValue(status_map, status);
}

function readRuleConfig(bytes) {
    var offset = 0;
    var rule_config = {};
    rule_config.rule_id = readUInt8(bytes[offset]);
    var rule_type_value = readUInt8(bytes[offset + 1]);
    rule_config.rule_type = readRuleType(rule_type_value);
    if (rule_type_value !== 0) {
        var day_bit_offset = { monday: 0, tuesday: 1, wednesday: 2, thursday: 3, friday: 4, saturday: 5, sunday: 6 };
        rule_config.condition = {};
        var day = readUInt8(bytes[offset + 2]);
        for (var key in day_bit_offset) {
            rule_config.condition[key] = readEnableStatus((day >> day_bit_offset[key]) & 0x01);
        }
        rule_config.condition.hour = readUInt8(bytes[offset + 3]);
        rule_config.condition.minute = readUInt8(bytes[offset + 4]);
        var switch_bit_offset = { switch_1: 0, switch_2: 2, switch_3: 4 };
        rule_config.action = {};
        var switch_raw_data = readUInt8(bytes[offset + 5]);
        for (var key in switch_bit_offset) {
            rule_config.action[key] = readSwitchStatus((switch_raw_data >> switch_bit_offset[key]) & 0x03);
        }
        rule_config.action.child_lock = readChildLockStatus(bytes[offset + 6]);
    }
    offset += 6;
    return rule_config;
}

function readRuleType(type) {
    var rule_type_map = { 0: "none", 1: "enable", 2: "disable" };
    return getDecoderValue(rule_type_map, type);
}

function readSwitchStatus(status) {
    var switch_status_map = { 0: "keep", 1: "on", 2: "off" };
    return getDecoderValue(switch_status_map, status);
}

function readRuleConfigResult(result) {
    var rule_config_result_map = { 0: "success", 2: "failed, out of range", 17: "success, conflict with rule_id=1", 18: "success, conflict with rule_id=2", 19: "success, conflict with rule_id=3", 20: "success, conflict with rule_id=4", 21: "success, conflict with rule_id=5", 22: "success, conflict with rule_id=6", 23: "success, conflict with rule_id=7", 24: "success, conflict with rule_id=8", 49: "failed, conflict with rule_id=1", 50: "failed, conflict with rule_id=2", 51: "failed, conflict with rule_id=3", 52: "failed, conflict with rule_id=4", 53: "failed, conflict with rule_id=5", 54: "failed, conflict with rule_id=6", 55: "failed, conflict with rule_id=7", 56: "failed, conflict with rule_id=8", 81: "failed,rule config empty" };
    return getDecoderValue(rule_config_result_map, result);
}

function readChildLockStatus(status) {
    var child_lock_status_map = { 0: "keep", 1: "enable", 2: "disable" };
    return getDecoderValue(child_lock_status_map, status);
}

function readLedMode(bytes) {
    var led_mode_map = { 0: "off", 1: "on_inverted", 2: "on_synced" };
    return getDecoderValue(led_mode_map, bytes);
}

function readEnableStatus(bytes) {
    var enable_map = { 0: "disable", 1: "enable" };
    return getDecoderValue(enable_map, bytes);
}

function readTimeZone(timezone) {
    var timezone_map = { "-720": "UTC-12", "-660": "UTC-11", "-600": "UTC-10", "-570": "UTC-9:30", "-540": "UTC-9", "-480": "UTC-8", "-420": "UTC-7", "-360": "UTC-6", "-300": "UTC-5", "-240": "UTC-4", "-210": "UTC-3:30", "-180": "UTC-3", "-120": "UTC-2", "-60": "UTC-1", 0: "UTC", 60: "UTC+1", 120: "UTC+2", 180: "UTC+3", 210: "UTC+3:30", 240: "UTC+4", 270: "UTC+4:30", 300: "UTC+5", 330: "UTC+5:30", 345: "UTC+5:45", 360: "UTC+6", 390: "UTC+6:30", 420: "UTC+7", 480: "UTC+8", 540: "UTC+9", 570: "UTC+9:30", 600: "UTC+10", 630: "UTC+10:30", 660: "UTC+11", 720: "UTC+12", 765: "UTC+12:45", 780: "UTC+13", 840: "UTC+14" };
    return getDecoderValue(timezone_map, timezone);
}

function readUInt8(bytes) {
    return bytes & 0xff;
}

function readInt8(bytes) {
    var ref = readUInt8(bytes);
    return ref > 0x7f ? ref - 0x100 : ref;
}

function readUInt16LE(bytes) {
    var value = (bytes[1] << 8) + bytes[0];
    return value & 0xffff;
}

function readInt16LE(bytes) {
    var ref = readUInt16LE(bytes);
    return ref > 0x7fff ? ref - 0x10000 : ref;
}

function readUInt32LE(bytes) {
    var value = (bytes[3] << 24) + (bytes[2] << 16) + (bytes[1] << 8) + bytes[0];
    return (value & 0xffffffff) >>> 0;
}

function readInt32LE(bytes) {
    var ref = readUInt32LE(bytes);
    return ref > 0x7fffffff ? ref - 0x100000000 : ref;
}

function getDecoderValue(map, key) {
    if (RAW_VALUE) {
        return key;
    }
    if (Object.prototype.hasOwnProperty.call(map, key)) {
        return map[key];
    }
    return "unknown";
}


if (!Object.assign) {
    Object.defineProperty(Object, "assign", {
        enumerable: false,
        configurable: true,
        writable: true,
        value: function (target) {
            "use strict";
            if (target == null) {
                throw new TypeError("Cannot convert first argument to object");
            }

            var to = Object(target);
            for (var i = 1; i < arguments.length; i++) {
                var nextSource = arguments[i];
                if (nextSource == null) {
                    continue;
                }
                nextSource = Object(nextSource);

                var keysArray = Object.keys(Object(nextSource));
                for (var nextIndex = 0, len = keysArray.length; nextIndex < len; nextIndex++) {
                    var nextKey = keysArray[nextIndex];
                    var desc = Object.getOwnPropertyDescriptor(nextSource, nextKey);
                    if (desc !== undefined && desc.enumerable) {
                        if (Array.isArray(to[nextKey]) && Array.isArray(nextSource[nextKey])) {
                            to[nextKey] = to[nextKey].concat(nextSource[nextKey]);
                        } else {
                            to[nextKey] = nextSource[nextKey];
                        }
                    }
                }
            }
            return to;
        },
    });
}


/**
 * =====================================================================
 *
 * Payload Encoder
 *
 * =====================================================================
 */

// Chirpstack v4
function encodeDownlink(input) {
    var encoded = milesightDeviceEncode(input.data);
    return { bytes: encoded };
}

// Chirpstack v3
function Encode(fPort, obj) {
    return milesightDeviceEncode(obj);
}

// The Things Network
function Encoder(obj, port) {
    return milesightDeviceEncode(obj);
}

function milesightDeviceEncode(payload) {
    var encoded = [];

    if ("reboot" in payload) {
        encoded = encoded.concat(reboot(payload.reboot));
    }
    if ("report_interval" in payload) {
        encoded = encoded.concat(setReportInterval(payload.report_interval));
    }
    if ("report_status" in payload) {
        encoded = encoded.concat(reportStatus(payload.report_status));
    }
    if ("report_attribute" in payload) {
        encoded = encoded.concat(reportAttribute(payload.report_attribute));
    }
    if ("switch_1" in payload) {
        encoded = encoded.concat(updateSwitch(1, payload.switch_1));
    }
    if ("switch_2" in payload) {
        encoded = encoded.concat(updateSwitch(2, payload.switch_2));
    }
    if ("delay_task" in payload) {
        encoded = encoded.concat(setDelayTask(payload.delay_task));
    }
    if ("cancel_delay_task" in payload) {
        encoded = encoded.concat(cancelDelayTask(payload.cancel_delay_task));
    }
    if ("led_mode" in payload) {
        encoded = encoded.concat(setLedMode(payload.led_mode));
    }
    if ("child_lock_config" in payload) {
        encoded = encoded.concat(setChildLockConfig(payload.child_lock_config));
    }
    if ("reset_button_enable" in payload) {
        encoded = encoded.concat(setResetButtonEnable(payload.reset_button_enable));
    }
    if ("power_consumption_enable" in payload) {
        encoded = encoded.concat(setPowerConsumptionEnable(payload.power_consumption_enable));
    }
    if ("clear_power_consumption" in payload) {
        encoded = encoded.concat(clearPowerConsumption(payload.clear_power_consumption));
    }

    return encoded;
}

function reboot(reboot) {
    var yes_no_map = { 0: "no", 1: "yes" };
    var yes_no_values = getEncoderValues(yes_no_map);
    if (yes_no_values.indexOf(reboot) === -1) {
        throw new Error("reboot must be one of: " + yes_no_values.join(", "));
    }

    if (getEncoderValue(yes_no_map, reboot) === 0) {
        return [];
    }
    return [0xff, 0x10, 0xff];
}

function setReportInterval(report_interval) {
    if (typeof report_interval !== "number") {
        throw new Error("report_interval must be a number");
    }
    if (report_interval < 60 || report_interval > 64800) {
        throw new Error("report_interval must be in the range of [60, 64800]");
    }

    var buffer = new Buffer(4);
    buffer.writeUInt8(0xff);
    buffer.writeUInt8(0x03);
    buffer.writeUInt16LE(report_interval);
    return buffer.toBytes();
}

function reportStatus(report_status) {
    var yes_no_map = { 0: "no", 1: "yes" };
    var yes_no_values = getEncoderValues(yes_no_map);
    if (yes_no_values.indexOf(report_status) === -1) {
        throw new Error("report_status must be one of " + yes_no_values.join(", "));
    }

    if (getEncoderValue(yes_no_map, report_status) === 0) {
        return [];
    }
    return [0xff, 0x28, 0xff];
}

function reportAttribute(report_attribute) {
    var yes_no_map = { 0: "no", 1: "yes" };
    var yes_no_values = getEncoderValues(yes_no_map);
    if (yes_no_values.indexOf(report_attribute) === -1) {
        throw new Error("report_attribute must be one of: " + yes_no_values.join(", "));
    }

    if (getEncoderValue(yes_no_map, report_attribute) === 0) {
        return [];
    }
    return [0xff, 0x2c, 0xff];
}

function updateSwitch(id, state) {
    var on_off_map = { 0: "off", 1: "on" };
    var on_off_values = getEncoderValues(on_off_map);
    if (on_off_values.indexOf(state) === -1) {
        throw new Error("switch_" + id + " must be one of: " + on_off_values.join(", "));
    }

    var on_off = on_off_values.indexOf(state);
    var mask = 0x01 << (id - 1);
    var ctrl = on_off << (id - 1);
    var data = (mask << 4) + ctrl;
    var buffer = new Buffer(3);
    buffer.writeUInt8(0x08);
    buffer.writeUInt8(data);
    buffer.writeUInt8(0xff);
    return buffer.toBytes();
}

function setDelayTask(delay_task) {
    var frame_count = delay_task.frame_count;
    var delay_time = delay_task.delay_time;

    var on_off_map = { 0: "off", 1: "on" };
    var on_off_values = getEncoderValues(on_off_map);
    if (frame_count < 0 || frame_count > 255) {
        throw new Error("delay_task.frame_count must be in the range of [0, 255]");
    }
    if (typeof delay_time !== "number") {
        throw new Error("delay_task.delay_time must be a number");
    }
    if (delay_time < 0 || delay_time > 65535) {
        throw new Error("delay_task.delay_time must be in the range of [0, 65535]");
    }

    var data = 0x00;
    var switch_bit_offset = { switch_1: 0, switch_2: 1 };
    for (var key in switch_bit_offset) {
        if (key in delay_task) {
            if (on_off_values.indexOf(delay_task[key]) === -1) {
                throw new Error("delay_task." + key + " must be one of: " + on_off_values.join(", "));
            }
            data |= 1 << (switch_bit_offset[key] + 4);
            data |= getEncoderValue(on_off_map, delay_task[key]) << switch_bit_offset[key];
        }
    }

    var buffer = new Buffer(6);
    buffer.writeUInt8(0xff);
    buffer.writeUInt8(0x22);
    buffer.writeUInt8(frame_count);
    buffer.writeUInt16LE(delay_time);
    buffer.writeUInt8(data);
    return buffer.toBytes();
}

function cancelDelayTask(cancel_delay_task) {
    if (typeof cancel_delay_task !== "number") {
        throw new Error("cancel_delay_task must be a number");
    }

    var buffer = new Buffer(4);
    buffer.writeUInt8(0xff);
    buffer.writeUInt8(0x23);
    buffer.writeUInt8(cancel_delay_task);
    buffer.writeUInt8(0x00);
    return buffer.toBytes();
}

function setLedMode(led_mode) {
    var led_mode_map = { 0: "off", 1: "on_inverted", 2: "on_synced" };
    var led_mode_values = getEncoderValues(led_mode_map);
    if (led_mode_values.indexOf(led_mode) === -1) {
        throw new Error("led_mode must be one of: " + led_mode_values.join(", "));
    }

    var buffer = new Buffer(3);
    buffer.writeUInt8(0xff);
    buffer.writeUInt8(0x2f);
    buffer.writeUInt8(getEncoderValue(led_mode_map, led_mode));
    return buffer.toBytes();
}

function setResetButtonEnable(reset_button_enable) {
    var enable_map = { 0: "disable", 1: "enable" };
    var enable_values = getEncoderValues(enable_map);
    if (enable_values.indexOf(reset_button_enable) === -1) {
        throw new Error("reset_button_enable must be one of: " + enable_values.join(", "));
    }

    var buffer = new Buffer(3);
    buffer.writeUInt8(0xff);
    buffer.writeUInt8(0x5e);
    buffer.writeUInt8(getEncoderValue(enable_map, reset_button_enable));
    return buffer.toBytes();
}

function setChildLockConfig(child_lock_config) {
    var enable = child_lock_config.enable;
    var lock_time = child_lock_config.lock_time;

    var enable_map = { 0: "disable", 1: "enable" };
    var enable_values = getEncoderValues(enable_map);
    if (enable_values.indexOf(enable) === -1) {
        throw new Error("child_lock_config.enable must be one of: " + enable_values.join(", "));
    }
    if (typeof lock_time !== "number") {
        throw new Error("child_lock_config.lock_time must be a number");
    }

    var data = 0x00;
    data |= getEncoderValue(enable_map, enable) << 15;
    data |= lock_time;
    var buffer = new Buffer(4);
    buffer.writeUInt8(0xff);
    buffer.writeUInt8(0x25);
    buffer.writeUInt16LE(data);
    return buffer.toBytes();
}

function setPowerConsumptionEnable(power_consumption_enable) {
    var enable_map = { 0: "disable", 1: "enable" };
    var enable_values = getEncoderValues(enable_map);
    if (enable_values.indexOf(power_consumption_enable) === -1) {
        throw new Error("power_consumption_enable must be one of: " + enable_values.join(", "));
    }

    var buffer = new Buffer(3);
    buffer.writeUInt8(0xff);
    buffer.writeUInt8(0x26);
    buffer.writeUInt8(getEncoderValue(enable_map, power_consumption_enable));
    return buffer.toBytes();
}

function clearPowerConsumption(clear_power_consumption) {
    var yes_no_map = { 0: "no", 1: "yes" };
    var yes_no_values = getEncoderValues(yes_no_map);
    if (yes_no_values.indexOf(clear_power_consumption) === -1) {
        throw new Error("clear_power_consumption must be one of: " + yes_no_values.join(", "));
    }

    if (getEncoderValue(yes_no_map, clear_power_consumption) === 0) {
        return [];
    }
    return [0xff, 0x27, 0xff];
}

function getEncoderValues(map) {
    var values = [];
    if (RAW_VALUE) {
        for (var key in map) {
            values.push(parseInt(key));
        }
    } else {
        for (var key in map) {
            values.push(map[key]);
        }
    }
    return values;
}

function getEncoderValue(map, value) {
    if (RAW_VALUE) return value;

    for (var key in map) {
        if (map[key] === value) {
            return parseInt(key);
        }
    }

    throw new Error("not match in " + JSON.stringify(map));
}

function Buffer(size) {
    this.buffer = new Array(size);
    this.offset = 0;

    for (var i = 0; i < size; i++) {
        this.buffer[i] = 0;
    }
}

Buffer.prototype._write = function (value, byteLength, isLittleEndian) {
    var offset = 0;
    for (var index = 0; index < byteLength; index++) {
        offset = isLittleEndian ? index << 3 : (byteLength - 1 - index) << 3;
        this.buffer[this.offset + index] = (value >> offset) & 0xff;
    }
};

Buffer.prototype.writeUInt8 = function (value) {
    this._write(value, 1, true);
    this.offset += 1;
};

Buffer.prototype.writeInt8 = function (value) {
    this._write(value < 0 ? value + 0x100 : value, 1, true);
    this.offset += 1;
};

Buffer.prototype.writeUInt16LE = function (value) {
    this._write(value, 2, true);
    this.offset += 2;
};

Buffer.prototype.writeInt16LE = function (value) {
    this._write(value < 0 ? value + 0x10000 : value, 2, true);
    this.offset += 2;
};

Buffer.prototype.writeUInt32LE = function (value) {
    this._write(value, 4, true);
    this.offset += 4;
};

Buffer.prototype.writeInt32LE = function (value) {
    this._write(value < 0 ? value + 0x100000000 : value, 4, true);
    this.offset += 4;
};

Buffer.prototype.toBytes = function () {
    return this.buffer;
};