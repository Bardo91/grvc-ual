#!/usr/bin/env python
import subprocess
import argparse
import utils
import numpy
import rospkg
import rospy
import tf2_ros
import tf2_geometry_msgs
from geometry_msgs.msg import PoseStamped
from geometry_msgs.msg import TransformStamped
import xml.etree.ElementTree as ET


def main():

    # Parse arguments
    parser = argparse.ArgumentParser(description='Spawn robot in Gazebo for SITL')
    parser.add_argument('-model', type=str, default="mbzirc",
                        help='robot model name, must match xacro description folder name')
    parser.add_argument('-id', type=int, default=1,
                        help='robot id, used to compute sim_port')
    parser.add_argument('-material', type=str, default="DarkGrey",
                        help='robot Gazebo/material; \
                        see materials/scripts/gazebo.material (at your gazebo version)')
    parser.add_argument('-backend', type=str, default="mavros",
                        help='backend to use')
    args, unknown = parser.parse_known_args()
    utils.check_unknown_args(unknown)

    # Get an instance of RosPack with the default search paths
    rospack = rospkg.RosPack()

    # Init ros node
    rospy.init_node('spawn_gzmodel_{}'.format(args.id))

    # Xacro description must be in robots_description package
    description_dir = rospack.get_path("robots_description")
    xacro_description = description_dir + "/models/" + args.model + "/model.xacro"

    # Create temporary directory for robot sitl stuff
    temp_dir = utils.temp_dir(args.id)
    subprocess.call("mkdir -p " + temp_dir, shell=True)

    # Get udp configuration, depending on id
    udp_config = utils.udp_config(args.id)

    # Create urdf from xacro description
    temp_urdf = temp_dir + "/" + args.model + ".urdf"
    xacro_args = "xacro --inorder -o " + temp_urdf + " " + \
    xacro_description + \
    " enable_mavlink_interface:=true" + \
    " enable_ground_truth:=false" + \
    " enable_logging:=false" + \
    " enable_camera:=false" + \
    " enable_wind:=false" + \
    " mavlink_udp_port:=" + str(udp_config["sim_port"]) + \
    " visual_material:=" + args.material
    xacro_out = open(temp_dir+"/xacro.out", 'w')
    xacro_err = open(temp_dir+"/xacro.err", 'w')
    subprocess.call(xacro_args, shell=True, stdout=xacro_out, stderr=xacro_err)
    xacro_out.close()
    xacro_err.close()

    # Create sdf from urdf
    temp_sdf = temp_dir + "/" + args.model + ".sdf"
    subprocess.call("gz sdf -p " + temp_urdf + " > " + temp_sdf, shell=True)
    
    # Set gravity=0 for light simulations
    if args.backend == 'light':
        tree = ET.parse(temp_sdf)
        root = tree.getroot()
        model = root.find('model')
        for linktag in model.findall('link'):
            #if linktag.get('name') == 'base_link':
            gravitytag = linktag.find('gravity')
            if gravitytag == None:
                gravitytag = ET.SubElement(linktag,'gravity')
            gravitytag.text = '0'
        tree.write(temp_sdf)

    # Get robot home position from rosparam
    tf_buffer = tf2_ros.Buffer(rospy.Duration(1200.0)) #tf buffer length
    tf_listener = tf2_ros.TransformListener(tf_buffer)

    if rospy.has_param( '/uav_{}_home_frame'.format(args.id) ):
        uav_frame = rospy.get_param( '/uav_{}_home_frame'.format(args.id) )
        if uav_frame['parent_frame']=='map':
            robot_home = uav_frame['translation']
            robot_yaw = uav_frame['rotation'][2]
        elif uav_frame['parent_frame']=='game':
            transform = tf_buffer.lookup_transform('map', 'game', rospy.Time(0), rospy.Duration(1.0))
            pose_stamped = PoseStamped()
            pose_stamped.header.frame_id = 'game'
            pose_stamped.pose.position.x = uav_frame['translation'][0]
            pose_stamped.pose.position.y = uav_frame['translation'][1]
            pose_stamped.pose.position.z = uav_frame['translation'][2]
            pose_transformed = tf2_geometry_msgs.do_transform_pose(pose_stamped, transform)
            robot_home = [pose_transformed.pose.position.x,pose_transformed.pose.position.y, pose_transformed.pose.position.z]
            robot_yaw = uav_frame['rotation'][2]
        else:
            robot_home = [0.0, 0.0, 0.0]
            robot_yaw = 0.0
    else:
        robot_home = [0.0, 0.0, 0.0]
        robot_yaw = 0.0
    
    z_min = 0

    # Spawn robot sdf in gazebo
    gzmodel_args = "gz model -f " + temp_sdf + \
    " -m " + args.model + "_" + str(args.id) + \
    " -x " + str(robot_home[0]) + \
    " -y " + str(robot_home[1]) + \
    " -z " + str(robot_home[2]+z_min) + \
    " -Y " + str(robot_yaw)
    subprocess.call(gzmodel_args, shell=True)

if __name__ == "__main__":
    main()
