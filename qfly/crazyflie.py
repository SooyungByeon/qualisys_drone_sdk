import math
import time

from cflib.crazyflie.log import LogConfig
from cflib.crazyflie.syncLogger import SyncLogger

import cflib.crtp
from cflib.crazyflie import Crazyflie
from cflib.crazyflie.syncCrazyflie import SyncCrazyflie

import qfly
from qfly.utils import sqrt


class QualisysCrazyflie():
    """Wrapper for Crazyflie drone to fly with Qualisys motion capture systems"""

    def __init__(self,
                 cf_body_name,
                 cf_uri,
                 world,
                 max_tracking_loss=200,
                 max_vel=1.0,
                 marker_ids=[101, 102, 103, 104]):
        print(f'[{cf_body_name}@{cf_uri}] Initializing...')

        # Init Crazyflie drivers
        cflib.crtp.init_drivers(enable_debug_driver=False)

        self.cf = None
        self.cf_body_name = cf_body_name
        self.cf_uri = cf_uri
        self.marker_ids = marker_ids
        self.max_tracking_loss = max_tracking_loss
        self.max_vel = max_vel
        self.qtm = qfly.QtmWrapper(cf_body_name)
        self.pose = qfly.Pose(0, 0, 0)
        self.scf = SyncCrazyflie(cf_uri)
        self.world = world

        print(f'[{self.cf_body_name}@{self.cf_uri}] Connected.')
        print(
            f'[{self.cf_body_name}@{self.cf_uri}] Connecting to QTM: {self.qtm.qtm_ip}')

    def __enter__(self):
        self.scf.open_link()
        self.cf = self.scf.cf

        # Slow down
        self.set_speed_limit(self.max_vel)

        # Set active marker IDs
        print(
            f'[{self.cf_body_name}@{self.cf_uri}] Active marker IDs: {self.marker_ids}')
        self.cf.param.set_value('activeMarker.front', self.marker_ids[0])
        self.cf.param.set_value('activeMarker.right', self.marker_ids[1])
        self.cf.param.set_value('activeMarker.back', self.marker_ids[2])
        self.cf.param.set_value('activeMarker.left', self.marker_ids[3])

        # Set up callbacks to handle data from QTM
        self.qtm.on_cf_pose = lambda pose: self._set_pose(pose)

        self.setup_estimator()

        return self

    def __exit__(self):
        self.qtm.close()
        self.scf.close_link()

    def is_safe(self):
        """
        Perform safety checks, return False if unsafe
        """
        world = self.world
        # Is the drone tracked properly?
        if self.qtm.tracking_loss > self.max_tracking_loss:
            print(
                f'[{self.cf_body_name}@{self.cf_uri}] TRACKING LOST FOR {str(self.max_tracking_loss)} FRAMES!')
            return False
        # Is the drone inside the safe volume?
        if not (world.origin.x + world.expanse < self.pose.x < world.origin.x - world.expanse
                and world.origin.y + world.expanse < self.pose.y < world.origin.y - world.expanse
                and world.origin.z + world.expanse < self.pose.z < world.origin.z - world.expanse):
            print(f'[{self.cf_body_name}@{self.cf_uri}] DRONE OUTSIDE SAFE VOLUME!')
            return False
        else:
            return True

    def land(self):
        """
        Execute a gentle landing sequence directly down from current 
        """
        print(f'[{self.cf_body_name}@{self.cf_uri}] Landing...')

        # Slow down
        self.cf.param.set_value('posCtlPid.xyVelMax', 0.3)
        self.cf.param.set_value('posCtlPid.zVelMax', 0.03)
        time.sleep(0.1)

        for z in range(5, 0, -1):
            self.cf.commander.send_hover_setpoint(0, 0, 0, float(z) / 10.0)
            time.sleep(0.15)
        self.cf.commander.send_stop_setpoint()

    def safe_position_setpoint(self, target):
        """
        Run safety checks and set absolute position setpoint.
        """
        world = self.world
        if self.is_safe():
            # Keep target inside bounding box
            target.clamp(world)
            # Touch up
            if target.yaw == None:
                target.yaw = 0
            # Engage
            self.cf.commander.send_position_setpoint(
                target.x, target.y, target.z, target.yaw)

    def setup_estimator(self):
        # Activate Kalman estimator
        self.cf.param.set_value('stabilizer.estimator', '2')

        # Set the std deviation for the quaternion data pushed into the Kalman filter.
        # The default value seems to be a bit too low.
        self.cf.param.set_value('locSrv.extQuatStdDev', 0.6)

        # Reset estimator
        self.cf.param.set_value('kalman.resetEstimation', '1')
        time.sleep(0.1)
        self.cf.param.set_value('kalman.resetEstimation', '0')
        time.sleep(1)

        # Wait for estimator to stabilize

        print(
            f'[{self.cf_body_name}@{self.cf_uri}] Waiting for estimator to find position...')

        log_config = LogConfig(name='Kalman Variance', period_in_ms=500)
        log_config.add_variable('kalman.varPX', 'float')
        log_config.add_variable('kalman.varPY', 'float')
        log_config.add_variable('kalman.varPZ', 'float')

        var_y_history = [1000] * 10
        var_x_history = [1000] * 10
        var_z_history = [1000] * 10

        threshold = 0.001

        with SyncLogger(self.scf, log_config) as logger:
            for log_entry in logger:
                data = log_entry[1]

                var_x_history.append(data['kalman.varPX'])
                var_x_history.pop(0)
                var_y_history.append(data['kalman.varPY'])
                var_y_history.pop(0)
                var_z_history.append(data['kalman.varPZ'])
                var_z_history.pop(0)

                min_x = min(var_x_history)
                max_x = max(var_x_history)
                min_y = min(var_y_history)
                max_y = max(var_y_history)
                min_z = min(var_z_history)
                max_z = max(var_z_history)

                print(f'[{self.cf_body_name}@{self.cf_uri}]' +
                      "Kalman variance | X: {:8.4f}  Y: {:8.4f}  Z: {:8.4f}".format(
                          max_x - min_x, max_y - min_y, max_z - min_z))

                if (max_x - min_x) < threshold and (
                        max_y - min_y) < threshold and (
                        max_z - min_z) < threshold:
                    break

    def set_speed_limit(self, max_vel):
        print(f'[{self.cf_body_name}@{self.cf_uri}] Speed limit: {max_vel} m/s')
        self.cf.param.set_value('posCtlPid.xyVelMax', max_vel)
        self.cf.param.set_value('posCtlPid.zVelMax', max_vel)

    def _set_pose(self, pose):
        self.pose = pose
        self._send_extpose(pose.x, pose.y, pose.z, pose.rotmatrix)

    def _send_extpose(self, pose):
        """Send full pose from mocap to Crazyflie."""
        rot = pose.rotmatrix
        qw = sqrt(1 + rot[0][0] + rot[1][1] + rot[2][2]) / 2
        qx = sqrt(1 + rot[0][0] - rot[1][1] - rot[2][2]) / 2
        qy = sqrt(1 - rot[0][0] + rot[1][1] - rot[2][2]) / 2
        qz = sqrt(1 - rot[0][0] - rot[1][1] + rot[2][2]) / 2
        # Normalize the quaternion
        ql = math.sqrt(qx ** 2 + qy ** 2 + qz ** 2 + qw ** 2)
        # Send to Crazyflie
        self.cf.extpos.send_extpose(
            pose.x, pose.y, pose.z, qx / ql, qy / ql, qz / ql, qw / ql)