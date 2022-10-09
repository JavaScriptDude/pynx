## `pynx` - CLI tool for managing nginx daemon, sites and associated wsgi services

Managing `nginx` instances, the activation, deactivation of sites and associated `wsgi` processes can be a bit cumbersome with the number of commands required to manage and analyze.

This tool is designed to allow a user to manage `nginx` daemon status, start, stop, reload etc; `nginx` website, enable, disable, start, stop, status and also `wsgi` process status, start, stop, restart etc; from one CLI utility

This project is still in alpha stage but should be usable.


## Installation
For now, the tool requires to be run from source. Download from github and place in an appropriate 'app' directory and create an appropriate script to invoke that allows it to be run as root (as required by nginx).

Its suggested to use the new (py_src_run)[https://github.com/JavaScriptDude/py_src_run] tool to aid in this process and the file `pynx_install.sh` file in the root of this project is tooled to use `py_src_run`. `py_src_run` has been developed and tested to work with running as root, which is required fo this tool. Deploying a python app that runs as root and does not interfere with the OS's built in python can be tricky and is beyond the experience of the author at this time.


## systemd
As the main developer works primarily in `debian` environments, this tool was developed to work with `systemd`. This tool could be adjusted in the future to work with non-systemd environments but additional developers will be needed to develop and test as such environments will not be focus of the main developer who is sticking with `debian` as main `*nix` development and production environment.


## Dependencies
Linux environments that utilize `systemd`. Python 3.7.9+ environment. Root access.



## nginx server management (pynx \<cmd\>):

### pynx `status`
Show status of nginx daemon
```
[sudo] password for <user>: 
◦ nginx status:
◦   status: active (running) since Fri 2022-10-07 20:17:26 EDT; 1 day 4h ago
◦      pid: 3007225
◦   memory: 31.5M
◦    tasks: 25 (limit: 115744)
◦      cli: /usr/sbin/nginx -g daemon on; master_process on;

```

### pynx `list`
List all available and enabled sites
```
    Site     | Enabled |     Name      |        Listens         | Notes
dev_testsite |    x    | dev_testsite2 | 29990                  | -    
dev_biztools |    x    | dev_biztools  | 9101                   | -    
default      |    -    | _             | 80 default_server      | -    
             |         |               | [::]:80 default_server |      

```

### pynx `test`
Verify site configs
```
Pass - nginx and site configs ok
```

### pynx `start`
Start nginx daemon
```
done - active (running) since Sun 2022-10-09 00:35:10 EDT; 10ms ago
-or-
Server already running (active (running) since Sun 2022-10-09 00:35:10 EDT; 22s ago)
```

### pynx `stop`
Stop nginx daemon
```
done - inactive (dead) since Sun 2022-10-09 00:34:35 EDT; 10ms ago
-or-
Server already inactive (inactive (dead) since Sun 2022-10-09 00:35:56 EDT; 1s ago)
```

### pynx `reload`
Reload nginx daemon
```
done - active (running) since Sun 2022-10-09 00:36:58 EDT; 12ms ago
-or-
Server is inactive (inactive (dead) since Sun 2022-10-09 00:37:25 EDT; 1s ago)
Please use `pynx start`
```
Notes:
* Tool is coded to be aware of segfault issue with perl and nginx in Ubuntu 20.04 and will prompt user to restart instead
* Will not restart if the server is stopped. Prompts user in such a case


### pynx `restart`
Restart nginx daemon
```
done - active (running) since Sun 2022-10-09 00:39:36 EDT; 10ms ago
-or-
Server is inactive (inactive (dead) since Sun 2022-10-09 00:37:25 EDT; 1s ago)
Please use `pynx start`
```


## nginx site management (pynx \<site\> \<cmd\>):

### pynx dev_testsite `status`
Show status for site
```
◦       Site     | Enabled |     Name      | Listens | Notes
◦   dev_testsite |    x    | dev_testsite2 | 29990   | -    
```

### pynx dev_testsite `start`
Enables site if not enabled an reload nginx
```
◦ nginx reloaded
◦ site dev_testsite started
◦       Site     | Enabled |     Name      | Listens | Notes
◦   dev_testsite |    x    | dev_testsite2 | 29990   | -   
# -or-
◦ Site is already started:
◦       Site     | Enabled |     Name      | Listens | Notes
◦   dev_testsite |    x    | dev_testsite2 | 29990   | -    
◦ run `pynx reload` if site is not running

```

### pynx dev_testsite `stop`
Disables site if enabled an reload nginx
```
◦ nginx reloaded
◦ site dev_testsite stopped
◦       Site     | Enabled |     Name      | Listens | Notes
◦   dev_testsite |    -    | dev_testsite2 | 29990   | -    
```

### pynx dev_testsite `enable`
Enables site if not enabled. Will prompt for reload
```
◦ site dev_testsite enabled
◦       Site     | Enabled |     Name      | Listens | Notes
◦   dev_testsite |    x    | dev_testsite2 | 29990   | -    
```

### pynx dev_testsite `disable`
Disables site if enabled. Will prompt for reload
```
◦ site dev_testsite disabled
◦       Site     | Enabled |     Name      | Listens | Notes
◦   dev_testsite |    -    | dev_testsite2 | 29990   | -    
```

### pynx dev_testsite `config`
Prints config summary for site
```
◦ Config for site default:
◦   server {
◦     listen 80 default_server;
◦     listen [::]:80 default_server;
◦     root /var/www/html;
◦     index index.html index.htm index.nginx-debian.html;
◦     server_name _;
◦     location / {
◦       try_files $uri $uri/ =404;
◦     }
◦   }
```


## WSGI commands (pynx wsgi:\<site\> \<cmd\>):

### pynx wsgi:dev_testsite `status`
Show status for site wsgi
```
active - (dev_testsite - active (running) since Fri 2022-10-07 19:59:30 EDT; 1 day 4h ago)
```

### pynx wsgi:dev_testsite `start`
Starts site wsgi if stopped
```
WSGI started (dev_testsite - active (running) since Sun 2022-10-09 00:47:24 EDT; 11ms ago)
```

### pynx wsgi:dev_testsite `stop`
Stops site wsgi if started
```
WSGI stopped (dev_testsite - inactive (dead) since Sun 2022-10-09 00:47:04 EDT; 13ms ago)
```

### pynx wsgi:dev_testsite `restart`
Restart site wsgi
```
WSGI restarted (dev_testsite - active (running) since Sun 2022-10-09 00:47:56 EDT; 10ms ago)
```


## Request for assistance
I am wide open for suggestions on how to improve the API and output. Please give this tool a run and pass along ideas.
If any python deveopers can assist with packaging this more formally to make it easier to deploy as a proper PyPi installed project, it would be greatly appreciated. I don't have experience with packaging cli apps on PyPi and need the help! I did do alot of testing to get proper installs working but ran out of time and decided to get the tried tested and trued `run from source` method working for the time being.



## Python Code Styling notes
My code styling may look quite different from python developers but its based on many years of experience developing systems in many other langages over my career. Over my time developing applications, I have swayed heavily to towards `fail fast` design principles, developing methods for early assertions of data and parameters which makes the development process much smoother as errors are easier to trace with the first exception rather than having `null pointer` type exceptions burried down the callstacks requiring back tracking to find the source of bad data. I will streamline the code in the future to be a bit faster and concise but for now its a slow and steady design approach.