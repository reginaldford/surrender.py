#!/usr/bin/env python

import math
import shutil
import signal
import sys
import os
import yaml
from datetime import datetime
import threading
import time
from paramiko import SSHClient
from scp import SCPClient

# TODO: before we can have multiple sessions, we must make a session class
surrender_sessions = []

def connect_to_hosts(session):
    for host_id in range(len(session['hosts'])):
        client = SSHClient()
        session['connections'][host_id] = client
        client.load_system_host_keys()
        print("Connecting via SSH to "+session['hosts'][host_id]['hostname'])
        port = session['default_ssh_port']
        if 'ssh_port' in  session['hosts'][host_id]:
            port = int(session['hosts'][host_id]['ssh_port'])
        client.connect(session['hosts'][host_id]['hostname'], username=session['user'],port=port)

def close_connections(session):
    if len(session['connections']) > 0:
        for host_id in range(len(session['hosts'])):
            print("Closing SSH connection to "+session['hosts'][host_id]['hostname'])
            session['connections'][host_id].close()

def exit_if_no_hosts(hosts):
    if len(hosts)==0:
        print("There are no enabled hosts!")
        sys.exit(1);

def send_cmd(session,host_id,cmd):
    cmd = "export TERM=xterm; "+cmd
    client = session['connections'][host_id]
    stdin, stdout, stderr = client.exec_command(cmd)

    # Print output of command. Will wait for command to finish.
    for line in stdout:
        parse_line(session,line,host_id)
    for line in stderr:
        print("!! "+line.strip('\n'))
    # We don't use stdin
    stdin.channel.shutdown_write()
    stdin.close()
    stdout.close()
    stderr.close()
    stat = stdout.channel.recv_exit_status()
    if stat!=0:
        print("ERROR on "+str(session['hosts'][host_id]['hostname'])+"! From command: "+cmd)
        print("Error code "+str(stat))
    return stat

def signal_handler(sig,frame):
    print("Program received signal to close...")
    for s in surrender_sessions:
        close_connections(s)
    sys.exit(0)

def parse_config(config_file):
    print("Parsing session file "+config_file)
    with open(config_file) as file:
        config = yaml.load(file,Loader=yaml.FullLoader)
    #We trust the config
    session = config #store the actual values
    surrender_sessions.append(session)

    ##disable the specified hosts:
    host_id=0
    while host_id < len(session['hosts']):
        if session['hosts'][host_id]['enabled'] == False:
            print(session['hosts'][host_id]['hostname']+" is disabled.")
            del session['hosts'][host_id]
        else:
            host_id = host_id + 1
    return session

def init(session):
    signal.signal(signal.SIGINT,signal_handler)
    session['start_time'] = time.time()
    session['connections']=[]
    session['frames_completed']=0
    session['specific_frames_completed']=[]
    session['time_last_frame_completed']=time.time()
    for host_id in range(len(session['hosts'])):
        session['connections'].append(False)
        session['specific_frames_completed'].append(0)

def setup_render_session(session):
    print("Begining Render Session")
    print("Creating local directory for session  at "+session['local_dest'])
    if not os.path.isdir(session['local_output_dir']):
        os.mkdir(session['local_output_dir'])
    if not os.path.isdir(session['local_dest']):
        os.mkdir(session['local_dest'])
    session['busy_state'] =[]
    session['host_feedback']=[]
    session['connections']=[]
    session['frame_log']=[]
    for host_id in range(len(session['hosts'])):
        session['busy_state'].append(False)
        session['host_feedback'].append('')
        session['connections'].append(False)
        session['frame_log'].append([])

def clear_remote(config_file):
    print("Clearing remote cache directories")
    session=parse_config(config_file)
    init(session)
    exit_if_no_hosts(session['hosts'])
    connect_to_hosts(session)
    exit_if_no_hosts(session['hosts'])
    for host_id in range(len(session['hosts'])):
        print("Removing "+session['remote_dest']+" on "+session['hosts'][host_id]['hostname'])
        send_cmd(session,host_id,"rm -fr "+session['remote_dest'])
        print("Recreating "+session['remote_dest']+" on "+session['hosts'][host_id]['hostname'])
        send_cmd(session,host_id,"mkdir "+session['remote_dest'])
    close_connections(session)

def clr_local(config_file):
    print("Clearing local cache directory")
    session=parse_config(config_file)
    init(session)
    exit_if_no_hosts(session['hosts'])
    print("Removing directories from "+session['local_output_dir'])
    ls_list = os.listdir(session['local_output_dir'])
    print(ls_list)
    for thing in ls_list:
        dir_path = session['local_output_dir']+'/'+thing
        if os.path.isdir(dir_path):
            print("Removing "+dir_path)
            shutil.rmtree(dir_path)

def collect_results(session):
    for host_id in range(len(session['hosts'])):
        if len(session['frame_log'][host_id])>0:
            print("Collecting images from "+session['hosts'][host_id]['hostname']+ " to "+ session['local_dest'])
            scp=SCPClient(session['connections'][host_id].get_transport())
            for frame_num in session['frame_log'][host_id]:
                scp.get(session['remote_session_dest']+"/"+str(frame_num).zfill(6)+"."+session['ext'],session['local_dest'])
            print("Collecting logs from "+session['hosts'][host_id]['hostname']+ " to "+ session['local_dest'])
            scp=SCPClient(session['connections'][host_id].get_transport())
            scp.get(session['remote_session_dest']+"/"+"log_"+session["hosts"][host_id]['hostname']+".txt",session['local_dest'])
            scp.close()

def get_data_by_session_name(session_name,config_file):
    print("Getting images and logs from session: "+session_name)
    session=parse_config(config_file)
    init(session)
    connect_to_hosts(session)
    recovery_dest = os.path.dirname(session['local_dest'])
    for host_id in range(len(session['hosts'])):
        scp=SCPClient(session['connections'][host_id].get_transport(),socket_timeout=30)
        print("Transferring "+session['hosts'][host_id]['hostname']+":"+session['remote_dest']+"/"+session_name+" to "+recovery_dest)
        scp.get(session['remote_dest']+"/"+session_name,recovery_dest,recursive=True)
        print("Closing SCP Connection to "+session['hosts'][host_id]['hostname'])
        scp.close()
    close_connections(session)

def parse_line(session,line,host_id):
    if line[0:12]=="Blender quit":
        session['host_feedback'][host_id]="Completed chunk"
        session['busy_state'][host_id]=False
        session['frames_completed']=session['frames_completed'] + session['chunk_size']
        session['specific_frames_completed'][host_id] = 0
        session["time_last_frame_completed"] = time.time()
    else:
        if line[0:4] == 'Fra:':
            session['host_feedback'][host_id] = line.strip('\n')
            current_frame=''
            counter=4
            while line[counter] != ' ':
                current_frame=current_frame + line[counter]
                counter = counter + 1
            extra_frames=(int(current_frame) - 1) % session['chunk_size']
            if session['specific_frames_completed'][host_id] != extra_frames:
                session['specific_frames_completed'][host_id] = extra_frames
                session["time_last_frame_completed"] = time.time()

def find_available_host(session):
    host_id=0
    while host_id < len(session['busy_state']):
        if session['busy_state'][host_id] == False:
            return host_id
        host_id = host_id + 1
    return - 1

class frame_job(threading.Thread):
    def __init__(self,session,my_host_id,frame,cmd):
        threading.Thread.__init__(self)
        self.my_host_id=my_host_id
        self.frame=frame
        self.cmd=cmd
        self.session=session
    def run(self):
        session = self.session
        session['frame_log'][self.my_host_id].append(self.frame)
        if(session['chunk_size']>1):
            for f in range(self.frame+1,min(self.frame+session['chunk_size'],session['end_frame']+1)):
                session['frame_log'][self.my_host_id].append(f)
        session['host_feedback'][self.my_host_id] = "Opening File, beginning frame "+str(self.frame)
        print("HOST: "+session['hosts'][self.my_host_id]['hostname']+" CMD: "+self.cmd)
        return send_cmd(session,self.my_host_id,self.cmd)

def space_to(string,desired_length):
    output=string
    if len(string)>desired_length:
        output=string[0:desired_length/2-1]+".."+string[desired_length/2-1:end]
    if len(string)<desired_length:
        for count in range(desired_length-len(string)):
            output = output+" "
    return output

def print_feedback(session,current_frame):
    print()#just 1 space from last display
    completed = session['frames_completed']
    for host_id in range(len(session['hosts'])):
        completed+=session['specific_frames_completed'][host_id]
    num_frames = session['end_frame']-session['start_frame']+1
    update_line = "Completed "+str(completed) + " frames of " + str(num_frames)
    update_line = update_line + " [ " +str(round(100 * (completed/num_frames))) + " % ]"
    print("Time elapsed: "+pretty_time(time.time()-session['start_time']))
    if completed > 0:
        time_elapsed = session['time_last_frame_completed']-session['start_time']
        avg_frame_time = time_elapsed/completed
        seconds_left = round((num_frames-completed) * avg_frame_time)
        update_line = update_line + " ETA: " + pretty_time(seconds_left)
    print(update_line)
    for host_id in range(len(session['hosts'])):
        print(space_to(session['hosts'][host_id]['hostname'],16)+" : "+session['host_feedback'][host_id])

def any_hosts_busy(session):
    for host_id in range(len(session['hosts'])):
        if session['busy_state'][host_id] == True:
            return True
    return False

def compute_frames(session):
    current_frame = session['start_frame']
    while current_frame <= session['end_frame']:
        time.sleep(session['program_frame_rate'])
        print_feedback(session,current_frame)
        available_host = find_available_host(session)
        if(available_host > -1):
            last_frame_in_chunk = min(session['end_frame'],current_frame+session['chunk_size']-1)
            print("Commanding "+session['hosts'][available_host]['hostname']+" to compute frame(s) "+ str(range(current_frame,last_frame_in_chunk)))
            format_string="PNG" #png by default
            ext = session['ext']
            if ext == "exr":
                 format_string = "OPEN_EXR"
            elif ext == "png":
                 format_string = "PNG"
            elif ext == "jpg" or ext == "jpeg":
                 format_string = "JPEG"
            elif ext == "tiff" or ext == "tif":
                 format_string = "TIFF"
            elif ext == "sgi" or ext == "rgb" or ext == "bw":
                 format_string = "IRIS"
            elif ext == "bmp":
                 format_string = "BMP"
            elif ext == "tga":
                 format_string = "TARGA"
            elif ext == "cin" or ext == "dpx":
                 format_string = "CINEON"
            elif ext == "jp2" or ext == "j2c":
                 format_string = "JPEG_2000"
            else:
                print("Unsupported file extension: "+session['ext'])

            bin_file = session['default_bin_file']
            if "bin_file" in session['hosts'][available_host]:
                bin_file = session['hosts'][available_host]["bin_file"]

            cmd = bin_file + " -b \""

            if session["send_file"]:
                cmd = cmd + session['remote_session_dest']+"/"+os.path.basename(session['blend_file'])
            else:
                cmd = cmd + session['blend_file']

            cmd = cmd + "\" -E " + session["engine"]

            cmd = cmd + " -o \"" + session['remote_session_dest'] + "/######." + ext + "\" -F " + format_string
            cmd = cmd + " -s " + str(current_frame) + " -e " + str(last_frame_in_chunk) + " -a "
            cmd = cmd + " | tee -a \""+session['remote_session_dest']+"/log_"+session['hosts'][available_host]['hostname']+".txt\""
            session['busy_state'][available_host]=True
            fj = frame_job(session,available_host,current_frame,cmd)
            current_frame=current_frame+session['chunk_size']
            fj.start()
    while any_hosts_busy(session) :
        time.sleep(session['program_frame_rate'])
        print_feedback(session,current_frame)

def make_remote_session_dest(session):
    for host_id in range(len(session['hosts'])):
        print("Creating session directory on each host:")
        for host_id in range(len(session['hosts'])):
            print("Making directory "+session['remote_session_dest']+" on "+ session['hosts'][host_id]['hostname'])
            send_cmd(session,host_id,"mkdir -p "+session['remote_session_dest'])

def distribute_blend_file(session):
    for host_id in range(len(session['hosts'])):
        print("Sending .blend file "+session['blend_file']+" to "+ session['hosts'][host_id]['hostname']+":"+session['remote_session_dest'])
        scp=SCPClient(session['connections'][host_id].get_transport())
        scp.put(session['blend_file'],session['remote_session_dest']+"/"+os.path.basename(session['blend_file']))
        scp.close()

def pretty_time(time_in_seconds):
    pretty_time = str(round(time_in_seconds)) + " s"
    if time_in_seconds > 60 and time_in_seconds < 3600:
        minutes = str(math.floor(time_in_seconds / 60.0))
        seconds = str(round(time_in_seconds % 60.0))
        pretty_time = minutes + " m " + seconds + " s"
    elif time_in_seconds >= 60 * 60:
        hours = str(math.floor(time_in_seconds/3600.0))
        minutes = str(math.floor((time_in_seconds - 3600 * int(hours)) / 60.0))
        seconds = str(round(time_in_seconds % 60.0))
        pretty_time =hours + " h " + minutes + " m " + seconds + " s"
    return pretty_time

def run_cluster(config_file,user_session_name):
    session = parse_config(config_file)
    #check for 2 specs of session name
    if "session_name" in session:
        if user_session_name!="":
            print("Session name is specified in both config and command argument! Exiting")
            sys.exit(1)

    if user_session_name!="":
        session['session_name']=user_session_name
    else:
        if "session_name" not in session:
            session['session_name']=now.strftime("%Y_%m_%d_%H_%M_%S")

    #if session name is specified, it will simply be used as session['session_nanme']

    #computed aspects of session
    session['remote_session_dest']= session['remote_dest']+"/"+session['session_name']
    session['local_dest']= session['local_output_dir']+"/"+session['session_name']
    session['remote_blend_file']=session['remote_session_dest']+"/"+os.path.basename(session['blend_file'])
        
    init(session)
    exit_if_no_hosts(session['hosts'])
    setup_render_session(session)
    connect_to_hosts(session)
    make_remote_session_dest(session)
    if session["send_file"]==True:
        distribute_blend_file(session)
    compute_frames(session)
    collect_results(session)
    close_connections(session)
    print("\n\nSUMMARY:")
    print("Output location: "+session['local_dest'])
    for host_id in range(len(session['hosts'])):
        print(session['hosts'][host_id]['hostname']+":")
        print("Number of Frames Completed: "+str(len(session['frame_log'][host_id])))
        total_frames = session['end_frame']-session['start_frame'] + 1
        frames_completed = len(session['frame_log'][host_id])
        percentage = round(100 * frames_completed  / total_frames)
        print("Percentage of Total Frames: "+str(percentage) + " %\n")
    end_time=time.time()
    time_in_seconds = round(end_time-session['start_time'])
    print("Total Time Elapsed: " + pretty_time(time_in_seconds));

def print_help():
    print("Surrender v 0.2")
    print("USAGES:")
    print("NOTE: Config file is ALWAYS optional and defaults to surrender.yaml")
    print("Config file MUST have .yaml extension")
    print("\n1) Run a render session according to config file")
    print("surrender.py <config file>")
    print("\n2) Delete all local data from render jobs")
    print("surrender.py <config file> clr")
    print("\n3) Delete all remote data from render jobs.")
    print("surrender.py <config file> clr_rmt")
    print("\n4) Download images and logs from previous session")
    print("surrender.py <config_file> get <session_id>")

now=datetime.now()
user_session_name=""

if len(sys.argv) > 1:
    possible_file, possible_extension = os.path.splitext(os.path.sys.argv[1])
    if possible_extension == ".yaml":
        config_file = sys.argv[1]
        if len(sys.argv) > 2:
            user_session_name=sys.argv[2]
    else:
        config_file = "surrender.yaml"
        user_session_name=sys.argv[1]
else:
    config_file = "surrender.yaml"

for i in range(1,min(2,len(sys.argv))):
    if sys.argv[i] == "clr_rmt":
        clear_remote(config_file)
        sys.exit(0)
    if sys.argv[i] == "clr":
        clr_local(config_file)
        sys.exit(0)
    if sys.argv[i] == "help" or sys.argv[i] == "--help":
        print_help()
        sys.exit(0)
    if sys.argv[i] == "get":
        if len(sys.argv) > i + 1 :
            get_data_by_session_name(sys.argv[i+1],config_file)
            sys.exit(0)
        else:
            print("Session name must be provided after 'get'")
            sys.exit(1)

run_cluster(config_file,user_session_name)
