from setuptools import Extension, setup, find_packages
packages = find_packages()

ext_modules = [
    Extension("vhost_raw", sources=["vhost_raw.c", "vhost_mapper.c",
                                    "copy_to_user.c"]),
    Extension("uptime", sources=["uptime.c"], libraries=['rt']),
    Extension("kernel_mapper", sources=["counter.c", "copy_to_user.c"])
]
print ext_modules
setup(name="raw_extensions", author="Eyal Moscocvici", version="0.1",
      packages=packages, ext_modules=ext_modules)
