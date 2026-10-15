"""Right-handed intrinsic Z-Y-X quaternion math; no implied device convention."""
import math


def orientation_from_components(components, *, component_order, conjugate=False):
    if component_order not in ('wxyz', 'xyzw') or not isinstance(conjugate, bool):
        raise ValueError('explicit wxyz or xyzw order and boolean conjugate required')
    if not isinstance(components, (list, tuple)) or len(components) != 4 or not all(type(value) in (int, float) and math.isfinite(value) for value in components):
        raise ValueError('four finite quaternion components required')
    norm = math.hypot(*components)
    if not math.isfinite(norm) or norm < 1e-12:
        raise ValueError('quaternion norm is zero')
    ordered = components if component_order == 'wxyz' else [components[3]] + list(components[:3])
    w, x, y, z = [value / norm for value in ordered]
    if conjugate:
        x, y, z = -x, -y, -z
    euler = dict(roll=math.degrees(math.atan2(2 * (w * x + y * z), 1 - 2 * (x * x + y * y))),
                 pitch=math.degrees(math.asin(max(-1, min(1, 2 * (w * y - z * x))))),
                 yaw=math.degrees(math.atan2(2 * (w * z + x * y), 1 - 2 * (y * y + z * z))))
    return dict(quaternion=dict(w=w, x=x, y=y, z=z), inputNorm=norm, euler=euler,
                componentOrder=component_order, conjugate=conjugate, convention='right-handed-intrinsic-ZYX', deviceConventionVerified=False)
