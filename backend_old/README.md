# forgelabSimulation

## Install Virtual Environment
Python 3.12
sudo apt-get update && sudo apt-get install -y build-essential python3.12-dev

Give passwordless sudo for the specific commands (most common):
sudo visudo
    then add:
     alextub ALL=(root) NOPASSWD: /usr/bin/apt-get, /usr/bin/apt, /usr/bin/dpkg

pip install 'vtk<9.5'
pip install --no-cache-dir --no-build-isolation -v mayavi
pip install -r requirements.txt
pip check

## Install Fluent-bit

### Windows settings for Fluent-Bit

1. Set network connection as Private
2. Open port 3130 for incoming connections

### Documentation:

    https://docs.fluentbit.io/manual/installation/windows

### Download Fluent-bit Windows installer 64-bit:

    https://packages.fluentbit.io/windows/fluent-bit-2.2.1-win64.exe

### Install Fluent-bit into directory: 

    C:\fluent-bit

### Test Fluent-bit:

Run in CMD command line:

    C:\fluent-bit\bin\fluent-bit.exe -i dummy -o stdout

### Copy Configuration into configuration file:

Fluent-bit configuration file is located at:    

    C:\fluent-bit\fluent-bit.conf

Configuration:
```
[SERVICE]
    Flush        1
    Grace        30
    Log_Level    debug


[INPUT]
    Name        tcp
    Listen      0.0.0.0
    Port        3130

[OUTPUT]
    Name    file
    Log_Level    debug
    Path    C:\fluent-bit\logs\
    Mkdir   yes
```

### Register Fluent Bit as a Windows service:

Execute the following command on Command Prompt. Please be careful that a single space is required after ```binpath=.```

    sc.exe create fluent-bit binpath= "\fluent-bit\bin\fluent-bit.exe -c \fluent-bit\conf\fluent-bit.conf"

### To start Fluent Bit automatically on boot, execute the following:

    sc.exe config fluent-bit start= auto

### Run Fluent Bit service:

    sc.exe start fluent-bit

### Check Fluent Bit service status:

Run Command Prompt in CMD:

    sc.exe query fluent-bit

You should see the following output:

    SERVICE_NAME: fluent-bit
        TYPE               : 10  WIN32_OWN_PROCESS
        STATE              : 4 Running
        ...

### To halt the Fluent Bit service:

Execute the "stop" command

    sc.exe stop fluent-bit


## Install on Windows 10

To run a Python script automatically upon user login on Windows 10 Pro, you can place a shortcut to the script in the "Startup" folder. Below are the detailed steps:

### Creating a Batch File
Instead of running the Python script directly, it's often more reliable to create a batch file that runs the script using the Python interpreter. 

1. **Create a Batch File:**
   - Open Notepad.
   - Type the following lines:
     ```batch
     @echo off
     pythonw.exe "C:\path\to\run_debug.py"
     ```
     Replace `"C:\path\to\run_debug.py"` with the full path to your Python script.
   - Save the file with a `.bat` extension, for example, `run_script.bat`.

### Adding Script to Startup
- Place it in the Startup Folder:**
  - Press `Win + R` to open the Run dialog.
  - Type `shell:startup` and press `Enter` to open the Startup folder.
  - Right-click in the folder and select `New > Shortcut`.
  - Click `Browse` and navigate to the location where you saved your batch file (`run_script.bat`).
  - Select the batch file and click `OK`, then click `Next`.
  - Give the shortcut a name if you want to change it, then click `Finish`.

### Note: Ensure Python Path
Ensure that the path to the Python interpreter (`pythonw.exe`) is in the System Environment Variable PATH. If not, you may need to provide the full path to `pythonw.exe` in the batch file. The difference between `python.exe` and `pythonw.exe` is that `pythonw.exe` will not open a command prompt window when the script is run.

### Debugging
Ensure your Python script can run without issue when run manually using the command line. If there are issues during startup, you may not be able to see error messages if the script is run with `pythonw.exe`. Replace `pythonw.exe` with `python.exe` in your batch file and run it manually to view any error messages in the command prompt window.

### Final Notes
- If your script requires administrative privileges, you'll need to ensure that it's run as an administrator. This can potentially be set via the shortcut properties ("Run as administrator" under the "Shortcut" tab).
- If you want the script to run but remain hidden, ensure you use `pythonw.exe` in your batch file to prevent a command prompt window from appearing.
- Test thoroughly to ensure the script runs as expected upon login.

And that's it! Following these steps should allow your Python script to run automatically upon user login in Windows 10 Pro.


## Clone from GitHub

###  Clone to FL-ADMIN-2

Open **Git Bash** 

```commandline
git clone https://github.com/forgingexpert/forgelab.git
```

Then open in PyCharm

### Update token in local repository

```commandline
git remote set-url origin https://github.com/forgingexpert/forgelab.git
```


## Ubuntu settings
|                       Parameter | Value              |
|--------------------------------:|:-------------------|
| Python scripts entry file name: | main.py            |
|     Python scripts working dir: | /opt/forgelabPre   |
|                   NetBIOS name: | fl-pre-1           |
|                    IP internal: | 192.168.111.130/24 |
|                        IP mask: | 255.255.255.0      |
|             Network interfaces: | ens32, ens33       |
|                      User name: | alext              |
|                  User password: | Pre7tlva2pv        |
|                             OS: | Ubuntu 22.04       |
|   SSH identification file name: | pre-1              |
|       SSH public key file name: | pre-1.pub          |
|                SSH pass phrase: | 2008               |

### Access

## Bitvise SSH Client settings

|        Parameter | Value                                                               |
|-----------------:|:--------------------------------------------------------------------|
|     Server Host: | 192.168.111.130                                                     |
|       User name: | alext                                                               |
|   User password: | Pre7tlva2pv                                                         |
|      Client key: | Global 2                                                            |
|   SSH file name: | pre-1.pub                                                           |
|         SSH key: | SHA256:2izTnNtsUnOTYpAc68w+NjABBBpLWV34SOaRQuckFso alext@FL-ADMIN-2 |
| SSH pass phrase: | 2008                                                                |


## Set up Windows OS

```

Install Git, Virtual environment, GitHub CLI

```
sudo apt install git
sudo apt-get install python3-venv
sudo apt-get install libpq-dev
```

## Pull from GitHub 

```
cd /opt/forgelabPre
source venv/bin/activate
git pull
sudo reboot
```



## Set up Ubuntu OS

### Set hostname (NetBIOS name)

```
sudo hostnamectl set-hostname fl-pre-1
sudoedit /etc/hosts
hostnamectl
hostname
```

### Set time zone

```
sudo timedatectl set-timezone Asia/Shanghai
timedatectl status
```

### Update

```
sudo apt update && sudo apt upgrade
```

```
sudo reboot
```

### Install Python 3.11 with help Pyenv

```
sudo apt-get update
sudo apt-get install -y make build-essential libssl-dev zlib1g-dev libbz2-dev libreadline-dev libsqlite3-dev wget curl llvm libncursesw5-dev xz-utils tk-dev libxml2-dev libxmlsec1-dev libffi-dev liblzma-dev
curl https://pyenv.run | bash

echo 'export PATH="$HOME/.pyenv/bin:$PATH"' >> ~/.bashrc
echo 'eval "$(pyenv init -)"' >> ~/.bashrc
echo 'eval "$(pyenv virtualenv-init -)"' >> ~/.bashrc

source ~/.bashrc

pyenv install 3.11.4

pyenv versions

pyenv global 3.11.4
```

### Install Git, Virtual environment, GitHub CLI

```
sudo apt install git
sudo apt-get install python3-venv
sudo apt-get install libpq-dev
```

### Clone from GitHub

```
cd /opt && sudo chown alext:alext /opt && sudo chmod 700 /opt
git clone https://github.com/forgingexpert/forgelabPre.git
sudo chown alext:alext /opt/forgelabPre && sudo chmod 700 /opt/forgelabPre && cd /opt/forgelabPre
```

### Set up Virtual Environment

```
cd /opt/forgelabPre && python -m venv venv && source venv/bin/activate
```

### Install libraries

```
python -m pip install --upgrade pip && python -m pip install --upgrade wheel && python -m pip install --upgrade setuptools
pip install -r requirements.txt
```

### Pull from GitHub repo

```
sudo systemctl stop forgelab-pre && cd /opt/forgelabPre && source venv/bin/activate && git pull && sudo systemctl start forgelab-pre
sudo reboot
```

## Pull from GitHub 

Turn on **Astril** `VPN Sharing` function on `Srv-1` server.

Take Gateway IP address from **Astril** `VPN Sharing`. For example `192.168.39.55`

Edit config `00-installer-config.yaml` file. Enter password `Pre7tlva2pv` 

```
sudo nano /etc/netplan/00-installer-config.yaml
sudo netplan generate
sudo netplan apply
```

Set up Gateway. For example  `192.168.39.55`

```
network:
  version: 2
  renderer: networkd
  ethernets:
    ens33:
      dhcp4: True
      dhcp6: False
      nameservers:
        addresses: [192.168.111.2]
      routes:
        - to: default
          via: 192.168.111.2
```

Use GitHub credentials above, when Git asks for username/password.

```
cd /opt/forgelabPre && source venv/bin/activate && git pull
git config --global user.name alext_at_fl-pre-1
git config --global user.email alex.troshin@outlook.com
sudo reboot
```

## Remove project

```
cd /opt/forgelabPre && rm -rf .git* && cd .. && rm -r forgelabPre
git config --global --unset user.name && git config --global --unset user.email
```

## Setting Python script as Ubuntu service for automatic start during boot-up.

Use systemd, which is the default system and service manager for Ubuntu. 
This will also give you the ability to start, stop, and monitor the service in a standardized manner.

### Create a systemd Service File for your application. 

Systemd service files typically reside within the `/etc/systemd/system` directory.

```
sudo nano /etc/systemd/system/forgelabPre.service
```

### Edit the Service File, input the following content

```
[Unit]
Description=ForgelabPre Preview Server
After=network.target

[Service]
User=alext
Group=alext
WorkingDirectory=/opt/forgelabPre/forgelabPre
ExecStart=/opt/forgelabPre/venv/bin/python3 -m main
Restart=always

[Install]
WantedBy=multi-user.target
```

Replace `YOUR_USERNAME` and `YOUR_USERGROUP` with your appropriate Ubuntu username and group (usually, they are the same for a default Ubuntu setup). 
In Ubuntu and most other Linux systems, your primary group is usually named the same as your username by default. However, to confirm the groups your user belongs to, you can use the `groups` command followed by your username.

```
groups alext
```

The command will display a list of all groups your user is a member of. The first group listed is typically your primary group. For example:

```
groups alext
alext : alext adm cdrom sudo dip plugdev lpadmin sambashare
```

In this case, "john" is the primary group for the user "john".
The `ExecStart` path assumes that the virtual environment is named `venv` inside `/opt/forgelabPre`. Adjust this path if it's named differently.

### Reload systemd manager configuration with

```
sudo systemctl daemon-reload
```

### Enable and Start Your Service

```
sudo systemctl enable forgelabPre
sudo systemctl start forgelabPre
```   

### Monitor Your Service

```
sudo journalctl -u forgelabPre -f
```

To exit from `log` view use `Ctrl + C`.

The `-f` flag makes `journalctl` show new messages as they come in.
Now, your Python server should start automatically during OS boot up. 
You can manage it using standard `systemctl` commands:

```
systemctl start forgelab-pre
systemctl stop forgelab-pre
```
