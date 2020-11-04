# Surrender
Surrender is a python program that uses SSH and SCP turn multiple Linux machines into a render farm for Blender, the open source 3D modeling and Animation program. Once configured correctly, this program allows an animation to be rendered quicker by tasking other machines to render the frames, sharing the render job by segmenting the frames. This code is only designed for Linux/Unix systems.

## How does it work?
* Surrender connects to the render machines by SSH and then creates a new directory for the render results and associated data. This directory is always named after the time in the format **YYYY_MM_DD_HH_mm_ss**. Surrender sends a copy of the **.blend** file to each machine. The file should be packed, so that everything necessary to render the image is available in the **.blend** file. Surrender then creates a new directory on each render host for this render, and commands each machine to render different frames of the animation. The segmentation size (in frames) is specified in the configuration file. Surrender relies on Blender's background rendering capabilities throught the command line. Check out [The Blender Documentation](https://docs.blender.org/manual/en/latest/advanced/command_line/render.html)
* Once the render is complete, Surrender then retreives all of the rendered images back to the master machine via SCP and provides a metric summary of the render job.
* Surrender also has auxilliary functions to:
1. Clear the render results on the render host.
**./surrender.py clr_rmt**

or

**./surrender.py <your.yaml> clr_rmt**

2. Clear the render results on the master side.
**./surrender.py clr**

or

**./surrender.py <your.yaml> clr**

3. Retreive images from a previous job on the render hosts via SCP. Example:
**./surrender.py get 2020_11_3_13_30_15**

or 

**./surrender.py get <your.yaml> 2020_11_3_13_30_15**

In each example above, **<your.yaml>** is an optional argument to specify the **.yaml** configuration file if it is not the default **surrender.yaml**.

## How to run:
### Prepare your machines
* Firstly, each render host will need to be able to run blender, particularly **blender -b**. The master computer will need SSH access to each of the worker hosts. A connection must be possible without using password, but using a key file instead. If the key file is encrypted with a passkey, you can register the passkey on some window managers with the ssh-add command. Once you can SSH to your worker hosts and SCP files to and from them without typing a password, you are ready to use surrender.
* Copy and or Edit the surrender.yaml file to describe your cluster and render needs
### Running the cluster
* Run **./surrender.py \<your config file.yaml\>** to start rendering!
* **ctrl+c** will send an exist signal, which will close any open SSH/SCP connections
  Note that closing the program before a render job completes will allow hosts to complete what ever chunk they are working on.
  The program does not STOP the render hosts early. You can kill blender programs with **killall blender** , but beware that this also will kill all running instances of blender unrelated to the cluster job.
  
### Help and Other Functions
  * Run **./surrender.py help** to see the command syntax and other functions available.
