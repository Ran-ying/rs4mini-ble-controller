"""Application facade by default; the device module can load without motion."""
from importlib import import_module

_exports = {
    "RS4Mini": ("controller", "RS4Mini"), "RS4MiniError": ("errors", "RS4MiniError"),
    "velocity_frame": ("protocol", "velocity_frame"), "stop_frame": ("protocol", "stop_frame"),
    "recenter_frame": ("protocol", "recenter_frame"), "DumlStreamDecoder": ("telemetry", "DumlStreamDecoder"),
    "parse_duml_frame": ("telemetry", "parse_duml_frame"), "decode_gimbal_telemetry": ("telemetry", "decode_gimbal_telemetry"),
    "orientation_from_components": ("orientation", "orientation_from_components"),
}
__all__ = list(_exports)

def __getattr__(name):
    if name not in _exports:
        raise AttributeError(name)
    module, attribute = _exports[name]
    value = getattr(import_module("." + module, __name__), attribute)
    globals()[name] = value
    return value
