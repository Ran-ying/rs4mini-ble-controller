#import "RSMotionCore.h"
#include <math.h>
static BOOL Numeric(id value) { return [value isKindOfClass:NSNumber.class] && CFGetTypeID((__bridge CFTypeRef)value) != CFBooleanGetTypeID() && isfinite([value doubleValue]); }
NSDictionary *RSOrientation(NSArray *components, NSString *order, BOOL conjugate) {
    if (![components isKindOfClass:NSArray.class] || components.count != 4 || ![@[@"wxyz", @"xyzw"] containsObject:order]) return nil;
    double values[4], norm = 0;
    for (NSUInteger i = 0; i < 4; i++) { if (!Numeric(components[i])) return nil; values[i] = [components[i] doubleValue]; norm = hypot(norm, values[i]); }
    if (!isfinite(norm) || norm < 1e-12) return nil;
    double w = values[[order isEqualToString:@"wxyz"] ? 0 : 3] / norm;
    double x = values[[order isEqualToString:@"wxyz"] ? 1 : 0] / norm, y = values[[order isEqualToString:@"wxyz"] ? 2 : 1] / norm, z = values[[order isEqualToString:@"wxyz"] ? 3 : 2] / norm;
    if (conjugate) { x = -x; y = -y; z = -z; }
    double toDeg = 180 / M_PI;
    return @{@"quaternion": @{@"w": @(w), @"x": @(x), @"y": @(y), @"z": @(z)}, @"inputNorm": @(norm),
        @"euler": @{@"roll": @(atan2(2 * (w*x + y*z), 1 - 2*(x*x+y*y)) * toDeg), @"pitch": @(asin(fmax(-1,fmin(1,2*(w*y-z*x)))) * toDeg), @"yaw": @(atan2(2*(w*z+x*y),1-2*(y*y+z*z)) * toDeg)},
        @"componentOrder": order, @"conjugate": @(conjugate), @"convention": @"right-handed-intrinsic-ZYX", @"deviceConventionVerified": @NO};
}
@implementation RSPositionLoop {
    NSDictionary *_targets, *_current, *_velocity;
    NSTimeInterval _started, _feedbackAt;
    BOOL _active;
}
- (BOOL)active { return _active; }
- (NSDictionary *)velocity { return _velocity ?: @{@"pan": @0, @"tilt": @0, @"roll": @0}; }
- (NSDictionary *)current { return _current; }
- (BOOL)begin:(NSDictionary *)targets at:(NSTimeInterval)now error:(NSError **)error {
    BOOL valid = targets.count > 0 && !_active;
    for (NSString *key in targets) {
        id value = targets[key];
        if (![@[@"pan", @"tilt", @"roll"] containsObject:key] || ![value isKindOfClass:NSNumber.class] || !isfinite([value doubleValue]) || fabs([value doubleValue]) > 180) valid = NO;
    }
    if (!valid) { if (error) *error = [NSError errorWithDomain:@"RS4Mini" code:1 userInfo:@{NSLocalizedDescriptionKey: @"目标角度无效或定位已在运行"}]; return NO; }
    _targets = [targets copy]; _started = now; _feedbackAt = now; _current = nil; _velocity = nil; _active = YES;
    return YES;
}
- (void)feedback:(NSDictionary *)joints at:(NSTimeInterval)now {
    if (!_active) return;
    for (NSString *axis in @[@"pitch", @"roll", @"yaw"]) if (![joints[axis] isKindOfClass:NSNumber.class] || !isfinite([joints[axis] doubleValue])) return;
    _current = [joints copy]; _feedbackAt = now;
}
- (NSString *)step:(NSTimeInterval)now {
    if (!_active) return @"idle";
    if (now - _started >= 30) { [self cancel]; return @"timeout"; }
    if (now - _feedbackAt >= 3) { [self cancel]; return @"telemetryTimeout"; }
    if (!_current) return @"waiting";
    NSMutableDictionary *velocity = [NSMutableDictionary dictionary];
    NSDictionary *mapping = @{@"pan": @"yaw", @"tilt": @"pitch", @"roll": @"roll"};
    BOOL arrived = YES;
    for (NSString *axis in @[@"pan", @"tilt", @"roll"]) {
        double error = _targets[axis] ? [_targets[axis] doubleValue] - [_current[mapping[axis]] doubleValue] : 0;
        if ([axis isEqualToString:@"pan"]) error = fmod(error + 540, 360) - 180;
        double speed = 0;
        if (fabs(error) > 1) { arrived = NO; speed = copysign(fmin(0.18, fmax(0.05, fabs(error) * 0.02)), error); }
        velocity[axis] = @([axis isEqualToString:@"tilt"] ? -speed : speed);
    }
    _velocity = velocity;
    if (arrived) { _active = NO; return @"arrived"; }
    return @"moving";
}
- (void)cancel { _active = NO; _velocity = nil; }
@end

@implementation RSTrajectoryLoop {
    NSArray *_points;
    NSString *_interpolation;
    NSDictionary *_velocity;
    NSTimeInterval _started, _lastStep;
    BOOL _active;
}
- (BOOL)active { return _active; }
- (NSDictionary *)velocity { return _velocity ?: @{@"pan": @0, @"tilt": @0, @"roll": @0}; }
- (BOOL)begin:(NSArray *)keyframes interpolation:(NSString *)interpolation at:(NSTimeInterval)now error:(NSError **)error {
    BOOL valid = !_active && [keyframes isKindOfClass:NSArray.class] && keyframes.count >= 2 && isfinite(now) &&
        [@[@"linear", @"smoothstep", @"step"] containsObject:interpolation];
    NSMutableArray *points = [NSMutableArray array]; double previous = -1;
    if (valid) for (id point in keyframes) {
        if (![point isKindOfClass:NSDictionary.class]) { valid = NO; break; }
        id stamp = point[@"timeMs"];
        if (![stamp isKindOfClass:NSNumber.class] || CFGetTypeID((__bridge CFTypeRef)stamp) == CFBooleanGetTypeID() ||
            !isfinite([stamp doubleValue]) || [stamp doubleValue] <= previous || [stamp doubleValue] > 2147483647 ||
            (!points.count && [stamp doubleValue] != 0)) { valid = NO; break; }
        NSMutableDictionary *copy = [NSMutableDictionary dictionary]; copy[@"timeMs"] = @([stamp doubleValue]); previous = [stamp doubleValue];
        for (NSString *key in point) if (![@[@"timeMs", @"pan", @"tilt", @"roll"] containsObject:key]) valid = NO;
        for (NSString *axis in @[@"pan", @"tilt", @"roll"]) {
            id value = point[axis] ?: @0;
            if (![value isKindOfClass:NSNumber.class] || CFGetTypeID((__bridge CFTypeRef)value) == CFBooleanGetTypeID() ||
                !isfinite([value doubleValue]) || fabs([value doubleValue]) > 1) { valid = NO; break; }
            copy[axis] = @([value doubleValue]);
        }
        [points addObject:[copy copy]];
    }
    if (!valid) { if (error) *error = [NSError errorWithDomain:@"RS4Mini" code:2 userInfo:@{NSLocalizedDescriptionKey: @"轨迹需至少两个严格递增、从零开始的 timeMs 关键帧，各轴值为 -1 到 1"}]; return NO; }
    _points = [points copy]; _interpolation = [interpolation copy]; _started = _lastStep = now; _velocity = nil; _active = YES; return YES;
}
- (NSString *)step:(NSTimeInterval)now {
    if (!_active) return @"idle";
    if (!isfinite(now) || now - _lastStep > .5 || now < _started) { [self cancel]; return @"overrun"; }
    _lastStep = now; double elapsed = (now - _started) * 1000;
    if (elapsed >= [_points.lastObject[@"timeMs"] doubleValue]) { [self cancel]; return @"done"; }
    NSUInteger index = 0;
    while (index < _points.count - 2 && [_points[index + 1][@"timeMs"] doubleValue] <= elapsed) index++;
    NSDictionary *a = _points[index], *b = _points[index + 1];
    double ratio = fmax(0, fmin(1, (elapsed - [a[@"timeMs"] doubleValue]) / ([b[@"timeMs"] doubleValue] - [a[@"timeMs"] doubleValue])));
    if ([_interpolation isEqualToString:@"step"]) ratio = 0;
    else if ([_interpolation isEqualToString:@"smoothstep"]) ratio = ratio * ratio * (3 - 2 * ratio);
    NSMutableDictionary *values = [NSMutableDictionary dictionary];
    for (NSString *axis in @[@"pan", @"tilt", @"roll"]) values[axis] = @([a[axis] doubleValue] + ([b[axis] doubleValue] - [a[axis] doubleValue]) * ratio);
    _velocity = [values copy]; return @"moving";
}
- (void)cancel { _active = NO; _velocity = nil; }
@end
