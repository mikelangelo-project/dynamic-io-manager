I/O manager
===========

First, we need to create a configuration file for the iomanager. On your target machine (i.e. the host) run:

`src/create_configuration_file.py <num_of_cores> <network_interface_name_1> [network_interface_name_2]` 

- `num_of_cores`: is the number of cores on your system; use less if you want to confine the virtual machines and iocores to use a subset of the available cores
- `network_interface_name_1/2`: is the interface name (from the host perspective) in which all traffic of the virtual machines goes through. Currently, supporting up to 2 NICs.
Note: the configuration file is stored at /tmp/

Next, run the iomanager:

`/src/start_io_manager.py <configuration_file>`

- `configuration_file`: is the configuration file path

Note: it is possible to manually tune the configuration settings (you should better know what you're doing); for more information please see: confs/configuration_template.json
