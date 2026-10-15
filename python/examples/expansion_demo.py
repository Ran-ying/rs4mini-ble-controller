"""Explicit hardware demonstrations; no arguments prints help without Bluetooth."""
import argparse
import asyncio
from rs4mini_sdk import RS4Mini


async def run(options):
    gimbal = RS4Mini()
    try:
        if options.operation in ('home', 'waypoints'):
            print('Pan +3 degrees, then return; balance and unobstructed movement required.')
        elif options.operation == 'velocity':
            print('Pan <=5% drive over 2 seconds; this does not guarantee physical speed.')
        else:
            print('Feedback/query demo; exit sends neutral frames.')
        await gimbal.connect()
        if options.operation == 'query':
            gimbal.experimental.use_profile(options.profile)
            value = await gimbal.experimental.query(kind='version')
            print('Unverified research response:', value['payload'].hex())
            return
        start = await gimbal.get_joint_angles(fresh=True)
        print('Start joints:', {key: start[key] for key in ('pitch', 'roll', 'yaw')})
        target = (start['yaw'] + 3 + 180) % 360 - 180
        if options.operation == 'waypoints':
            print(await gimbal.move_through([dict(pan=target, holdMs=500), dict(pan=start['yaw'])]))
        elif options.operation == 'home':
            home = await gimbal.capture_home(fresh=True)
            await gimbal.move_to(pan=(home['pan'] + 3 + 180) % 360 - 180)
            print(await gimbal.move_home(axes=['pan']))
        elif options.operation == 'velocity':
            print(await gimbal.run_trajectory([dict(timeMs=0, pan=0), dict(timeMs=1000, pan=.05), dict(timeMs=2000, pan=0)], interpolation='smoothstep'))
    finally:
        await gimbal.close()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('operation', nargs='?', choices=['read', 'waypoints', 'home', 'velocity', 'query'])
    parser.add_argument('--profile', choices=['rs3', 'rs3mini'])
    args = parser.parse_args()
    if args.operation is None:
        parser.print_help()
    elif args.operation == 'query' and not args.profile:
        parser.error('query requires --profile rs3 or rs3mini')
    elif args.operation != 'query' and args.profile:
        parser.error('--profile is only used with query')
    else:
        asyncio.run(run(args))
