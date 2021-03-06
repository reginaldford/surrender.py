# Surrender.py
Surrender.py is a single file python program that uses SSH and SCP to render **Blender** animations on other computers. Surrender renders animations faster by splitting up the frames to render among other hosts. During a render session, if a render host becomes available to do more work, it is assigned to render the next set of frames (chunk) that need to be rendered, until all frames are rendered and finally sent back to the master host.

## How does it work?
* Surrender connects to the render hosts by SSH and then creates a new directory for the render results and associated data. The directory will have the session name, which can be specified in the configuration file or in the command line. If no session name is given, this directory is named after the time that the program is executed in the format YYYY_MM_DD_HH_mm_ss. Surrender sends a copy of the **.blend** file to each machine to store into this new directory. The file should be packed so that necessary resources are available. Surrender commands each host to render different frames of the animation according to the config file. When a host finishes a chunk of frames, Surrender commands the host to do the next chunk of frames or Surrender has completed and prints a statistical summary of the session. The chunk size (in frames) is specified in the configuration file. The master can help render, by allowing SSH/SCP to the loopback address and adding **127.0.0.1** to as a host in the config file. Surrender relies on Blender's background rendering capabilities from the command line.
* While rendering, Surrender uses **tee** to direct logs into the render while providing the log data as feedback. The logs are all collected back to the master with the file name **\<hostname\>_log.txt** where **\<hostname\>** is the actual host that the log came from.


## How to run:
### Prerequisites for surrender
* Running surrender.py requires [python 3](https://www.python.org/downloads/), as well as [paramiko SSH library](https://github.com/paramiko/paramiko) and [SCP](https://pypi.org/project/scp/). Both can be installed with **PIP**. 

### Prepare your machines
* Each host will need to be able to run blender, particularly **blender -b**. The Blender program on each render host should be the same version to avoid unwanted variations between rendered frames. Render hosts must also have a running SSH service. The master computer will need SSH access to each of the worker hosts. A connection must be possible without using password, but using a key file instead. If the key file is encrypted with a passkey, you can register the passkey on some window managers with the **ssh-add** command. Once you can SSH to your worker hosts and SCP files to and from them without typing a password, you are ready to use surrender.
* Copy and/or Edit the surrender.yaml file to describe your cluster and render needs.

## Installing surrender.py
* Surrender.py is a single standalone file, so it can be run by using **./surrender.py**, but installing it can be more convenient.
* To install surrender.py, just copy **surrender.py** into your **/usr/bin** directory and make sure that you can execute the file:
**chmod +x /usr/bin/surrender.py** 

### Running the cluster
* Run a cluster with surrender:
 The config file is optional and defaults to **surrender.yaml**
 The session name is optional and defaults to the date and time of execution.

**surrender.py \<your config file.yaml\> \<session name\>**

* **ctrl+c** will send an exit signal, which will close all of the open SSH/SCP connections
  Note that closing the program before a render session completes will allow hosts to complete what ever chunk they are working on.
  The program does not STOP the render hosts before they complete a chunk. You can kill blender programs on a host with **killall blender** , but beware that this also will kill all running instances of blender unrelated to the cluster session. Surrender.py will eventually have a feature to kill the render jobs and continue previous jobs.
  
 ### Surrender also has auxilliary functions
In each command, **\<your.yaml\>** is optional and defaults to **surrender.yaml**

1. Clear the render results on the render host.

  **surrender.py \<your.yaml\> clr_rmt**

2. Clear the render results on the master side.

  **surrender.py \<your.yaml\> clr**

3. Retreive images from a previous session on the render hosts via SCP. Examples:

  **surrender.py get \<your.yaml\> \<session name\>**

### Help and Other Functions
  * Run **surrender.py help** to see the command syntax and other functions available.
