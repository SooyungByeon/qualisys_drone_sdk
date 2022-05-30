import pynput
from time import sleep, time

from qfly import Pose, QualisysCrazyflie, World, parallel, utils

import numpy as np

# SETTINGS
# QTM rigid body names
cf_body_names = [
    'E7E7E7E701',
    'E7E7E7E702',
    # 'E7E7E7E703',
]
# Crazyflie addresses
cf_uris = [
    'radio://0/80/1M/E7E7E7E701',
    'radio://0/80/1M/E7E7E7E702',
    # 'radio://0/80/1M/E7E7E7E703',
]

# Crazyflie addresses
cf_marker_ids = [
    [11, 12, 13, 14],
    [21, 22, 23, 24],
    # [31, 32, 33, 34],
]

# Watch key presses with a global variable
last_key_pressed = None


# Set up keyboard callback
def on_press(key):
    """React to keyboard."""
    global last_key_pressed
    last_key_pressed = key


# Listen to the keyboard
listener = pynput.keyboard.Listener(on_press=on_press)
listener.start()


# Set up world - the World object comes with sane defaults
world = World()

# Stack up context managers

_qcfs = [QualisysCrazyflie(cf_body_name,
                           cf_uri,
                           world,
                           marker_ids=cf_marker_id)
         for cf_body_name, cf_uri, cf_marker_id
         in zip(cf_body_names, cf_uris, cf_marker_ids)]

with parallel(*_qcfs) as qcfs:

    # Let there be time
    t = time()
    dt = 0

    print("Beginning maneuvers...")

    # MAIN LOOP WITH SAFETY CHECK
    while(dt < 32):

        # Safety check
        if not all(qcf.is_safe() for qcf in qcfs):
            break

        # Land with Esc
        if last_key_pressed == pynput.keyboard.Key.esc:
            break

        # Mind the clock
        dt = time() - t

        for idx, qcf in enumerate(qcfs):

            if dt < 5:
                print(f'[t={int(dt)}] Liftoff...')
                qcf.ascend(step=10.0)

            # Take off and hover in the center of safe airspace
            elif dt < 8:
                print(f'[t={int(dt)}] Maneuvering - Center...')
                # Set target
                x = np.interp(idx,
                              [0,
                               len(qcfs) - 1],
                              [world.origin.x - world.expanse / 2,
                                  world.origin.x + world.expanse / 2])
                target = Pose(x,
                              world.origin.y,
                              world.expanse)
                # Engage
                qcf.safe_position_setpoint(target)

                sleep(0.1)

            # Move out half of the safe airspace in the X direction and circle around Z axis
            elif dt < 10:
                print(f'[t={int(dt)}] Maneuvering - Circle around Z...')
                # Set target
                phi = (dt * 90) % 360  # Calculate angle based on time
                # Offset angle based on array
                phi = phi + 360 * (idx / len(qcfs))
                _x, _y = utils.pol2cart(0.5, phi)
                target = Pose(world.origin.x + _x,
                              world.origin.y + _y,
                              world.expanse)
                print("TARGET ANGLE FOR " + str(idx) + " => " + str(phi))
                # Engage
                qcf.safe_position_setpoint(target)
                sleep(0.1)

            # Back to center
            elif dt < 12:
                print(f'[t={int(dt)}] Maneuvering - Center...')
                # Set target
                x = np.interp(idx,
                              [0,
                               len(qcfs) - 1],
                              [world.origin.x - world.expanse / 2,
                                  world.origin.x + world.expanse / 2])
                target = Pose(x,
                              world.origin.y,
                              world.expanse)
                # Engage
                qcf.safe_position_setpoint(target)
                sleep(0.1)

            # # Move out half of the safe airspace in the Z direction and circle around Y axis
            elif dt < 20:
                print(f'[t={int(dt)}] Maneuvering - Circle around Y...')
                # Set target
                phi = (dt * 90) % 360  # Calculate angle based on time
                # Offset angle based on array
                phi = phi + 360 * (idx / len(qcfs))
                _x, _z = utils.pol2cart(0.5, phi)
                target = Pose(world.origin.x + _x,
                              world.origin.y,
                              world.expanse + _z)
                print("TARGET ANGLE FOR " + str(idx) + " => " + str(phi))
                # Engage
                qcf.safe_position_setpoint(target)
                sleep(0.1)

            # Back to center
            elif dt < 22:
                print(f'[t={int(dt)}] Maneuvering - Center...')
                # Set target
                x = np.interp(idx,
                              [0,
                               len(qcfs) - 1],
                              [world.origin.x - world.expanse / 2,
                                  world.origin.x + world.expanse / 2])
                target = Pose(x,
                              world.origin.y,
                              world.expanse)
                # Engage
                qcf.safe_position_setpoint(target)
                sleep(0.1)

            # # Move out half of the safe airspace in the Z direction and circle around X axis
            elif dt < 30:
                print(f'[t={int(dt)}] Maneuvering - Circle around x...')
                # Set target
                phi = (dt * 90) % 360  # Calculate angle based on time
                # Offset angle based on array
                phi = phi + 360 * (idx / len(qcfs))
                _y, _z = utils.pol2cart(0.5, phi)
                target = Pose(world.origin.x,
                              world.origin.y + _y,
                              world.expanse + _z)
                print("TARGET ANGLE FOR " + str(idx) + " => " + str(phi))
                # Engage
                qcf.safe_position_setpoint(target)
                sleep(0.1)

            # # Back to center
            elif dt < 32:
                print(f'[t={int(dt)}] Maneuvering - Center...')
                # Set target
                x = np.interp(idx,
                              [0,
                               len(qcfs) - 1],
                              [world.origin.x - world.expanse / 2,
                                  world.origin.x + world.expanse / 2])
                target = Pose(x,
                              world.origin.y,
                              world.expanse)
                # Engage
                qcf.safe_position_setpoint(target)
                sleep(0.1)

    # Land calmly
    while(any(qcf.pose.z > 0.1 for qcf in qcfs)):
        for qcf in qcfs:
            qcf.descend()