I/O manager
===========

First, we need to create a configuration file for the iomanager. On your target machine (i.e. the host) run:

`src/create_configuration_file.py <num_of_cores> <network_interface_name[,second_if_name]> [OPTIONS]`

- `num_of_cores`: is the number of cores on your system; use less if you want to confine the virtual machines and iocores to use a subset of the available cores
- `network_interface_name`: is the interface name (from the host perspective) in which all traffic of the virtual machines goes through. Currently, supporting up to 2 NICs

Options:
- `--config`: override the default configuration file path
- `--min`: minimum number of iocores allowed
- `--max`: maximum number of iocores allowed


Note: the configuration file is stored in /tmp/ by default

Next, run the iomanager:

`/src/start_io_manager.py [OPTIONS]`

Options:
- `-c, --config`: override the default configuration file path
- `-p, --process`: run as a process (as opposed to a daemon) and direct all output to stdout/stderr


Note: it is possible to manually tune the configuration settings (you should better know what you're doing); for more information please see: confs/configuration_template.json

To stop the iomanager daemon run the following command:

`/src/stop_io_manager.py`

